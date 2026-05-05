"""Phase 5 — `/api/strategies` CRUD endpoints.

Each test boots a tiny FastAPI app holding only the strategies router
(see ``conftest.py``) so the assertions describe the public HTTP
contract: status codes, persisted shape, isolation across users.

Coverage matrix:

    create        → 201, body is a StrategyResponse, row exists
    create-422    → invalid StrategyJSON is rejected at the boundary
    list          → newest-first, only the caller's rows
    get-one       → 200 happy path
    get-404       → unknown id
    update        → 200, name + json replaced
    delete        → 204, row gone, subsequent GET → 404
    isolation     → user-B can't read/update/delete user-A's strategy
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_current_active_user
from app.db.models.strategy import Strategy
from app.db.models.user import User
from tests.strategy_engine.api.conftest import _seed_user, make_strategy_payload

# ─── create ────────────────────────────────────────────────────────────


def test_create_strategy_returns_201_and_persists_row(
    client: TestClient,
    seed_user: User,
) -> None:
    payload = make_strategy_payload(name="EMA cross v1", strategy_id="ema_cross_v1")

    resp = client.post("/api/strategies", json=payload)

    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "EMA cross v1"
    assert body["is_active"] is True
    assert uuid.UUID(body["id"])  # parses
    # by-alias round-trip — exit fields come back camelCased.
    assert body["strategy_json"]["exit"]["targetPercent"] == 2.0
    assert body["strategy_json"]["entry"]["conditions"][0]["left"] == "ema_20"
    # owner is the seeded user (not surfaced in the response, asserted via list).
    list_resp = client.get("/api/strategies")
    assert list_resp.status_code == 200
    assert list_resp.json()["count"] == 1


def test_create_strategy_422_on_invalid_dsl(client: TestClient) -> None:
    """A StrategyJSON that fails Pydantic validation never hits the DB."""
    payload = make_strategy_payload()
    # Reference an undeclared indicator id — StrategyJSON's
    # `_indicator_ids_unique_and_referenced` validator rejects this.
    payload["strategy_json"]["entry"]["conditions"][0]["left"] = "missing_id"

    resp = client.post("/api/strategies", json=payload)

    assert resp.status_code == 422


def test_create_strategy_422_on_missing_exit_primitive(
    client: TestClient,
) -> None:
    """ExitRules requires at least one exit primitive."""
    payload = make_strategy_payload()
    payload["strategy_json"]["exit"] = {}

    resp = client.post("/api/strategies", json=payload)

    assert resp.status_code == 422


# ─── list ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_returns_only_caller_strategies_newest_first(
    client: TestClient,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    """List is scoped by user_id and ordered by created_at desc.

    SQLite's ``CURRENT_TIMESTAMP`` is per-second, so three back-to-back
    POSTs end up with identical ``created_at`` values and the
    ``order_by`` tiebreaker is undefined. We backdate each row through
    the session to lock down a deterministic ordering — the assertion
    then exercises the actual ``desc()`` query the handler runs.
    """
    created_ids: list[str] = []
    for i in range(3):
        resp = client.post(
            "/api/strategies",
            json=make_strategy_payload(
                name=f"strat-{i}", strategy_id=f"strat_{i}"
            ),
        )
        assert resp.status_code == 201
        created_ids.append(resp.json()["id"])

    # Backdate so strat-0 is oldest, strat-2 is newest.
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    async with db_session_maker() as s:
        for i, sid in enumerate(created_ids):
            await s.execute(
                update(Strategy)
                .where(Strategy.id == uuid.UUID(sid))
                .values(created_at=base + timedelta(seconds=i))
            )
        await s.commit()

    resp = client.get("/api/strategies")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 3
    names = [item["name"] for item in body["strategies"]]
    assert names == ["strat-2", "strat-1", "strat-0"]


def test_list_empty_when_no_strategies(client: TestClient) -> None:
    resp = client.get("/api/strategies")

    assert resp.status_code == 200
    assert resp.json() == {"strategies": [], "count": 0}


# ─── get-one ───────────────────────────────────────────────────────────


def test_get_strategy_happy_path(client: TestClient) -> None:
    created = client.post(
        "/api/strategies", json=make_strategy_payload(name="fetched")
    ).json()

    resp = client.get(f"/api/strategies/{created['id']}")

    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]
    assert resp.json()["name"] == "fetched"


def test_get_unknown_id_returns_404(client: TestClient) -> None:
    resp = client.get(f"/api/strategies/{uuid.uuid4()}")

    assert resp.status_code == 404
    assert resp.json() == {"detail": "Strategy not found."}


# ─── update ────────────────────────────────────────────────────────────


def test_update_replaces_name_and_payload(client: TestClient) -> None:
    created = client.post(
        "/api/strategies",
        json=make_strategy_payload(name="v1", strategy_id="v1_id"),
    ).json()

    new_payload = make_strategy_payload(name="v2 renamed", strategy_id="v2_id")
    new_payload["strategy_json"]["exit"]["targetPercent"] = 5.5

    resp = client.put(f"/api/strategies/{created['id']}", json=new_payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created["id"]
    assert body["name"] == "v2 renamed"
    assert body["strategy_json"]["exit"]["targetPercent"] == 5.5
    assert body["strategy_json"]["id"] == "v2_id"


def test_update_unknown_id_returns_404(client: TestClient) -> None:
    resp = client.put(
        f"/api/strategies/{uuid.uuid4()}", json=make_strategy_payload()
    )

    assert resp.status_code == 404


# ─── delete ────────────────────────────────────────────────────────────


def test_delete_removes_row_and_subsequent_get_404s(
    client: TestClient,
    db_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    created = client.post(
        "/api/strategies", json=make_strategy_payload()
    ).json()

    resp = client.delete(f"/api/strategies/{created['id']}")

    assert resp.status_code == 204
    assert client.get(f"/api/strategies/{created['id']}").status_code == 404


def test_delete_unknown_id_returns_404(client: TestClient) -> None:
    resp = client.delete(f"/api/strategies/{uuid.uuid4()}")

    assert resp.status_code == 404


# ─── cross-user isolation ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_user_b_cannot_read_or_mutate_user_a_strategies(
    client: TestClient,
    db_session_maker: async_sessionmaker[AsyncSession],
    seed_user: User,
) -> None:
    """User B sees 404 for every endpoint operating on user A's row.

    The handler returns the same 404 for "not found" and "not owned"
    so cross-user probes can't enumerate which ids exist.
    """
    # User A (= seed_user) creates a strategy.
    created = client.post(
        "/api/strategies", json=make_strategy_payload(name="a-only")
    ).json()
    other_id = created["id"]

    # Spin up user B and re-point the auth override at them.
    user_b = await _seed_user(
        db_session_maker, email="phase5-other@tradetri.com"
    )

    async def _override_user_b() -> User:
        return user_b

    client.app.dependency_overrides[get_current_active_user] = _override_user_b  # type: ignore[attr-defined]

    # B can list — sees nothing.
    list_resp = client.get("/api/strategies")
    assert list_resp.status_code == 200
    assert list_resp.json() == {"strategies": [], "count": 0}

    # B cannot read / update / delete A's strategy.
    assert client.get(f"/api/strategies/{other_id}").status_code == 404
    assert (
        client.put(
            f"/api/strategies/{other_id}", json=make_strategy_payload(name="hijack")
        ).status_code
        == 404
    )
    assert client.delete(f"/api/strategies/{other_id}").status_code == 404

    # And A's row is still intact in the DB.
    async with db_session_maker() as s:
        rows = (await s.execute(select(Strategy))).scalars().all()
        assert len(rows) == 1
        assert rows[0].name == "a-only"
        assert rows[0].user_id == seed_user.id


# ─── DSL round-trip — verify the column actually stores the JSONB ─────


@pytest.mark.asyncio
async def test_strategy_json_is_persisted_as_dict_in_column(
    client: TestClient,
    db_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    """The DB row's ``strategy_json`` column holds the dumped DSL."""
    payload = make_strategy_payload(name="persist-check")
    resp = client.post("/api/strategies", json=payload)
    assert resp.status_code == 201
    strategy_id = uuid.UUID(resp.json()["id"])

    async with db_session_maker() as s:
        row = (
            await s.execute(select(Strategy).where(Strategy.id == strategy_id))
        ).scalar_one()
        assert isinstance(row.strategy_json, dict)
        assert row.strategy_json["name"] == "persist-check"
        assert row.strategy_json["execution"]["orderType"] == "MARKET"
        assert row.strategy_json["exit"]["targetPercent"] == 2.0
