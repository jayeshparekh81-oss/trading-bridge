"""POST /api/orders/live — endpoint tests.

Exercises the FastAPI router via :class:`TestClient` with auth + DB
session deps overridden. Mirrors the
``test_backtest_endpoint`` pattern: each test mounts a fresh
:class:`FastAPI` app holding only the live-orders router, swaps the
``get_session`` and ``get_current_active_user`` deps, and replaces
the production broker factory with a mock by monkey-patching
:func:`app.strategy_engine.live_orders.order_router.place_live_order`'s
factory default.

Each test seeds the SafetyChain prerequisites (paper sessions,
cached scores, broker credential, etc.) by reusing the production
helpers — no direct table inserts where a fixture exists.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import fakeredis.aioredis as fake_aioredis
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
from app.core import redis_client
from app.core.security import encrypt_credential
from app.db.base import Base
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.db.session import get_session
from app.schemas.broker import (
    BrokerCredentials,
    BrokerName,
    OrderRequest,
    OrderResponse,
    OrderStatus,
)
from app.strategy_engine.audit import clear_audit_log
from app.strategy_engine.feature_flags import (
    reset_all_flags,
    set_flag,
)
from app.strategy_engine.feature_flags.constants import ENV_PREFIX
from app.strategy_engine.live_orders import api as live_orders_api
from app.strategy_engine.live_orders import order_router as order_router_module
from app.strategy_engine.paper_trading import store as paper_store

_VALID_DSL: dict[str, Any] = {
    "id": "api_live_test",
    "name": "API live test",
    "mode": "expert",
    "indicators": [],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [{"type": "price", "op": ">", "value": 99.5}],
    },
    "exit": {"targetPercent": 2.0, "stopLossPercent": 1.0},
    "risk": {},
    "execution": {
        "mode": "live",
        "orderType": "MARKET",
        "productType": "INTRADAY",
    },
}


# ─── Fakes + harness ──────────────────────────────────────────────────


class _FakeBroker:
    """Same behaviour-toggle stand-in used by the order_router tests."""

    broker_name = BrokerName.DHAN

    def __init__(self) -> None:
        self.place_calls: list[OrderRequest] = []

    async def login(self) -> bool:
        return True

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        self.place_calls.append(order)
        return OrderResponse(
            broker_order_id=f"FAKE-API-{len(self.place_calls)}",
            status=OrderStatus.COMPLETE,
            message="placed",
            raw_response={"echo": order.symbol},
        )


@pytest.fixture(autouse=True)
def _isolated_state(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Drop env overrides + audit log + runtime flag map per test."""
    import os

    for name, _ in list(os.environ.items()):
        if name.startswith(ENV_PREFIX):
            monkeypatch.delenv(name, raising=False)
    reset_all_flags()
    clear_audit_log()
    yield
    reset_all_flags()
    clear_audit_log()


@pytest_asyncio.fixture
async def redis_(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[fake_aioredis.FakeRedis]:
    client = fake_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: client)
    try:
        yield client
    finally:
        await client.aclose()


