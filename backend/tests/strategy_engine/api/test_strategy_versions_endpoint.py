"""Phase 2 — `/api/strategies/{id}/versions` endpoint tests.

Each test boots a tiny FastAPI app holding both the strategies CRUD
router (so we can POST/PUT to drive the auto-version side-effect) and
the new versions router. The Phase-1 file-store is redirected at a
fresh tmp directory per test so on-disk state never bleeds across
tests or into the developer's real cache.
"""

from __future__ import annotations

import uuid as _uuid
from collections.abc import AsyncIterator, Iterator
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
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api import router as strategy_crud_router
from app.strategy_engine.api.strategy_versions import (
    router as strategy_versions_router,
)
from tests.strategy_engine.api.conftest import _seed_user, make_strategy_payload

# Note: version-store isolation is provided by the autouse
# ``_isolated_version_store`` fixture in conftest.py.


@pytest_asyncio.fixture
async def db_session_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Per-test in-memory aiosqlite engine, single shared connection."""
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-strategy-versions-{_uuid.uuid4().hex}"
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


@pytest_asyncio.fixture
async def seed_user(
    db_session_maker: async_sessionmaker[AsyncSession],
) -> User:
    return await _seed_user(db_session_maker, email="phase2-versions@tradetri.com")


def _build_app(
    db_session_maker: async_sessionmaker[AsyncSession],
    user: User | None,
) -> FastAPI:
    """Build the test app. ``user=None`` leaves auth unstubbed so the
    real :func:`get_current_active_user` runs and 401s on missing
    Authorization header."""
    app = FastAPI()
    # Versions router first, mirroring main.py ordering: literal
    # sub-paths > /{strategy_id}.
    app.include_router(strategy_versions_router)
    app.include_router(strategy_crud_router)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with db_session_maker() as s:
            try:
                yield s
            except Exception:
                await s.rollback()
                raise

    app.dependency_overrides[get_session] = _override_session
    if user is not None:
        async def _override_user() -> User:
            return user

        app.dependency_overrides[get_current_active_user] = _override_user
    return app


@pytest.fixture
def client(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> Iterator[TestClient]:
    app = _build_app(db_session_maker, seed_user)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def unauthenticated_client(
    db_session_maker: async_sessionmaker[AsyncSession],
) -> Iterator[TestClient]:
    """Client with no auth override — every protected endpoint 401s."""
    app = _build_app(db_session_maker, user=None)
    with TestClient(app) as c:
        yield c


def _create_strategy(client: TestClient, **kwargs: Any) -> dict[str, Any]:
    resp = client.post("/api/strategies", json=make_strategy_payload(**kwargs))
    assert resp.status_code == 201, resp.text
    return resp.json()  # type: ignore[no-any-return]


# ─── 1. POST /api/strategies creates v1 automatically ────────────────


def test_post_strategies_auto_creates_v1(client: TestClient) -> None:
    body = _create_strategy(client)
    assert body["current_version_number"] == 1

    versions = client.get(f"/api/strategies/{body['id']}/versions").json()
    assert len(versions) == 1
    assert versions[0]["version_number"] == 1
    assert versions[0]["change_summary"] == "Initial version"
    assert versions[0]["parent_version_id"] is None
    assert versions[0]["strategy_json"]["name"] == body["name"]


# ─── 2. PUT /api/strategies/{id} creates v2 with diff summary ────────


def test_put_strategies_auto_creates_v2_with_diff_summary(client: TestClient) -> None:
    created = _create_strategy(client, name="v1", strategy_id="sid")
    new_payload = make_strategy_payload(name="v2", strategy_id="sid")
    new_payload["strategy_json"]["exit"]["targetPercent"] = 7.5

    resp = client.put(f"/api/strategies/{created['id']}", json=new_payload)
    assert resp.status_code == 200
    assert resp.json()["current_version_number"] == 2

    versions = client.get(f"/api/strategies/{created['id']}/versions").json()
    assert [v["version_number"] for v in versions] == [1, 2]
    assert versions[1]["parent_version_id"] == versions[0]["version_id"]
    # diff summary is non-empty and references the change.
    assert versions[1]["change_summary"]
    # Either the exit branch or the target heuristic should fire.
    summary_lower = versions[1]["change_summary"].lower()
    assert "target" in summary_lower or "exit" in summary_lower or "modified" in summary_lower


# ─── 3. GET /versions lists all versions ─────────────────────────────


def test_list_versions_returns_full_history(client: TestClient) -> None:
    created = _create_strategy(client)
    for tp in (3.0, 4.0, 5.0):
        new = make_strategy_payload(name="x", strategy_id="x_id")
        new["strategy_json"]["exit"]["targetPercent"] = tp
        client.put(f"/api/strategies/{created['id']}", json=new)

    resp = client.get(f"/api/strategies/{created['id']}/versions")
    assert resp.status_code == 200
    versions = resp.json()
    assert [v["version_number"] for v in versions] == [1, 2, 3, 4]


def test_list_versions_respects_limit_returning_newest(client: TestClient) -> None:
    created = _create_strategy(client)
    for tp in (3.0, 4.0, 5.0, 6.0):
        new = make_strategy_payload(name="x", strategy_id="x_id")
        new["strategy_json"]["exit"]["targetPercent"] = tp
        client.put(f"/api/strategies/{created['id']}", json=new)

    resp = client.get(f"/api/strategies/{created['id']}/versions?limit=2")
    assert resp.status_code == 200
    versions = resp.json()
    assert [v["version_number"] for v in versions] == [4, 5]


# ─── 4. GET /versions/{n} returns specific version ───────────────────


def test_get_specific_version(client: TestClient) -> None:
    created = _create_strategy(client, name="v1")
    updated = make_strategy_payload(name="v2-name", strategy_id="x")
    client.put(f"/api/strategies/{created['id']}", json=updated)

    resp = client.get(f"/api/strategies/{created['id']}/versions/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version_number"] == 1
    assert body["strategy_json"]["name"] == "v1"


def test_get_unknown_version_returns_404(client: TestClient) -> None:
    created = _create_strategy(client)
    resp = client.get(f"/api/strategies/{created['id']}/versions/99")
    assert resp.status_code == 404


# ─── 5. GET /versions/compare returns diff ───────────────────────────


def test_compare_versions_returns_diff(client: TestClient) -> None:
    created = _create_strategy(client, name="v1")
    new = make_strategy_payload(name="v2", strategy_id="sid")
    new["strategy_json"]["exit"]["targetPercent"] = 9.0
    client.put(f"/api/strategies/{created['id']}", json=new)

    resp = client.get(
        f"/api/strategies/{created['id']}/versions/compare"
        "?from_version=1&to_version=2"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["from_version"] == 1
    assert body["to_version"] == 2
    assert any("targetPercent" in d["field_path"] for d in body["diffs"])
    assert body["summary_hinglish"]


# ─── 6. POST /versions/{n}/rollback creates new version with old ─────


def test_rollback_creates_new_version_and_updates_main_row(client: TestClient) -> None:
    created = _create_strategy(client, name="orig")
    # Bump to v2 with different content.
    new = make_strategy_payload(name="changed", strategy_id="x")
    new["strategy_json"]["exit"]["targetPercent"] = 9.0
    client.put(f"/api/strategies/{created['id']}", json=new)

    resp = client.post(f"/api/strategies/{created['id']}/versions/1/rollback")
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_version_number"] == 3
    # Live row reflects rolled-back content.
    assert body["name"] == "orig"
    assert body["strategy_json"]["exit"]["targetPercent"] == 2.0

    # History intact: 3 entries, with v3 mirroring v1's payload.
    versions = client.get(f"/api/strategies/{created['id']}/versions").json()
    assert [v["version_number"] for v in versions] == [1, 2, 3]
    assert versions[2]["change_summary"] == "Rolled back to v1"
    assert versions[2]["strategy_json"]["exit"]["targetPercent"] == 2.0


def test_rollback_to_unknown_version_returns_404(client: TestClient) -> None:
    created = _create_strategy(client)
    resp = client.post(f"/api/strategies/{created['id']}/versions/99/rollback")
    assert resp.status_code == 404


# ─── 7. Cross-user enumeration blocked (404 not 403) ─────────────────


@pytest.mark.asyncio
async def test_user_b_cannot_access_user_a_versions(
    client: TestClient,
    db_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    """User B sees 404 for every versions endpoint operating on user
    A's strategy — same opaque-404 contract as the CRUD router."""
    created = _create_strategy(client, name="a-only")
    sid = created["id"]

    user_b = await _seed_user(
        db_session_maker, email="phase2-other@tradetri.com"
    )

    async def _override_user_b() -> User:
        return user_b

    client.app.dependency_overrides[get_current_active_user] = _override_user_b  # type: ignore[attr-defined]

    assert client.get(f"/api/strategies/{sid}/versions").status_code == 404
    assert client.get(f"/api/strategies/{sid}/versions/1").status_code == 404
    assert (
        client.get(
            f"/api/strategies/{sid}/versions/compare?from_version=1&to_version=1"
        ).status_code
        == 404
    )
    assert (
        client.post(f"/api/strategies/{sid}/versions/1/rollback").status_code == 404
    )


