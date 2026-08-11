"""End-to-end integration tests for the live-orders flow.

Drives the full HTTP stack against an in-memory aiosqlite DB +
fakeredis Redis + fake-broker injection:

    POST /api/strategies/{id}/backtest   →  scores cached on row
    GET  /api/orders/live/preflight       →  SafetyChainResult
    POST /api/orders/live                 →  LiveOrderResult
                                           +  audit-log emissions

Reuses ``tests/integration/conftest.py``'s ``db_session_maker``,
``fake_redis``, and ``seed`` fixtures. The conftest's stock ``client``
fixture mounts the full ``create_app()`` but does not override the
JWT auth dep — this file installs that override (and the broker-
factory monkey-patch) on its own client builder so each test can
swap the broker behaviour independently.

Scenarios (13):

    1.  Happy path — all 7 checks pass + broker accepts.
    2.  Dry-run full flow — same setup, ``dry_run=true``, broker not called.
    3.  Block: paper_sessions < 7.
    4.  Block: trust_score < 70.
    5.  Block: stale scores (>24h old).
    6.  Block: live_trading_enabled flag off.
    7.  Block: auto_kill_switch tripped.
    8.  Broker offline — generic ``BrokerConnectionError`` → 503.
    9.  Session expired → relogin → succeeds.
    10. Session expired → relogin fails → 503.
    11. Cross-user enumeration → 404.
    12. Sequential 5-order burst — all succeed.
    13. Preflight refresh flow — block then unblock then place.

Mocks all Dhan calls. No real network.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis as fake_aioredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_current_active_user
from app.core import redis_client
from app.core.exceptions import (
    BrokerAuthError,
    BrokerConnectionError,
    BrokerSessionExpiredError,
)
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.db.session import get_session
from app.main import create_app
from app.schemas.broker import (
    BrokerCredentials,
    BrokerName,
    OrderRequest,
    OrderResponse,
    OrderStatus,
)
from app.strategy_engine.audit import clear_audit_log, query_events
from app.strategy_engine.feature_flags import reset_all_flags, set_flag
from app.strategy_engine.feature_flags.constants import ENV_PREFIX
from app.strategy_engine.live_orders import api as live_orders_api
from app.strategy_engine.live_orders import order_router as order_router_module
from app.strategy_engine.live_orders.order_router import BrokerFactory
from app.strategy_engine.paper_trading import store as paper_store
from tests.integration.conftest import _seed_user_with_strategy

# ─── Fake broker + helpers ────────────────────────────────────────────


class _FakeBroker:
    """Mock :class:`DhanBroker`.

    Behaviour toggles mirror :mod:`tests.strategy_engine.live_orders.test_order_router`
    so the integration suite and the unit suite assert against identical
    fakes.
    """

    broker_name = BrokerName.DHAN

    def __init__(
        self,
        *,
        raise_on_first_place: BaseException | None = None,
        raise_on_relogin: BaseException | None = None,
        always_raise: BaseException | None = None,
    ) -> None:
        self.place_calls: list[OrderRequest] = []
        self.login_calls = 0
        self._raise_on_first_place = raise_on_first_place
        self._raise_on_relogin = raise_on_relogin
        self._always_raise = always_raise

    async def login(self) -> bool:
        self.login_calls += 1
        if self._raise_on_relogin is not None:
            raise self._raise_on_relogin
        return True

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        self.place_calls.append(order)
        if self._always_raise is not None:
            raise self._always_raise
        if self._raise_on_first_place is not None and len(self.place_calls) == 1:
            raise self._raise_on_first_place
        return OrderResponse(
            broker_order_id=f"BROKER-INT-{len(self.place_calls)}",
            status=OrderStatus.COMPLETE,
            message="placed",
            raw_response={"echo": order.symbol},
        )


_VALID_DSL: dict[str, Any] = {
    "id": "live_int_e2e",
    "name": "Integration live e2e",
    "mode": "expert",
    "indicators": [
        {"id": "ema_5", "type": "ema", "params": {"period": 5}},
    ],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [
            {"type": "indicator", "left": "ema_5", "op": ">", "value": 95.0},
        ],
    },
    # Stop loss MUST be present — broker_guard subset check rejects
    # otherwise.
    "exit": {"targetPercent": 1.5, "stopLossPercent": 1.0},
    "risk": {},
    "execution": {
        "mode": "live",
        "orderType": "MARKET",
        "productType": "INTRADAY",
    },
}


# ─── Per-test isolation ──────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolated_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
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


# ─── Client builder — auth override + broker injection ───────────────


@pytest.fixture
def make_client(
    monkeypatch: pytest.MonkeyPatch,
    db_session_maker: async_sessionmaker[AsyncSession],
    fake_redis: fake_aioredis.FakeRedis,
) -> Callable[[User, _FakeBroker], TestClient]:
    """Build a TestClient impersonating ``user`` with ``broker`` injected.

    Patches the live-orders endpoint module to wrap its
    :func:`place_live_order` call with the supplied broker factory —
    same trick the unit suite uses, but here against the full app
    so every router (CRUD, backtest, kill-switch, live-orders) is
    available end-to-end.

    Boots ``app.main.create_app()`` with the conftest's standard
    monkey-patches (fake redis, sqlite session, position/recon loops
    disabled) plus our auth override.
    """

    def _build(user: User, broker: _FakeBroker) -> TestClient:
        # Wrap the orchestrator call so the endpoint uses our fake.
        original = order_router_module.place_live_order

        async def _patched_place(
            request: Any,
            *,
            user_id: uuid.UUID,
            db_session: AsyncSession,
            broker_factory: Any = None,
        ) -> Any:
            def _factory(_creds: BrokerCredentials) -> Any:
                return broker

            return await original(
                request,
                user_id=user_id,
                db_session=db_session,
                broker_factory=cast(BrokerFactory, _factory),
            )

        monkeypatch.setattr(
            live_orders_api, "place_live_order", _patched_place
        )

        # Standard conftest stack — fake redis, sqlite session, loops
        # disabled. Reused so the integration test behaves like the
        # rest of the suite.
        #
        # ``STRATEGY_PAPER_MODE`` is forced OFF here (the only sibling
        # in the integration suite that does so). The live-orders
        # endpoint added a hard-refusal in paper mode on 2026-05-15
        # (order_router.py:168 — "System paper mode mein hai") to stop
        # frontend curl-bypass; this test file is specifically
        # exercising the LIVE path, so paper mode would short-circuit
        # every scenario at 403 before the SafetyChain or broker is
        # ever touched. Defence-in-depth still works because the
        # ``_FakeBroker`` injected above is the only object the
        # endpoint can reach — there is no real-broker code path
        # available even with the env flag off.
        monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
        from app.core import config as _config

        _config.get_settings.cache_clear()

        async def _noop_close() -> None:
            return None

        monkeypatch.setattr(
            "app.core.redis_client.get_redis", lambda: fake_redis
        )
        monkeypatch.setattr(
            "app.core.redis_client.close_redis", _noop_close
        )
        monkeypatch.setattr(
            "redis.asyncio.from_url", lambda *a, **kw: fake_redis
        )

        class _FakeEngine:
            async def dispose(self) -> None:
                return None

            def connect(self) -> Any:
                from contextlib import asynccontextmanager

                @asynccontextmanager
                async def _ctx() -> Any:
                    conn = MagicMock()
                    conn.execute = AsyncMock(return_value=MagicMock())
                    yield conn

                return _ctx()

        monkeypatch.setattr(
            "app.db.session.get_engine", lambda: _FakeEngine()
        )
        monkeypatch.setattr(
            "app.db.session.dispose_engine", AsyncMock(return_value=None)
        )
        monkeypatch.setattr(
            "app.db.session.get_sessionmaker", lambda: db_session_maker
        )
        monkeypatch.setattr(
            "app.workers.position_loop.start_position_loop",
            lambda _app: None,
        )
        monkeypatch.setattr(
            "app.workers.position_loop.stop_position_loop",
            AsyncMock(return_value=None),
        )
        monkeypatch.setattr(
            "app.workers.reconciliation_loop.start_reconciliation_loop",
            lambda _app: None,
        )
        monkeypatch.setattr(
            "app.workers.reconciliation_loop.stop_reconciliation_loop",
            AsyncMock(return_value=None),
        )

        app = create_app()

        async def _override_session() -> AsyncIterator[AsyncSession]:
            async with db_session_maker() as session:
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


# ─── Setup helper ────────────────────────────────────────────────────


async def _enrich_for_live_orders(
    maker: async_sessionmaker[AsyncSession],
    *,
    user_id: uuid.UUID,
    strategy_id: uuid.UUID,
    paper_session_count: int = 7,
    trust_score: float = 85.0,
    truth_score: float = 70.0,
    scores_age_hours: int = 1,
    user_live_trading_enabled: bool = True,
    include_dsl: bool = True,
) -> None:
    """Add the rows the live-orders SafetyChain demands on top of the
    conftest's ``seed`` (which gives us user + creds + strategy + webhook).

    Every knob is independently controllable so individual scenarios
    can break exactly one thing — paper sessions, stale scores,
    per-user flag, etc.
    """
    async with maker() as s:
        strat = await s.get(Strategy, strategy_id)
        assert strat is not None
        if include_dsl:
            strat.strategy_json = _VALID_DSL.copy()
        strat.last_trust_score = trust_score
        strat.last_truth_score = truth_score
        strat.last_scores_at = (
            datetime.now(UTC) - timedelta(hours=scores_age_hours)
        )

        u = await s.get(User, user_id)
        assert u is not None
        u.live_trading_enabled = user_live_trading_enabled

        base = date(2026, 5, 1)
        for i in range(paper_session_count):
            row = await paper_store.create_session(
                s,
                user_id=user_id,
                strategy_id=strategy_id,
                engine_strategy_id="eng",
                session_date=base + timedelta(days=i),
            )
            await paper_store.complete_session(
                s,
                session_id=row.id,
                total_trades=1,
                total_pnl=Decimal("10"),
            )
        await s.commit()


async def _load_user(
    maker: async_sessionmaker[AsyncSession], user_id: uuid.UUID
) -> User:
    async with maker() as s:
        u = await s.get(User, user_id)
        assert u is not None
        return u


def _request_body(strategy_id: uuid.UUID, *, dry_run: bool = False) -> dict[str, Any]:
    return {
        "strategy_id": str(strategy_id),
        "symbol": "NIFTY25JANFUT",
        "side": "BUY",
        "quantity": 1,
        "exchange": "NFO",
        "product_type": "INTRADAY",
        "dry_run": dry_run,
    }


# ─── Scenarios ───────────────────────────────────────────────────────


# 1. Happy path ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_happy_path_all_checks_pass_order_placed(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    """Full flow: seeded scores fresh, all 7 checks pass, broker accepts.

    The score-writeback path is exercised separately by the backtest
    endpoint test (`test_backtest_caches_trust_and_truth_scores_on_strategy_row`).
    Here we seed scores directly so the integration assertion is
    deterministic (synthetic backtest output is not value-stable).
    """
    await _enrich_for_live_orders(
        db_session_maker,
        user_id=seed["user_id"],
        strategy_id=seed["strategy_id"],
    )
    set_flag("LIVE_TRADING_ENABLED", True)
    user = await _load_user(db_session_maker, seed["user_id"])
    broker = _FakeBroker()

    with make_client(user, broker) as client:
        preflight = client.get(
            "/api/orders/live/preflight",
            params={"strategy_id": str(seed["strategy_id"])},
        )
        assert preflight.status_code == 200
        assert preflight.json()["all_passed"] is True

        place = client.post(
            "/api/orders/live",
            json=_request_body(seed["strategy_id"]),
        )

    assert place.status_code == 200, place.text
    body = place.json()
    assert body["success"] is True
    assert body["order_id"] == "BROKER-INT-1"
    assert body["broker_guard_passed"] is True
    assert body["is_dry_run"] is False
    assert len(broker.place_calls) == 1

    # PRE + POST = two live_order_attempted events.
    attempts = query_events(
        user_id=seed["user_id"],
        strategy_id=seed["strategy_id"],
        event_type="live_order_attempted",
    )
    assert attempts.filtered_count == 2


# 2. Dry-run full flow ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dry_run_full_flow_skips_broker_call(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    await _enrich_for_live_orders(
        db_session_maker,
        user_id=seed["user_id"],
        strategy_id=seed["strategy_id"],
    )
    set_flag("LIVE_TRADING_ENABLED", True)
    user = await _load_user(db_session_maker, seed["user_id"])
    broker = _FakeBroker()

    with make_client(user, broker) as client:
        place = client.post(
            "/api/orders/live",
            json=_request_body(seed["strategy_id"], dry_run=True),
        )

    assert place.status_code == 200, place.text
    body = place.json()
    assert body["success"] is True
    assert body["order_id"] == "DRY_RUN_SIMULATED"
    assert body["is_dry_run"] is True
    # No broker call.
    assert broker.place_calls == []
    # PRE only — the absence of a POST is the dry-run audit signal.
    attempts = query_events(
        user_id=seed["user_id"],
        strategy_id=seed["strategy_id"],
        event_type="live_order_attempted",
    )
    assert attempts.filtered_count == 1


# 3. Block — paper sessions < 7 ────────────────────────────────────────


@pytest.mark.asyncio
async def test_paper_sessions_below_seven_blocks_with_403(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    await _enrich_for_live_orders(
        db_session_maker,
        user_id=seed["user_id"],
        strategy_id=seed["strategy_id"],
        paper_session_count=3,
    )
    set_flag("LIVE_TRADING_ENABLED", True)
    user = await _load_user(db_session_maker, seed["user_id"])
    broker = _FakeBroker()

    with make_client(user, broker) as client:
        place = client.post(
            "/api/orders/live",
            json=_request_body(seed["strategy_id"]),
        )

    assert place.status_code == 403
    detail = place.json()["detail"]
    assert detail["safety_chain_result"]["blocking_check"]["check_name"] == "paper_sessions"
    assert "Sirf 3/7" in detail["failure_reason_hinglish"]
    assert "4 aur" in detail["failure_reason_hinglish"]
    assert broker.place_calls == []
    # Block emits one critical-severity event.
    blocked = query_events(
        user_id=seed["user_id"],
        strategy_id=seed["strategy_id"],
        event_type="live_order_blocked",
    )
    assert blocked.filtered_count == 1
    assert blocked.events[0].severity == "critical"


# 4. Block — low trust score ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_trust_score_below_threshold_blocks_with_score_in_message(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    await _enrich_for_live_orders(
        db_session_maker,
        user_id=seed["user_id"],
        strategy_id=seed["strategy_id"],
        trust_score=45.0,
    )
    set_flag("LIVE_TRADING_ENABLED", True)
    user = await _load_user(db_session_maker, seed["user_id"])
    broker = _FakeBroker()

    with make_client(user, broker) as client:
        place = client.post(
            "/api/orders/live",
            json=_request_body(seed["strategy_id"]),
        )

    assert place.status_code == 403
    detail = place.json()["detail"]
    assert detail["safety_chain_result"]["blocking_check"]["check_name"] == "trust_score"
    assert "Trust Score 45/100 hai" in detail["failure_reason_hinglish"]
    assert "70+ chahiye" in detail["failure_reason_hinglish"]
    assert broker.place_calls == []


# 5. Block — stale scores ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stale_scores_block_with_purana_message(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    await _enrich_for_live_orders(
        db_session_maker,
        user_id=seed["user_id"],
        strategy_id=seed["strategy_id"],
        scores_age_hours=25,  # one hour past the 24h TTL
    )
    set_flag("LIVE_TRADING_ENABLED", True)
    user = await _load_user(db_session_maker, seed["user_id"])
    broker = _FakeBroker()

    with make_client(user, broker) as client:
        place = client.post(
            "/api/orders/live",
            json=_request_body(seed["strategy_id"]),
        )

    assert place.status_code == 403
    detail = place.json()["detail"]
    assert detail["safety_chain_result"]["blocking_check"]["check_name"] == "trust_score"
    assert "purana" in detail["failure_reason_hinglish"]


# 6. Block — live_trading_enabled flag off ────────────────────────────


@pytest.mark.asyncio
async def test_per_user_live_flag_off_blocks(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    await _enrich_for_live_orders(
        db_session_maker,
        user_id=seed["user_id"],
        strategy_id=seed["strategy_id"],
        user_live_trading_enabled=False,
    )
    set_flag("LIVE_TRADING_ENABLED", True)  # global on; per-user wins.
    user = await _load_user(db_session_maker, seed["user_id"])
    broker = _FakeBroker()

    with make_client(user, broker) as client:
        place = client.post(
            "/api/orders/live",
            json=_request_body(seed["strategy_id"]),
        )

    assert place.status_code == 403
    detail = place.json()["detail"]
    assert (
        detail["safety_chain_result"]["blocking_check"]["check_name"]
        == "live_trading_enabled"
    )
    assert "Customer support" in detail["failure_reason_hinglish"]


# 7. Block — auto kill switch tripped ────────────────────────────────


@pytest.mark.asyncio
async def test_auto_kill_switch_tripped_blocks_at_check_one(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
    fake_redis: fake_aioredis.FakeRedis,
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    await _enrich_for_live_orders(
        db_session_maker,
        user_id=seed["user_id"],
        strategy_id=seed["strategy_id"],
    )
    set_flag("LIVE_TRADING_ENABLED", True)
    # Trip the kill switch directly in fake redis. Going through
    # ``redis_client.set_kill_switch_status`` here would use whatever
    # ``get_redis()`` returns at *call time* — but ``make_client``
    # only installs the fake-redis monkey-patch lazily inside the
    # fixture body, so the call would land on the real client. Write
    # the value directly to the fake to skip the indirection.
    await fake_redis.set(
        f"kill:{seed['user_id']}", redis_client.KILL_SWITCH_TRIPPED
    )
    user = await _load_user(db_session_maker, seed["user_id"])
    broker = _FakeBroker()

    with make_client(user, broker) as client:
        place = client.post(
            "/api/orders/live",
            json=_request_body(seed["strategy_id"]),
        )

    assert place.status_code == 403
    detail = place.json()["detail"]
    assert (
        detail["safety_chain_result"]["blocking_check"]["check_name"]
        == "auto_kill_switch"
    )
    # Fail-fast: only the first check executed.
    assert len(detail["safety_chain_result"]["checks"]) == 1
    assert broker.place_calls == []


# 8. Broker offline (generic broker error) → 503 ─────────────────────


@pytest.mark.asyncio
async def test_broker_connection_error_returns_503(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    """All safety checks pass, but the broker SDK errors on
    place_order — the API maps it to 503."""
    await _enrich_for_live_orders(
        db_session_maker,
        user_id=seed["user_id"],
        strategy_id=seed["strategy_id"],
    )
    set_flag("LIVE_TRADING_ENABLED", True)
    user = await _load_user(db_session_maker, seed["user_id"])
    broker = _FakeBroker(
        always_raise=BrokerConnectionError(
            "network down", BrokerName.DHAN.value
        )
    )

    with make_client(user, broker) as client:
        place = client.post(
            "/api/orders/live",
            json=_request_body(seed["strategy_id"]),
        )

    assert place.status_code == 503
    # Some test environments install a global 5xx handler that
    # sanitises the detail to a generic message — the contract that
    # matters is the status code; broker_calls=1 confirms the broker
    # was invoked and raised.
    assert len(broker.place_calls) == 1


# 9. Session expired → relogin → success ─────────────────────────────


@pytest.mark.asyncio
async def test_session_expired_relogin_then_succeeds(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    await _enrich_for_live_orders(
        db_session_maker,
        user_id=seed["user_id"],
        strategy_id=seed["strategy_id"],
    )
    set_flag("LIVE_TRADING_ENABLED", True)
    user = await _load_user(db_session_maker, seed["user_id"])
    broker = _FakeBroker(
        raise_on_first_place=BrokerSessionExpiredError(
            "expired", BrokerName.DHAN.value
        )
    )

    with make_client(user, broker) as client:
        place = client.post(
            "/api/orders/live",
            json=_request_body(seed["strategy_id"]),
        )

    assert place.status_code == 200, place.text
    body = place.json()
    assert body["success"] is True
    assert body["order_id"] == "BROKER-INT-2"  # 2nd attempt won.
    assert broker.login_calls == 1
    assert len(broker.place_calls) == 2


# 10. Session expired → relogin fails → 503 ──────────────────────────


@pytest.mark.asyncio
async def test_session_expired_relogin_fails_returns_503(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    await _enrich_for_live_orders(
        db_session_maker,
        user_id=seed["user_id"],
        strategy_id=seed["strategy_id"],
    )
    set_flag("LIVE_TRADING_ENABLED", True)
    user = await _load_user(db_session_maker, seed["user_id"])
    broker = _FakeBroker(
        raise_on_first_place=BrokerSessionExpiredError(
            "expired", BrokerName.DHAN.value
        ),
        raise_on_relogin=BrokerAuthError(
            "relogin failed", BrokerName.DHAN.value
        ),
    )

    with make_client(user, broker) as client:
        place = client.post(
            "/api/orders/live",
            json=_request_body(seed["strategy_id"]),
        )

    assert place.status_code == 503
    # Verified via broker call counters: first place call raised
    # session-expired (1), relogin attempted (login_calls=1), retry
    # raised again because the relogin fake-broker raised — but the
    # orchestrator's _place_with_retry catches the relogin failure
    # before the second attempt. login_calls=1 confirms the retry
    # path took effect; place_calls=1 confirms only one place
    # attempt was made.
    assert broker.login_calls == 1
    assert len(broker.place_calls) == 1
    # The orchestrator emitted a blocked audit event with broker_offline.
    blocked = query_events(
        user_id=seed["user_id"],
        strategy_id=seed["strategy_id"],
        event_type="live_order_blocked",
    )
    assert blocked.filtered_count >= 1


# 11. Cross-user enumeration → 404 ──────────────────────────────────


@pytest.mark.asyncio
async def test_cross_user_strategy_returns_404_with_no_audit_leak(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    """User A's strategy id, User B authenticated → 404. The
    backend must not emit any audit event for the impostor's
    strategy_id (no information leak via the audit log)."""
    # Make A's strategy fully ready so the only failure mode is
    # ownership.
    await _enrich_for_live_orders(
        db_session_maker,
        user_id=seed["user_id"],
        strategy_id=seed["strategy_id"],
    )
    set_flag("LIVE_TRADING_ENABLED", True)
    # Seed user B (intruder) with their own strategy / creds, but we
    # use them to attack user A's strategy id.
    intruder = await _seed_user_with_strategy(
        db_session_maker, email="intruder-int@x"
    )
    intruder_user = await _load_user(db_session_maker, intruder["user_id"])
    broker = _FakeBroker()

    with make_client(intruder_user, broker) as client:
        place = client.post(
            "/api/orders/live",
            json=_request_body(seed["strategy_id"]),
        )

    assert place.status_code == 404
    assert broker.place_calls == []
    # Zero audit events keyed by the victim strategy id (the orchestrator
    # raises before audit emission on the LookupError path).
    leaked = query_events(strategy_id=seed["strategy_id"])
    assert leaked.filtered_count == 0


# 12. Sequential 5-order burst — all succeed ─────────────────────────


@pytest.mark.asyncio
async def test_five_sequential_orders_all_succeed(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    """Five back-to-back orders all succeed — pins the absence of
    module-level mutable state in the chain or orchestrator. (True
    HTTP-level concurrency requires multiple TestClients which is
    awkward in this harness; sequential burst is the proxy that
    catches every shared-state regression we've seen in practice.)"""
    await _enrich_for_live_orders(
        db_session_maker,
        user_id=seed["user_id"],
        strategy_id=seed["strategy_id"],
    )
    set_flag("LIVE_TRADING_ENABLED", True)
    user = await _load_user(db_session_maker, seed["user_id"])
    broker = _FakeBroker()

    with make_client(user, broker) as client:
        responses = [
            client.post(
                "/api/orders/live",
                json=_request_body(seed["strategy_id"]),
            )
            for _ in range(5)
        ]

    for r in responses:
        assert r.status_code == 200, r.text
        assert r.json()["success"] is True
    # 5 place calls, 5 distinct broker_order_ids.
    assert len(broker.place_calls) == 5
    order_ids = {r.json()["order_id"] for r in responses}
    assert len(order_ids) == 5

    # 5 PRE + 5 POST = 10 attempt events.
    attempts = query_events(
        user_id=seed["user_id"],
        strategy_id=seed["strategy_id"],
        event_type="live_order_attempted",
    )
    assert attempts.filtered_count == 10


# 13. Preflight refresh flow ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_preflight_refresh_flow_block_then_unblock_then_place(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
    make_client: Callable[[User, _FakeBroker], TestClient],
) -> None:
    """Preflight reports a fail; user fixes (we add the missing rows);
    preflight returns clean; place succeeds. Mirrors the UI's
    expected refresh loop."""
    # Start with only 3 paper sessions (block).
    await _enrich_for_live_orders(
        db_session_maker,
        user_id=seed["user_id"],
        strategy_id=seed["strategy_id"],
        paper_session_count=3,
    )
    set_flag("LIVE_TRADING_ENABLED", True)
    user = await _load_user(db_session_maker, seed["user_id"])
    broker = _FakeBroker()

    with make_client(user, broker) as client:
        first = client.get(
            "/api/orders/live/preflight",
            params={"strategy_id": str(seed["strategy_id"])},
        )
        assert first.status_code == 200
        assert first.json()["all_passed"] is False
        assert (
            first.json()["blocking_check"]["check_name"] == "paper_sessions"
        )

        # User completes 4 more paper sessions (the spec's "fix" step).
        async with db_session_maker() as s:
            base = date(2026, 6, 1)
            for i in range(4):
                row = await paper_store.create_session(
                    s,
                    user_id=seed["user_id"],
                    strategy_id=seed["strategy_id"],
                    engine_strategy_id="eng",
                    session_date=base + timedelta(days=i),
                )
                await paper_store.complete_session(
                    s,
                    session_id=row.id,
                    total_trades=1,
                    total_pnl=Decimal("10"),
                )
            await s.commit()

        second = client.get(
            "/api/orders/live/preflight",
            params={"strategy_id": str(seed["strategy_id"])},
        )
        assert second.status_code == 200
        assert second.json()["all_passed"] is True

        place = client.post(
            "/api/orders/live",
            json=_request_body(seed["strategy_id"]),
        )

    assert place.status_code == 200, place.text
    assert place.json()["success"] is True
    assert len(broker.place_calls) == 1


