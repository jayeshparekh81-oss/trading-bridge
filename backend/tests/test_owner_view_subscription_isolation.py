"""Owner view must NOT leak marketplace fan-out subscriber (paper) rows.

BUGFIX (feat/marketplace-fanout). The customer-facing read endpoints
``GET /api/strategies/positions`` and ``GET /api/strategies/executions`` did not
filter ``subscription_id``. Subscriber fan-out rows carry a NON-NULL
``subscription_id`` (positions also carry the subscriber's ``user_id``;
executions link to the OWNER's signal), so once ``MARKETPLACE_FANOUT_ENABLED``
flips they would surface in a user's OWN view. The fix scopes both endpoints to
``subscription_id IS NULL`` (owner rows only). These tests prove:

    (a) with subscriber rows present, the owner's view returns ONLY NULL rows;
    (b) with NO subscriber rows, the owner's view is unchanged (every owner row
        still returned — the filter drops nothing).

Display-only / read-path. The internal owner lookups already filter NULL and
are untouched.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import JSONB as _JSONB
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles as _compiles
from sqlalchemy.pool import StaticPool

import app.auth.entitlements as ent
from app.api.deps import get_current_active_user
from app.api.strategy_positions import router as positions_router
from app.api.strategy_signals import router as signals_router
from app.db.base import Base
from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.db.session import get_session


# JSONB → JSON shim so create_all renders on sqlite (mirrors the other tests).
@_compiles(_JSONB, "sqlite")
def _render_jsonb_as_json_on_sqlite(element, compiler, **kw):  # type: ignore[no-untyped-def]
    return compiler.visit_JSON(element, **kw)


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-iso-{uuid.uuid4().hex}"
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


def _client(
    db_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    user: User,
) -> TestClient:
    # Paywall OFF so the (require_active_plan-gated) executions endpoint passes.
    monkeypatch.setattr(ent, "get_settings", lambda: SimpleNamespace(paywall_enforced=False))
    app = FastAPI()
    app.include_router(positions_router)
    app.include_router(signals_router)

    async def _ovr_user() -> User:
        return user

    async def _ovr_session() -> AsyncIterator[AsyncSession]:
        async with db_maker() as s:
            yield s

    app.dependency_overrides[get_current_active_user] = _ovr_user
    app.dependency_overrides[get_session] = _ovr_session
    return TestClient(app)


def _user(uid: uuid.UUID) -> User:
    u = User(email=f"{uid}@x", password_hash="p", is_active=True)
    u.id = uid
    return u


def _position(*, user_id: uuid.UUID, subscription_id: uuid.UUID | None) -> StrategyPosition:
    return StrategyPosition(
        user_id=user_id,
        strategy_id=uuid.uuid4(),
        broker_credential_id=uuid.uuid4(),
        subscription_id=subscription_id,
        symbol="NIFTY",
        side="BUY",
        total_quantity=1,
        remaining_quantity=1,
        status="open",
    )


def _execution(
    *, signal_id: uuid.UUID, subscription_id: uuid.UUID | None
) -> StrategyExecution:
    return StrategyExecution(
        signal_id=signal_id,
        broker_credential_id=uuid.uuid4(),
        subscription_id=subscription_id,
        leg_number=1,
        leg_role="entry",
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        order_type="market",
    )


# ── (a) leak fixed — owner view returns ONLY subscription_id IS NULL rows ──


@pytest.mark.asyncio
async def test_positions_view_excludes_subscriber_rows(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A user with BOTH an owned position (NULL) and a fan-out paper position
    (non-NULL subscription_id, same user_id) sees ONLY the owned one."""
    uid = uuid.uuid4()
    async with db_maker() as s:
        owned = _position(user_id=uid, subscription_id=None)
        s.add(owned)
        s.add(_position(user_id=uid, subscription_id=uuid.uuid4()))  # subscriber paper
        await s.commit()
        owned_id = str(owned.id)

    client = _client(db_maker, monkeypatch, _user(uid))
    resp = client.get("/api/strategies/positions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 1
    assert [p["id"] for p in body["positions"]] == [owned_id]  # subscriber row excluded


@pytest.mark.asyncio
async def test_executions_view_excludes_subscriber_rows(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Subscriber executions link to the OWNER's signal. The owner's view must
    return ONLY its own (NULL) execution, never the subscriber (non-NULL) one."""
    uid = uuid.uuid4()
    async with db_maker() as s:
        sig = StrategySignal(
            user_id=uid, strategy_id=uuid.uuid4(), raw_payload={}, symbol="NIFTY",
            action="BUY",
        )
        s.add(sig)
        await s.flush()
        owner_exec = _execution(signal_id=sig.id, subscription_id=None)
        s.add(owner_exec)
        # subscriber paper exec — SAME owner signal, non-NULL subscription_id.
        s.add(_execution(signal_id=sig.id, subscription_id=uuid.uuid4()))
        await s.commit()
        owner_exec_id = str(owner_exec.id)

    client = _client(db_maker, monkeypatch, _user(uid))
    resp = client.get("/api/strategies/executions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 1
    assert [e["id"] for e in body["executions"]] == [owner_exec_id]  # subscriber excluded


# ── (b) byte-identical when NO subscriber rows exist ──────────────────


@pytest.mark.asyncio
async def test_positions_view_unchanged_without_subscriber_rows(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    """With only owner rows (the world today, flag OFF), every owner position is
    still returned — the NULL filter drops nothing."""
    uid = uuid.uuid4()
    ids: set[str] = set()
    async with db_maker() as s:
        for _ in range(3):
            p = _position(user_id=uid, subscription_id=None)
            s.add(p)
            await s.flush()
            ids.add(str(p.id))
        await s.commit()

    client = _client(db_maker, monkeypatch, _user(uid))
    body = client.get("/api/strategies/positions").json()
    assert body["count"] == 3
    assert {p["id"] for p in body["positions"]} == ids


@pytest.mark.asyncio
async def test_executions_view_unchanged_without_subscriber_rows(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    """With only owner executions, every one is still returned (filter drops none)."""
    uid = uuid.uuid4()
    ids: set[str] = set()
    async with db_maker() as s:
        sig = StrategySignal(
            user_id=uid, strategy_id=uuid.uuid4(), raw_payload={}, symbol="NIFTY",
            action="BUY",
        )
        s.add(sig)
        await s.flush()
        for _ in range(3):
            e = _execution(signal_id=sig.id, subscription_id=None)
            s.add(e)
            await s.flush()
            ids.add(str(e.id))
        await s.commit()

    client = _client(db_maker, monkeypatch, _user(uid))
    body = client.get("/api/strategies/executions").json()
    assert body["count"] == 3
    assert {e["id"] for e in body["executions"]} == ids
