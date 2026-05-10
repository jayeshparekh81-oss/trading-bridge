"""``/api/compliance`` route tests — RBAC + cross-user isolation.

Mirrors the per-test in-memory aiosqlite + dependency_overrides
pattern used by the marketplace / support / onboarding tests in
this module.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_active_user
from app.auth.roles import ROLE_ADMIN, ROLE_USER
from app.db.base import Base
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api.compliance import router as compliance_router


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-cmpl-{uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    yield maker
    await engine.dispose()


async def _seed_user(
    maker: async_sessionmaker[AsyncSession], *, email: str, role: str
) -> User:
    async with maker() as s:
        u = User(email=email, password_hash="x", is_active=True, role=role)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def _seed_strategy(
    maker: async_sessionmaker[AsyncSession],
    *,
    user: User,
    name: str,
    indicators: list[dict[str, Any]],
) -> Strategy:
    async with maker() as s:
        strat = Strategy(
            user_id=user.id,
            name=name,
            strategy_json={
                "name": name,
                "mode": "beginner",
                "indicators": indicators,
            },
            is_active=True,
        )
        s.add(strat)
        await s.commit()
        await s.refresh(strat)
        return strat


@pytest.fixture
def make_client(
    db_maker: async_sessionmaker[AsyncSession],
) -> Callable[[User | None], TestClient]:
    def _build(user: User | None) -> TestClient:
        app = FastAPI()
        app.include_router(compliance_router)

        async def _override_session() -> AsyncIterator[AsyncSession]:
            async with db_maker() as s:
                yield s

        app.dependency_overrides[get_session] = _override_session

        if user is not None:
            async def _override_user() -> User:
                async with db_maker() as s:
                    fresh = await s.get(User, user.id)
                    assert fresh is not None
                    return fresh

            app.dependency_overrides[get_current_active_user] = _override_user

        return TestClient(app)

    return _build


# ─── User endpoints ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_my_summary_returns_caller_strategies_only(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    """A user only sees their own strategies — never strategies
    owned by other users (cross-tenant isolation)."""
    alice = await _seed_user(db_maker, email="alice@x", role=ROLE_USER)
    bob = await _seed_user(db_maker, email="bob@x", role=ROLE_USER)
    await _seed_strategy(
        db_maker,
        user=alice,
        name="alice-strategy",
        indicators=[{"id": "a1", "type": "ema"}],
    )
    await _seed_strategy(
        db_maker,
        user=bob,
        name="bob-strategy",
        indicators=[{"id": "b1", "type": "ema"}],
    )
    with make_client(alice) as client:
        resp = client.get("/api/compliance/strategies/me")
    body = resp.json()
    assert resp.status_code == 200
    names = {s["strategy_name"] for s in body["strategies"]}
    assert names == {"alice-strategy"}


@pytest.mark.asyncio
async def test_my_summary_compliance_scores_match_indicator_status(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    """Active-only → 100; one coming_soon → 90."""
    alice = await _seed_user(db_maker, email="alice2@x", role=ROLE_USER)
    await _seed_strategy(
        db_maker,
        user=alice,
        name="all-active",
        indicators=[{"id": "a1", "type": "ema"}],
    )
    await _seed_strategy(
        db_maker,
        user=alice,
        name="one-cs",
        indicators=[
            {"id": "a1", "type": "ema"},
            {"id": "a2", "type": "kama"},
        ],
    )
    with make_client(alice) as client:
        resp = client.get("/api/compliance/strategies/me")
    body = resp.json()
    by_name = {s["strategy_name"]: s for s in body["strategies"]}
    assert by_name["all-active"]["compliance_score"] == 100
    assert by_name["one-cs"]["compliance_score"] == 90


@pytest.mark.asyncio
async def test_strategy_detail_for_owner_returns_full_report(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    alice = await _seed_user(db_maker, email="alice3@x", role=ROLE_USER)
    s = await _seed_strategy(
        db_maker,
        user=alice,
        name="detail-test",
        indicators=[{"id": "a1", "type": "kama"}],
    )
    with make_client(alice) as client:
        resp = client.get(f"/api/compliance/strategies/{s.id}")
    body = resp.json()
    assert resp.status_code == 200
    assert body["strategy_name"] == "detail-test"
    assert body["compliance_score"] == 90
    assert len(body["warnings"]) == 1


@pytest.mark.asyncio
async def test_cross_user_strategy_detail_returns_404_not_403(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    """Probing for someone else's strategy id must return 404 —
    a 403 would leak the existence of the row."""
    alice = await _seed_user(db_maker, email="alice4@x", role=ROLE_USER)
    bob = await _seed_user(db_maker, email="bob4@x", role=ROLE_USER)
    bob_strat = await _seed_strategy(
        db_maker,
        user=bob,
        name="bob-private",
        indicators=[],
    )
    with make_client(alice) as client:
        resp = client.get(f"/api/compliance/strategies/{bob_strat.id}")
    assert resp.status_code == 404


def test_unauthenticated_my_summary_returns_401(
    make_client: Callable[[User | None], TestClient],
) -> None:
    with make_client(None) as client:
        resp = client.get("/api/compliance/strategies/me")
    assert resp.status_code == 401


# ─── Admin endpoints ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_indicator_usage_stats_admin_only(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    """Non-admin users get 403 from /indicators."""
    user = await _seed_user(db_maker, email="user@x", role=ROLE_USER)
    with make_client(user) as client:
        resp = client.get("/api/compliance/indicators")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_indicator_usage_stats_returns_counts_for_admin(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    """Two strategies referencing ema → ema row reports
    total_strategies_using=2 and total_users_affected=2."""
    admin = await _seed_user(db_maker, email="admin@x", role=ROLE_ADMIN)
    alice = await _seed_user(db_maker, email="alice5@x", role=ROLE_USER)
    bob = await _seed_user(db_maker, email="bob5@x", role=ROLE_USER)
    await _seed_strategy(
        db_maker,
        user=alice,
        name="a",
        indicators=[{"id": "a1", "type": "ema"}],
    )
    await _seed_strategy(
        db_maker,
        user=bob,
        name="b",
        indicators=[{"id": "b1", "type": "ema"}],
    )
    with make_client(admin) as client:
        resp = client.get("/api/compliance/indicators")
    body = resp.json()
    assert resp.status_code == 200
    by_id = {row["indicator_id"]: row for row in body["indicators"]}
    assert by_id["ema"]["total_strategies_using"] == 2
    assert by_id["ema"]["total_users_affected"] == 2
    # Promotion candidate is False for ema (it's already active,
    # so the flag never lights up regardless of usage).
    assert by_id["ema"]["is_promotion_candidate"] is False


@pytest.mark.asyncio
async def test_indicator_usage_stats_surfaces_unknown_ids(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    """Strategies referencing an indicator id that's not in the
    registry produce a synthetic ``unknown:`` row in the response —
    admin needs visibility into stale references."""
    admin = await _seed_user(db_maker, email="admin2@x", role=ROLE_ADMIN)
    alice = await _seed_user(db_maker, email="alice6@x", role=ROLE_USER)
    await _seed_strategy(
        db_maker,
        user=alice,
        name="ghost-strat",
        indicators=[{"id": "ghost", "type": "definitely_not_in_registry_xyz"}],
    )
    with make_client(admin) as client:
        resp = client.get("/api/compliance/indicators")
    body = resp.json()
    by_id = {row["indicator_id"]: row for row in body["indicators"]}
    assert "definitely_not_in_registry_xyz" in by_id
    assert by_id["definitely_not_in_registry_xyz"]["status"] == "unknown"
    assert by_id["definitely_not_in_registry_xyz"][
        "total_strategies_using"
    ] == 1


@pytest.mark.asyncio
async def test_admin_all_strategies_paginates_and_reports_has_more(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    admin = await _seed_user(db_maker, email="admin3@x", role=ROLE_ADMIN)
    alice = await _seed_user(db_maker, email="alice7@x", role=ROLE_USER)
    for i in range(3):
        await _seed_strategy(
            db_maker,
            user=alice,
            name=f"s{i}",
            indicators=[{"id": "x", "type": "ema"}],
        )
    with make_client(admin) as client:
        resp = client.get(
            "/api/compliance/strategies/all?limit=2&offset=0"
        )
    body = resp.json()
    assert resp.status_code == 200
    assert body["count"] == 2
    assert body["has_more"] is True
    with make_client(admin) as client:
        resp2 = client.get(
            "/api/compliance/strategies/all?limit=2&offset=2"
        )
    body2 = resp2.json()
    assert body2["count"] == 1
    assert body2["has_more"] is False


@pytest.mark.asyncio
async def test_admin_all_strategies_min_score_filter(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    """``min_score=70`` returns only strategies whose compliance
    score is at most 70 — the worst offenders."""
    admin = await _seed_user(db_maker, email="admin4@x", role=ROLE_ADMIN)
    alice = await _seed_user(db_maker, email="alice8@x", role=ROLE_USER)
    # All-active → 100 (above filter, excluded)
    await _seed_strategy(
        db_maker,
        user=alice,
        name="clean",
        indicators=[{"id": "x", "type": "ema"}],
    )
    # One unknown → 50 (below filter, included)
    await _seed_strategy(
        db_maker,
        user=alice,
        name="dirty",
        indicators=[{"id": "g", "type": "no_such_indicator"}],
    )
    with make_client(admin) as client:
        resp = client.get(
            "/api/compliance/strategies/all?limit=50&offset=0&min_score=70"
        )
    body = resp.json()
    names = [s["strategy_name"] for s in body["strategies"]]
    assert "dirty" in names
    assert "clean" not in names


@pytest.mark.asyncio
async def test_admin_all_strategies_blocks_non_admin(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    user = await _seed_user(db_maker, email="not-admin@x", role=ROLE_USER)
    with make_client(user) as client:
        resp = client.get("/api/compliance/strategies/all")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_all_strategies_limit_bounds_enforced(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User | None], TestClient],
) -> None:
    """``limit > 200`` is a 422 (Pydantic clamps via Query)."""
    admin = await _seed_user(db_maker, email="admin5@x", role=ROLE_ADMIN)
    with make_client(admin) as client:
        resp = client.get(
            "/api/compliance/strategies/all?limit=10000"
        )
    assert resp.status_code == 422
