"""Phase 2 Billing B3.2 — premium-endpoint gating.

Locks the contract for the 5 endpoints gated with ``require_active_plan``:

    GET /api/users/me/trades                              (analytics list)
    GET /api/users/me/trades/export                       (trade CSV export)
    GET /api/strategies/executions                        (trade history)
    GET /api/marketplace/listings/{id}/ledger             (ledger view)
    GET /api/marketplace/listings/{id}/ledger/history     (ledger history)

Guarantees:
    * Flag OFF ⇒ behavior-neutral (every status passes).
    * Flag ON ⇒ active+non-expired passes; none/expired/cancelled → 402.
    * **Lockout-guard**: the free siblings in the SAME touched routers stay
      ungated for a ``none`` user under flag ON+OFF — explicitly
      ``/me/trades/stats`` (the global AlgoMitra 60s poll, B3.2 audit finding)
      and ``/ledger/verify``.

Gate-open ledger requests hit an unseeded listing → 404; a 404 (not 402)
proves the paywall let the request through. Seeding a full listing (Strategy
+ User FK chain) would test marketplace internals, not the gate, so we assert
on the 402-vs-not-402 boundary that B3.2 actually changes.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
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
from app.api.strategy_signals import router as signals_router
from app.api.users import router as users_router
from app.db.base import Base
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api.marketplace_ledger import router as ledger_router


# JSONB → JSON shim so ``Base.metadata.create_all`` renders on the sqlite
# test engine (some models, e.g. strategy_templates, use Postgres JSONB).
# Mirrors tests/integration/conftest.py; production keeps real jsonb.
@_compiles(_JSONB, "sqlite")
def _render_jsonb_as_json_on_sqlite(element, compiler, **kw):  # type: ignore[no-untyped-def]
    return compiler.visit_JSON(element, **kw)


_FUTURE = datetime(2099, 1, 1, tzinfo=UTC)
_LID = "11111111-1111-1111-1111-111111111111"  # arbitrary (unseeded) listing id

# The 5 gated endpoints.
GATED = [
    "/api/users/me/trades",
    "/api/users/me/trades/export",
    "/api/strategies/executions",
    f"/api/marketplace/listings/{_LID}/ledger",
    f"/api/marketplace/listings/{_LID}/ledger/history",
]
# Gate-open ⇒ these reach an empty-data handler and return 200 (no seeding).
PASSES_200_WHEN_OPEN = {"/api/users/me/trades", "/api/strategies/executions"}

# Free siblings in the touched routers that MUST stay ungated.
STATS = "/api/users/me/trades/stats"
LEDGER_VERIFY = f"/api/marketplace/listings/{_LID}/ledger/verify"


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-gate-{uuid.uuid4().hex}"
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
    *,
    plan_status: str,
    flag_on: bool,
) -> TestClient:
    """App mounting the 3 touched routers, impersonating a user with the
    given plan_status, with PAYWALL_ENFORCED set to flag_on."""
    monkeypatch.setattr(ent, "get_settings", lambda: SimpleNamespace(paywall_enforced=flag_on))
    app = FastAPI()
    app.include_router(users_router)
    app.include_router(signals_router)
    app.include_router(ledger_router)

    user = User(
        email="u@x",
        password_hash="p",
        is_active=True,
        plan_status=plan_status,
        plan_expires_at=_FUTURE if plan_status == "active" else None,
    )
    user.id = uuid.uuid4()

    async def _ovr_user() -> User:
        return user

    async def _ovr_session() -> AsyncIterator[AsyncSession]:
        async with db_maker() as s:
            yield s

    app.dependency_overrides[get_current_active_user] = _ovr_user
    app.dependency_overrides[get_session] = _ovr_session
    return TestClient(app)


# ── 1. Flag ON + none ⇒ 402 PLAN_REQUIRED on all 4 gated ──────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("path", GATED)
async def test_gated_402_for_none_when_flag_on(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    client = _client(db_maker, monkeypatch, plan_status="none", flag_on=True)
    resp = client.get(path)
    assert resp.status_code == 402, (path, resp.text)
    assert resp.json()["detail"]["code"] == "PLAN_REQUIRED"


# ── 2. Flag ON + active ⇒ passes (gate open) ──────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("path", GATED)
async def test_gated_passes_for_active_when_flag_on(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    client = _client(db_maker, monkeypatch, plan_status="active", flag_on=True)
    resp = client.get(path)
    assert resp.status_code != 402, (path, resp.text)
    if path in PASSES_200_WHEN_OPEN:
        assert resp.status_code == 200, (path, resp.text)


# ── 3. Flag OFF + none ⇒ passes (behavior-neutral) ────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("path", GATED)
async def test_gated_passes_for_none_when_flag_off(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    client = _client(db_maker, monkeypatch, plan_status="none", flag_on=False)
    resp = client.get(path)
    assert resp.status_code != 402, (path, resp.text)
    if path in PASSES_200_WHEN_OPEN:
        assert resp.status_code == 200, (path, resp.text)


# ── 4. Lockout-guard: free siblings stay ungated (flag ON + OFF) ──────


@pytest.mark.asyncio
@pytest.mark.parametrize("flag_on", [True, False])
async def test_free_siblings_never_gated_for_none(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch, flag_on: bool
) -> None:
    client = _client(db_maker, monkeypatch, plan_status="none", flag_on=flag_on)
    # /me/trades/stats — global AlgoMitra poll + stats teaser → must be 200.
    assert client.get(STATS).status_code == 200
    # ledger/verify stays free (404 = listing unseeded, NOT a paywall block).
    assert client.get(LEDGER_VERIFY).status_code != 402


# ── 5. EXPLICIT AlgoMitra regression guard (B3.2 audit finding) ───────


@pytest.mark.asyncio
async def test_me_trades_stats_stays_200_for_none_with_flag_on(
    db_maker: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``/me/trades/stats`` feeds the global AlgoMitraReactionLayer (polled
    every 60s on every dashboard page incl. free ones). It must NEVER be
    gated — else a free user gets a 402 every 60s platform-wide. Locks the
    B3.2 audit finding as a regression test."""
    client = _client(db_maker, monkeypatch, plan_status="none", flag_on=True)
    assert client.get(STATS).status_code == 200
