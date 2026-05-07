"""Phase 7 — ``POST /api/strategies/{id}/compare-fix``.

Self-contained: each test builds its own FastAPI app holding the
backtest + compare-fix routers and overrides the auth + DB session
dependencies. A fresh sqlite-in-memory engine per test keeps state
isolated.

Coverage:

    * happy path — POST returns ``{ original, improved, comparison }``
                   with the seven master deltas + Hinglish verdict.
    * 422 — proposed draft fails StrategyJSON validation.
    * 401 — auth required when no override is registered.
    * 404 — strategy id unknown OR not owned by the caller.
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
from app.db.base import Base
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api import router as strategy_crud_router
from app.strategy_engine.api.compare_fix import router as compare_fix_router

# ─── Fixtures ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-cf-{uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


async def _seed_user(maker: async_sessionmaker[AsyncSession], email: str) -> User:
    async with maker() as s:
        user = User(email=email, password_hash="x", is_active=True)
        s.add(user)
        await s.commit()
        await s.refresh(user)
        return user


_SAMPLE_STRATEGY_JSON: dict[str, Any] = {
    "id": "compare_fix_test",
    "name": "Compare-fix test",
    "mode": "expert",
    "indicators": [
        {"id": "ema_5", "type": "ema", "params": {"period": 5}},
    ],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [{"type": "indicator", "left": "ema_5", "op": ">", "value": 95.0}],
    },
    "exit": {"targetPercent": 1.5, "stopLossPercent": 1.0},
    "risk": {},
    "execution": {
        "mode": "backtest",
        "orderType": "MARKET",
        "productType": "INTRADAY",
    },
}


async def _seed_strategy(
    maker: async_sessionmaker[AsyncSession], *, user_id: uuid.UUID
) -> Strategy:
    async with maker() as s:
        strategy = Strategy(
            user_id=user_id,
            name="compare-fix test strategy",
            strategy_json=dict(_SAMPLE_STRATEGY_JSON),
            is_active=True,
        )
        s.add(strategy)
        await s.commit()
        await s.refresh(strategy)
        return strategy


@pytest.fixture
def make_client(
    db_maker: async_sessionmaker[AsyncSession],
) -> Callable[[User], TestClient]:
    """Builder that returns a TestClient impersonating ``user``."""

    def _build(user: User) -> TestClient:
        app = FastAPI()
        app.include_router(compare_fix_router)
        app.include_router(strategy_crud_router)

        async def _override_session() -> AsyncIterator[AsyncSession]:
            async with db_maker() as s:
                try:
                    yield s
                except Exception:
                    await s.rollback()
                    raise

        async def _override_user() -> User:
            return user

        app.dependency_overrides[get_session] = _override_session
        app.dependency_overrides[get_current_active_user] = _override_user
        return TestClient(app)

    return _build


# ─── Happy path ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_compare_fix_returns_original_improved_and_comparison(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """200 + ``{original, improved, comparison}`` shape with deltas."""
    user = await _seed_user(db_maker, "owner@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=user.id)

    # Tighten the stop loss in the proposed draft so the two
    # pipelines produce different (but well-formed) results.
    improved_draft = dict(_SAMPLE_STRATEGY_JSON)
    improved_draft["exit"] = {"targetPercent": 2.0, "stopLossPercent": 0.5}

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/compare-fix",
            json={"improved_strategy_draft": improved_draft},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {"original", "improved", "comparison"}

    for side in ("original", "improved"):
        snapshot = body[side]
        assert set(snapshot.keys()) == {
            "backtest",
            "reliability",
            "health_card",
            "truth",
            "trade_quality",
        }
        # Backtest section uses camelCase aliases.
        assert "totalPnl" in snapshot["backtest"]
        # Health card uses snake_case (coach has no aliases).
        assert "overall_grade" in snapshot["health_card"]

    comparison = body["comparison"]
    for key in (
        "pnl_delta",
        "win_rate_delta",
        "drawdown_delta",
        "profit_factor_delta",
        "truth_score_delta",
        "trust_score_delta",
        "trade_quality_delta",
        "verdict_hinglish",
    ):
        assert key in comparison, f"missing comparison key {key!r}"
    assert isinstance(comparison["verdict_hinglish"], str)
    assert len(comparison["verdict_hinglish"]) > 0
    # The Hinglish verdict is one of the three locked phrases.
    assert any(
        phrase in comparison["verdict_hinglish"]
        for phrase in ("better hai", "mixed", "Original strategy")
    )


# ─── 422 — invalid draft ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_compare_fix_returns_422_for_invalid_draft(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    user = await _seed_user(db_maker, "validator@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=user.id)

    # Missing the ``execution`` block — StrategyJSON requires it.
    bad_draft = {
        "id": "broken",
        "name": "bad",
        "mode": "expert",
        "indicators": [],
        "entry": {
            "side": "BUY",
            "operator": "AND",
            "conditions": [{"type": "price", "op": ">", "value": 1.0}],
        },
        "exit": {"targetPercent": 1.0},
    }

    with make_client(user) as client:
        resp = client.post(
            f"/api/strategies/{strategy.id}/compare-fix",
            json={"improved_strategy_draft": bad_draft},
        )

    assert resp.status_code == 422
    assert "improved_strategy_draft" in resp.json()["detail"]


# ─── 404 — unknown / cross-user strategy ──────────────────────────────


@pytest.mark.asyncio
async def test_compare_fix_returns_404_on_unknown_or_unowned_strategy(
    db_maker: async_sessionmaker[AsyncSession],
    make_client: Callable[[User], TestClient],
) -> None:
    """404 covers both 'not found' and 'not yours' — same body keeps
    the endpoint from being an enumeration oracle."""
    owner = await _seed_user(db_maker, "owner-cf@tradetri.com")
    intruder = await _seed_user(db_maker, "intruder-cf@tradetri.com")
    strategy = await _seed_strategy(db_maker, user_id=owner.id)

    body = {"improved_strategy_draft": dict(_SAMPLE_STRATEGY_JSON)}

    with make_client(owner) as client:
        unknown_resp = client.post(f"/api/strategies/{uuid.uuid4()}/compare-fix", json=body)
    assert unknown_resp.status_code == 404

    with make_client(intruder) as client:
        cross_resp = client.post(f"/api/strategies/{strategy.id}/compare-fix", json=body)
    assert cross_resp.status_code == 404


# ─── 401 — without auth override ──────────────────────────────────────


def test_compare_fix_requires_authentication() -> None:
    """Without the auth dep override, the dep raises 401 before any
    DB lookup happens — so this test needs no DB plumbing."""
    app = FastAPI()
    app.include_router(compare_fix_router)
    with TestClient(app) as client:
        resp = client.post(
            f"/api/strategies/{uuid.uuid4()}/compare-fix",
            json={"improved_strategy_draft": dict(_SAMPLE_STRATEGY_JSON)},
        )
    assert resp.status_code == 401