@pytest_asyncio.fixture
async def db_maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Per-test in-memory aiosqlite engine, single shared connection."""
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:tradetri-live-api-{uuid.uuid4().hex}"
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


async def _seed_user(
    maker: async_sessionmaker[AsyncSession],
    *,
    email: str,
    live_trading_enabled: bool = True,
) -> User:
    async with maker() as s:
        u = User(
            email=email,
            password_hash="p",
            is_active=True,
            live_trading_enabled=live_trading_enabled,
        )
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def _seed_full_setup(
    maker: async_sessionmaker[AsyncSession],
    user: User,
    *,
    with_dsl: bool = True,
    with_broker_fk: bool = True,
) -> Strategy:
    """Insert a strategy + 7 paper sessions + cached fresh scores +
    optional broker credential + FK link. Mirrors
    ``conftest.all_passing`` but for the API harness's own session."""
    async with maker() as s:
        strat = Strategy(
            user_id=user.id,
            name="api-live",
            is_active=True,
            strategy_json=_VALID_DSL.copy() if with_dsl else None,
        )
        s.add(strat)
        await s.flush()

        base = date(2026, 5, 1)
        for i in range(7):
            row = await paper_store.create_session(
                s,
                user_id=user.id,
                strategy_id=strat.id,
                engine_strategy_id="eng",
                session_date=base + timedelta(days=i),
            )
            await paper_store.complete_session(
                s,
                session_id=row.id,
                total_trades=1,
                total_pnl=Decimal("10"),
            )
        strat.last_trust_score = Decimal("80.00")
        strat.last_truth_score = Decimal("70.00")
        strat.last_scores_at = datetime.now(UTC) - timedelta(hours=1)

        if with_broker_fk:
            cred = BrokerCredential(
                user_id=user.id,
                broker_name=BrokerName.DHAN,
                client_id_enc=encrypt_credential("CID"),
                api_key_enc=encrypt_credential("KEY"),
                api_secret_enc=encrypt_credential("SEC"),
                access_token_enc=encrypt_credential("TOK"),
                token_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
                is_active=True,
            )
            s.add(cred)
            await s.flush()
            strat.broker_credential_id = cred.id

        await s.commit()
        await s.refresh(strat)
        return strat


@pytest.fixture
def make_client(
    db_maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[User, _FakeBroker], TestClient]:
    """Builder that returns a TestClient impersonating ``user`` and
    routing the orchestrator's broker_factory through ``broker``."""

    def _build(user: User, broker: _FakeBroker) -> TestClient:
        # The endpoint calls place_live_order without passing a
        # broker_factory; monkey-patch the orchestrator to inject our
        # fake at every call.
        original = order_router_module.place_live_order

        async def _patched_place(
            request: Any,
            *,
            user_id: uuid.UUID,
            db_session: AsyncSession,
            broker_factory: Any = None,
        ) -> Any:
            def _factory(_creds: BrokerCredentials) -> _FakeBroker:
                return broker

            return await original(
                request,
                user_id=user_id,
                db_session=db_session,
                broker_factory=_factory,
            )

        monkeypatch.setattr(
            live_orders_api, "place_live_order", _patched_place
        )

        app = FastAPI()
        app.include_router(live_orders_api.router)

        async def _override_session() -> AsyncIterator[AsyncSession]:
            async with db_maker() as session:
                try:
                    yield session
                except Exception:
                    await session.rollback()
                    raise

        async def _override_user() -> User:
            return user

        app.dependency_overrides[get_session] = _override_session
        app.dependency_overrides[get_current_active_user] = _override_user
        return TestClient(app)

    return _build