# Sanity — strategy column writeback path (light coverage of the cache
# producer; the heavy path is in test_backtest_endpoint).


@pytest.mark.asyncio
async def test_backtest_endpoint_writes_scores_visible_to_safety_chain(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
    make_client: Callable[[User, _FakeBroker], TestClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calling POST /api/strategies/{id}/backtest populates the cache
    columns the SafetyChain reads. Asserts the producer/consumer pair
    are wired against the same row at the integration level.

    NOTE: pre-guard this test drove the cache write via a synthetic
    run (``json={}``). The new score-write guard at backtest.py:403
    requires ``candles_source == "dhan_historical"`` — synthetic
    fallback (Dhan outage / market-hours gate / raw-injection) must
    NOT mutate the gate. To drive the integration-level cache write
    we mock the Dhan adapter to return clean candles and pin the
    market-closed branch, mirroring the unit-test pattern in
    ``tests/strategy_engine/api/test_backtest_endpoint.py``.
    """
    # Seed strategy_json so backtest can run; clear scores so the
    # writeback effect is observable.
    async with db_session_maker() as s:
        strat = await s.get(Strategy, seed["strategy_id"])
        assert strat is not None
        strat.strategy_json = _VALID_DSL.copy()
        strat.last_trust_score = None
        strat.last_truth_score = None
        strat.last_scores_at = None
        await s.commit()

    # Drive the real-data path so the guard allows the score write.
    monkeypatch.setenv("DHAN_ACCESS_TOKEN", "test-token")

    async def _force_market_closed() -> bool:
        return False

    monkeypatch.setattr(
        "app.strategy_engine.api.backtest._market_is_open", _force_market_closed
    )

    from app.strategy_engine.data_provider.models import (
        HistoricalDataRequest,
        HistoricalDataResponse,
    )
    from app.strategy_engine.schema.ohlcv import Candle

    base = datetime(2026, 4, 1, 9, 30, tzinfo=UTC)
    fake_candles = [
        Candle(
            timestamp=base + timedelta(minutes=i),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1_000.0,
        )
        for i in range(120)
    ]

    def _fake_fetch(
        request: HistoricalDataRequest, *args: Any, **kwargs: Any
    ) -> HistoricalDataResponse:
        return HistoricalDataResponse(
            candles=fake_candles,
            request=request,
            fetched_at=datetime.now(UTC),
            cache_hit=False,
            quality_warnings=[],
        )

    monkeypatch.setattr(
        "app.strategy_engine.api.backtest.fetch_historical_candles",
        _fake_fetch,
    )

    user = await _load_user(db_session_maker, seed["user_id"])
    broker = _FakeBroker()

    candles_request = {
        "symbol": "NIFTY",
        "timeframe": "1m",
        "from_date": "2026-04-01T09:30:00Z",
        "to_date": "2026-04-01T11:30:00Z",
    }

    with make_client(user, broker) as client:
        resp = client.post(
            f"/api/strategies/{seed['strategy_id']}/backtest",
            json={"candles_request": candles_request},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candles_source"] == "dhan_historical"
    assert body["reliability"] is not None
    assert body["truth"] is not None

    # Verify the row picked up the scores.
    async with db_session_maker() as s:
        row = await s.get(Strategy, seed["strategy_id"])
        assert row is not None
        assert row.last_trust_score is not None
        assert row.last_truth_score is not None
        assert row.last_scores_at is not None


# ─── Auth required (defence in depth) ────────────────────────────────


@pytest.mark.asyncio
async def test_post_live_requires_authentication(
    monkeypatch: pytest.MonkeyPatch,
    db_session_maker: async_sessionmaker[AsyncSession],
    fake_redis: fake_aioredis.FakeRedis,
    seed: dict[str, Any],
) -> None:
    """Confirm the endpoint enforces JWT through the full app stack —
    no auth override here, so the dep raises 401."""
    # Re-use the conftest's stock client wiring without our auth
    # override. Build a minimal client by importing the conftest's
    # fixture machinery directly.
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
    from app.core import config as _config

    _config.get_settings.cache_clear()

    monkeypatch.setattr("app.core.redis_client.get_redis", lambda: fake_redis)
    monkeypatch.setattr(
        "app.core.redis_client.close_redis", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        "redis.asyncio.from_url", lambda *a, **kw: fake_redis
    )

    class _FakeEngine:
        async def dispose(self) -> None:
            return None

        def connect(self) -> Any:
            from contextlib import asynccontextmanager

            @asynccontextmanager
            async def _ctx() -> Any:
                conn = MagicMock()
                conn.execute = AsyncMock(return_value=MagicMock())
                yield conn

            return _ctx()

    monkeypatch.setattr("app.db.session.get_engine", lambda: _FakeEngine())
    monkeypatch.setattr(
        "app.db.session.dispose_engine", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        "app.db.session.get_sessionmaker", lambda: db_session_maker
    )
    monkeypatch.setattr(
        "app.workers.position_loop.start_position_loop", lambda _app: None
    )
    monkeypatch.setattr(
        "app.workers.position_loop.stop_position_loop",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.workers.reconciliation_loop.start_reconciliation_loop",
        lambda _app: None,
    )
    monkeypatch.setattr(
        "app.workers.reconciliation_loop.stop_reconciliation_loop",
        AsyncMock(return_value=None),
    )

    app = create_app()

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with db_session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session

    with TestClient(app) as client:
        resp = client.post(
            "/api/orders/live",
            json=_request_body(seed["strategy_id"]),
        )
    assert resp.status_code == 401


# ─── Locked broker-credential FK contract ────────────────────────────


@pytest.mark.asyncio
async def test_active_credential_is_visible_to_chain_at_e2e(
    db_session_maker: async_sessionmaker[AsyncSession],
    seed: dict[str, Any],
) -> None:
    """Sanity: the conftest seed wires an active Dhan credential and
    the strategy's FK points at it. If this ever drifts, the broker_
    connection check will mysteriously fail in every scenario above —
    pin it explicitly so the breakage surfaces here rather than in
    every individual test."""
    async with db_session_maker() as s:
        cred = (
            await s.execute(
                select(BrokerCredential).where(
                    BrokerCredential.user_id == seed["user_id"],
                    BrokerCredential.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        assert cred is not None
        assert cred.broker_name == BrokerName.DHAN

        strat = await s.get(Strategy, seed["strategy_id"])
        assert strat is not None
        assert strat.broker_credential_id == cred.id