# ─── 8. Auth required (401 without token) ────────────────────────────


def test_versions_endpoints_require_auth(
    unauthenticated_client: TestClient,
) -> None:
    """Without an Authorization header every protected endpoint
    short-circuits to 401 before touching the DB or the version store."""
    fake_id = _uuid.uuid4()
    expected = {401, 403}  # 401 in our deps; tolerate 403 if auth layer changes.

    assert unauthenticated_client.get(f"/api/strategies/{fake_id}/versions").status_code in expected
    assert (
        unauthenticated_client.get(f"/api/strategies/{fake_id}/versions/1").status_code in expected
    )
    assert (
        unauthenticated_client.get(
            f"/api/strategies/{fake_id}/versions/compare?from_version=1&to_version=1"
        ).status_code
        in expected
    )
    assert (
        unauthenticated_client.post(
            f"/api/strategies/{fake_id}/versions/1/rollback"
        ).status_code
        in expected
    )


# ─── 9. Existing strategy CRUD still works (regression) ──────────────


def test_existing_get_and_delete_unaffected_by_versioning(client: TestClient) -> None:
    created = _create_strategy(client, name="ok")
    sid = created["id"]

    # Plain GET still returns the row.
    resp = client.get(f"/api/strategies/{sid}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "ok"

    # DELETE still 204s — versioning history persists on disk after
    # the row is gone (Phase 1 doesn't cascade), which is intentional:
    # an audit trail of strategies a user once owned is not a leak.
    assert client.delete(f"/api/strategies/{sid}").status_code == 204
    assert client.get(f"/api/strategies/{sid}").status_code == 404


# ─── 10. Comparison Hinglish summary correct for indicator add ───────


def test_compare_hinglish_summary_mentions_indicator_addition(
    client: TestClient,
) -> None:
    created = _create_strategy(client)

    # Add a second indicator via PUT.
    augmented = make_strategy_payload()
    augmented["strategy_json"]["indicators"].append(
        {"id": "rsi_14", "type": "rsi", "params": {"period": 14}}
    )
    client.put(f"/api/strategies/{created['id']}", json=augmented)

    resp = client.get(
        f"/api/strategies/{created['id']}/versions/compare"
        "?from_version=1&to_version=2"
    )
    assert resp.status_code == 200
    summary = resp.json()["summary_hinglish"].lower()
    assert "indicator" in summary
    assert "added" in summary


# ─── Bonus: returned StrategyVersion shape round-trips ───────────────


def test_version_payload_shape_matches_pydantic_model(client: TestClient) -> None:
    created = _create_strategy(client)
    body = client.get(f"/api/strategies/{created['id']}/versions/1").json()
    # Required fields per StrategyVersion model.
    for key in (
        "version_id",
        "strategy_id",
        "version_number",
        "strategy_json",
        "change_summary",
        "created_by",
        "created_at",
        "parent_version_id",
    ):
        assert key in body, f"missing {key} in version response"
    assert body["strategy_id"] == created["id"]


# ─── Bonus: list_versions for unknown owned-but-empty strategy ──────


def test_list_versions_for_known_strategy_with_no_history_is_empty(
    client: TestClient,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    """Direct-DB-insert a strategy without going through POST so the
    auto-versioning side-effect doesn't fire. Listing versions should
    then return an empty list (and 200, not 404 — the strategy exists,
    its history just doesn't)."""
    import asyncio

    from app.db.models.strategy import Strategy

    async def _insert() -> _uuid.UUID:
        async with db_session_maker() as s:
            row = Strategy(
                user_id=seed_user.id,
                name="no-history",
                strategy_json={"name": "no-history"},
                is_active=True,
            )
            s.add(row)
            await s.commit()
            await s.refresh(row)
            return row.id

    sid = asyncio.run(_insert())
    resp = client.get(f"/api/strategies/{sid}/versions")
    assert resp.status_code == 200
    assert resp.json() == []