# ─── 1. Happy path ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_live_returns_200_with_order_id_when_all_pass(
    db_maker: async_sessionmaker[AsyncSession],
    redis_: fake_aioredis.FakeRedis,
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    user = await _seed_user(db_maker, email="api-happy@x")
    strategy = await _seed_full_setup(db_maker, user)
    set_flag("LIVE_TRADING_ENABLED", True)

    broker = _FakeBroker()
    with make_client(user, broker) as client:
        resp = client.post(
            "/api/orders/live",
            json={
                "strategy_id": str(strategy.id),
                "symbol": "NIFTY25JANFUT",
                "side": "BUY",
                "quantity": 1,
                "exchange": "NFO",
                "product_type": "INTRADAY",
            },
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["order_id"] == "FAKE-API-1"
    assert body["is_dry_run"] is False
    assert body["broker_guard_passed"] is True
    assert len(broker.place_calls) == 1


# ─── 2. SafetyChain block → 403 ──────────────────────────────────────


@pytest.mark.asyncio
async def test_post_live_returns_403_when_safety_chain_blocks(
    db_maker: async_sessionmaker[AsyncSession],
    redis_: fake_aioredis.FakeRedis,
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    """No paper sessions seeded — chain stops at check #2."""
    user = await _seed_user(db_maker, email="api-block@x")
    async with db_maker() as s:
        strat = Strategy(
            user_id=user.id, name="empty", is_active=True
        )
        s.add(strat)
        await s.commit()
        await s.refresh(strat)

    broker = _FakeBroker()
    with make_client(user, broker) as client:
        resp = client.post(
            "/api/orders/live",
            json={
                "strategy_id": str(strat.id),
                "symbol": "NIFTY25JANFUT",
                "side": "BUY",
                "quantity": 1,
            },
        )

    assert resp.status_code == 403
    body = resp.json()
    detail = body["detail"]
    # Detail carries the full LiveOrderResult shape.
    assert detail["success"] is False
    assert (
        detail["safety_chain_result"]["blocking_check"]["check_name"]
        == "paper_sessions"
    )
    assert "Sirf 0/7" in detail["failure_reason_hinglish"]
    assert broker.place_calls == []


# ─── 3. Dry-run → 200 with simulated id ──────────────────────────────


@pytest.mark.asyncio
async def test_post_live_dry_run_returns_simulated_id_no_broker_call(
    db_maker: async_sessionmaker[AsyncSession],
    redis_: fake_aioredis.FakeRedis,
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    user = await _seed_user(db_maker, email="api-dryrun@x")
    strategy = await _seed_full_setup(db_maker, user)
    set_flag("LIVE_TRADING_ENABLED", True)

    broker = _FakeBroker()
    with make_client(user, broker) as client:
        resp = client.post(
            "/api/orders/live",
            json={
                "strategy_id": str(strategy.id),
                "symbol": "NIFTY25JANFUT",
                "side": "BUY",
                "quantity": 1,
                "dry_run": True,
            },
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["is_dry_run"] is True
    assert body["order_id"] == "DRY_RUN_SIMULATED"
    # No broker call.
    assert broker.place_calls == []


# ─── 4. Cross-user enumeration → 404 ─────────────────────────────────


@pytest.mark.asyncio
async def test_post_live_cross_user_strategy_returns_404(
    db_maker: async_sessionmaker[AsyncSession],
    redis_: fake_aioredis.FakeRedis,
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    owner = await _seed_user(db_maker, email="owner@x")
    intruder = await _seed_user(db_maker, email="intruder@x")
    owner_strategy = await _seed_full_setup(db_maker, owner)
    set_flag("LIVE_TRADING_ENABLED", True)

    broker = _FakeBroker()
    with make_client(intruder, broker) as client:
        resp = client.post(
            "/api/orders/live",
            json={
                "strategy_id": str(owner_strategy.id),
                "symbol": "NIFTY25JANFUT",
                "side": "BUY",
                "quantity": 1,
            },
        )

    assert resp.status_code == 404
    assert broker.place_calls == []


# ─── 5. Auth required → 401 ──────────────────────────────────────────


def test_post_live_requires_authentication() -> None:
    """No auth dep override → ``get_current_active_user`` raises 401
    before any DB lookup happens. No DB plumbing needed."""
    app = FastAPI()
    app.include_router(live_orders_api.router)
    with TestClient(app) as client:
        resp = client.post(
            "/api/orders/live",
            json={
                "strategy_id": str(uuid.uuid4()),
                "symbol": "NIFTY25JANFUT",
                "side": "BUY",
                "quantity": 1,
            },
        )
    assert resp.status_code == 401


# ─── 6. Validation errors → 422 ──────────────────────────────────────


@pytest.mark.asyncio
async def test_post_live_zero_quantity_returns_422(
    db_maker: async_sessionmaker[AsyncSession],
    redis_: fake_aioredis.FakeRedis,
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    user = await _seed_user(db_maker, email="qty-zero@x")
    broker = _FakeBroker()
    with make_client(user, broker) as client:
        resp = client.post(
            "/api/orders/live",
            json={
                "strategy_id": str(uuid.uuid4()),
                "symbol": "NIFTY25JANFUT",
                "side": "BUY",
                "quantity": 0,
            },
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_live_negative_quantity_returns_422(
    db_maker: async_sessionmaker[AsyncSession],
    redis_: fake_aioredis.FakeRedis,
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    user = await _seed_user(db_maker, email="qty-neg@x")
    broker = _FakeBroker()
    with make_client(user, broker) as client:
        resp = client.post(
            "/api/orders/live",
            json={
                "strategy_id": str(uuid.uuid4()),
                "symbol": "NIFTY25JANFUT",
                "side": "BUY",
                "quantity": -5,
            },
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_live_invalid_side_returns_422(
    db_maker: async_sessionmaker[AsyncSession],
    redis_: fake_aioredis.FakeRedis,
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    user = await _seed_user(db_maker, email="bad-side@x")
    broker = _FakeBroker()
    with make_client(user, broker) as client:
        resp = client.post(
            "/api/orders/live",
            json={
                "strategy_id": str(uuid.uuid4()),
                "symbol": "NIFTY25JANFUT",
                "side": "MAYBE",
                "quantity": 1,
            },
        )
    assert resp.status_code == 422


# ─── 7. Strategy without broker FK → 422 ─────────────────────────────


@pytest.mark.asyncio
async def test_post_live_strategy_without_broker_fk_returns_422(
    db_maker: async_sessionmaker[AsyncSession],
    redis_: fake_aioredis.FakeRedis,
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    """All SafetyChain checks pass (1+ active credential exists for
    the user) but the strategy itself has no FK — surfaces as 422."""
    user = await _seed_user(db_maker, email="no-fk@x")
    # Seed full setup but null out the FK after.
    strategy = await _seed_full_setup(db_maker, user, with_broker_fk=True)
    async with db_maker() as s:
        row = await s.get(Strategy, strategy.id)
        assert row is not None
        row.broker_credential_id = None
        await s.commit()
    set_flag("LIVE_TRADING_ENABLED", True)

    broker = _FakeBroker()
    with make_client(user, broker) as client:
        resp = client.post(
            "/api/orders/live",
            json={
                "strategy_id": str(strategy.id),
                "symbol": "NIFTY25JANFUT",
                "side": "BUY",
                "quantity": 1,
            },
        )
    assert resp.status_code == 422
    assert broker.place_calls == []


# ─── 8. GET /api/orders/live/preflight ────────────────────────────────


@pytest.mark.asyncio
async def test_preflight_returns_all_checks_when_safety_passes(
    db_maker: async_sessionmaker[AsyncSession],
    redis_: fake_aioredis.FakeRedis,
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    """All seven checks pass → 200 with ``all_passed=True`` and the
    full check list. No broker call, no audit emission."""
    user = await _seed_user(db_maker, email="preflight-pass@x")
    strategy = await _seed_full_setup(db_maker, user)
    set_flag("LIVE_TRADING_ENABLED", True)

    broker = _FakeBroker()
    with make_client(user, broker) as client:
        resp = client.get(
            "/api/orders/live/preflight",
            params={"strategy_id": str(strategy.id)},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["all_passed"] is True
    assert body["blocking_check"] is None
    assert len(body["checks"]) == 7
    # Locked check order — same assertion as the SafetyChain happy-path
    # test, but exercised through the HTTP layer.
    assert [c["check_name"] for c in body["checks"]] == [
        "auto_kill_switch",
        "paper_sessions",
        "trust_score",
        "truth_score",
        "live_trading_enabled",
        "broker_connection",
        "risk_engine_precheck",
    ]
    # No broker call should ever happen on the preflight surface.
    assert broker.place_calls == []


@pytest.mark.asyncio
async def test_preflight_returns_blocking_check_when_safety_fails(
    db_maker: async_sessionmaker[AsyncSession],
    redis_: fake_aioredis.FakeRedis,
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    """Empty strategy → chain stops at paper_sessions; the response
    is still 200 (the block is the *expected* output of preflight,
    not an HTTP error)."""
    user = await _seed_user(db_maker, email="preflight-block@x")
    async with db_maker() as s:
        strat = Strategy(user_id=user.id, name="empty", is_active=True)
        s.add(strat)
        await s.commit()
        await s.refresh(strat)

    broker = _FakeBroker()
    with make_client(user, broker) as client:
        resp = client.get(
            "/api/orders/live/preflight",
            params={"strategy_id": str(strat.id)},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["all_passed"] is False
    assert body["blocking_check"]["check_name"] == "paper_sessions"
    assert "Sirf 0/7" in body["blocking_check"]["reason_hinglish"]
    # Fail-fast: only the first two checks should have executed.
    assert len(body["checks"]) == 2
    assert broker.place_calls == []


@pytest.mark.asyncio
async def test_preflight_cross_user_strategy_returns_404(
    db_maker: async_sessionmaker[AsyncSession],
    redis_: fake_aioredis.FakeRedis,
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    owner = await _seed_user(db_maker, email="preflight-owner@x")
    intruder = await _seed_user(db_maker, email="preflight-intruder@x")
    owner_strategy = await _seed_full_setup(db_maker, owner)

    broker = _FakeBroker()
    with make_client(intruder, broker) as client:
        resp = client.get(
            "/api/orders/live/preflight",
            params={"strategy_id": str(owner_strategy.id)},
        )
    assert resp.status_code == 404


def test_preflight_requires_authentication() -> None:
    """Without auth override the dep raises 401 before any DB lookup."""
    app = FastAPI()
    app.include_router(live_orders_api.router)
    with TestClient(app) as client:
        resp = client.get(
            "/api/orders/live/preflight",
            params={"strategy_id": str(uuid.uuid4())},
        )
    assert resp.status_code == 401


# ─── Paper-mode gate (safety fix #3) ─────────────────────────────────


@pytest.mark.asyncio
async def test_place_live_order_403_in_paper_mode(
    db_maker: async_sessionmaker[AsyncSession],
    redis_: fake_aioredis.FakeRedis,
    make_client: Callable[[User, _FakeBroker], TestClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``POST /api/orders/live`` must return 403 with the Hinglish
    paper-mode message when ``strategy_paper_mode=True``. The
    SafetyChain seed is fully passing on purpose — the gate must fire
    before any chain evaluation. Broker must NOT be touched."""
    from app.core.config import get_settings

    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    get_settings.cache_clear()

    user = await _seed_user(db_maker, email="api-paper-gate@x")
    strategy = await _seed_full_setup(db_maker, user)
    set_flag("LIVE_TRADING_ENABLED", True)

    broker = _FakeBroker()
    with make_client(user, broker) as client:
        resp = client.post(
            "/api/orders/live",
            json={
                "strategy_id": str(strategy.id),
                "symbol": "NIFTY25JANFUT",
                "side": "BUY",
                "quantity": 1,
                "exchange": "NFO",
                "product_type": "INTRADAY",
            },
        )

    assert resp.status_code == 403, resp.text
    body = resp.json()
    assert "paper mode" in body["detail"].lower()
    assert "July 2026" in body["detail"]
    # Broker must never have been touched.
    assert broker.place_calls == []


@pytest.mark.asyncio
async def test_place_live_order_works_in_live_mode_regression(
    db_maker: async_sessionmaker[AsyncSession],
    redis_: fake_aioredis.FakeRedis,
    make_client: Callable[[User, _FakeBroker], TestClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression guard: with ``STRATEGY_PAPER_MODE=false`` the live
    path is unchanged — 200 + ``order_id`` + broker hit exactly once."""
    from app.core.config import get_settings

    monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
    get_settings.cache_clear()

    user = await _seed_user(db_maker, email="api-live-regression@x")
    strategy = await _seed_full_setup(db_maker, user)
    set_flag("LIVE_TRADING_ENABLED", True)

    broker = _FakeBroker()
    with make_client(user, broker) as client:
        resp = client.post(
            "/api/orders/live",
            json={
                "strategy_id": str(strategy.id),
                "symbol": "NIFTY25JANFUT",
                "side": "BUY",
                "quantity": 1,
                "exchange": "NFO",
                "product_type": "INTRADAY",
            },
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["order_id"] == "FAKE-API-1"
    assert len(broker.place_calls) == 1
