"""Unit tests for :func:`place_live_order`.

Exercises the orchestrator directly with an injected ``broker_factory``
that returns a :class:`_FakeBroker`. SafetyChain prerequisites are
seeded by reusing the ``all_passing`` fixture from
:mod:`tests.strategy_engine.live_orders.conftest`.

Audit-trail assertions read the in-memory ring buffer via
:func:`query_events`. Every test clears the buffer before exercising
the orchestrator so events from earlier tests never leak in.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import fakeredis.aioredis as fake_aioredis
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import redis_client
from app.core.exceptions import (
    BrokerAuthError,
    BrokerConnectionError,
    BrokerSessionExpiredError,
)
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.schemas.broker import (
    BrokerCredentials,
    BrokerName,
    OrderRequest,
    OrderResponse,
    OrderStatus,
)
from app.strategy_engine.audit import clear_audit_log, query_events
from app.strategy_engine.live_orders.models import LiveOrderRequest
from app.strategy_engine.live_orders.order_router import (
    BrokerOfflineError,
    PaperModeActiveError,
    place_live_order,
)

# ─── Test doubles ─────────────────────────────────────────────────────


class _FakeBroker:
    """Minimal stand-in for :class:`DhanBroker`. Records every call.

    Behaviours configurable via constructor flags:

        * ``raise_on_first_place`` — first call raises this exception.
        * ``raise_on_relogin`` — when set, ``login`` raises (simulates
          the relogin failure path).
        * ``always_raise`` — every place_order raises this; tests for
          generic broker errors set this.
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
            broker_order_id=f"FAKE-{len(self.place_calls)}",
            status=OrderStatus.COMPLETE,
            message="placed",
            raw_response={"echo": order.symbol},
        )


def _factory_returning(
    broker: _FakeBroker,
) -> Any:
    """Build a ``broker_factory`` that always returns the same fake."""

    def _f(_creds: BrokerCredentials) -> _FakeBroker:
        return broker

    return _f


def _make_request(
    strategy_id: uuid.UUID,
    *,
    dry_run: bool = False,
    quantity: int = 1,
) -> LiveOrderRequest:
    return LiveOrderRequest(
        strategy_id=strategy_id,
        symbol="NIFTY25JANFUT",
        side="BUY",
        quantity=quantity,
        price=None,
        dry_run=dry_run,
        exchange="NFO",
        product_type="INTRADAY",
    )


@pytest.fixture(autouse=True)
def _isolated_audit_log() -> None:
    """Reset the audit ring buffer before and after each test."""
    clear_audit_log()


@pytest.fixture
async def all_passing_with_strategy_dsl(
    all_passing: tuple[User, Strategy],
    db: AsyncSession,
) -> tuple[User, Strategy]:
    """Extend ``all_passing`` with the strategy_json + broker FK that
    the order_router needs (Broker Guard subset checks DSL stop-loss;
    broker resolution needs the FK)."""
    from app.core.security import encrypt_credential
    from app.db.models.broker_credential import BrokerCredential

    user, strategy = all_passing
    strategy.strategy_json = {
        "id": "live_order_test",
        "name": "Live order test",
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

    cred = BrokerCredential(
        user_id=user.id,
        broker_name=BrokerName.DHAN,
        client_id_enc=encrypt_credential("CID2"),
        api_key_enc=encrypt_credential("KEY2"),
        api_secret_enc=encrypt_credential("SEC2"),
        access_token_enc=encrypt_credential("TOK2"),
        token_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        is_active=True,
    )
    db.add(cred)
    await db.flush()
    strategy.broker_credential_id = cred.id
    await db.flush()
    return user, strategy


# ─── 1. Happy path ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_all_checks_pass_places_order_and_returns_broker_id(
    all_passing_with_strategy_dsl: tuple[User, Strategy],
    db: AsyncSession,
    redis: fake_aioredis.FakeRedis,
) -> None:
    user, strategy = all_passing_with_strategy_dsl
    broker = _FakeBroker()

    result = await place_live_order(
        _make_request(strategy.id),
        user_id=user.id,
        db_session=db,
        broker_factory=_factory_returning(broker),
    )

    assert result.success is True
    assert result.order_id == "FAKE-1"
    assert result.is_dry_run is False
    assert result.broker_guard_passed is True
    assert result.failure_reason_hinglish is None
    assert result.broker_response is not None
    assert result.broker_response["broker_order_id"] == "FAKE-1"
    # Exactly one place_order call.
    assert len(broker.place_calls) == 1


# ─── 2-4. SafetyChain failures ────────────────────────────────────────


@pytest.mark.asyncio
async def test_paper_sessions_below_seven_blocks_with_check_name(
    db: AsyncSession,
    user: User,
    strategy: Strategy,
    redis: fake_aioredis.FakeRedis,
) -> None:
    """No paper sessions seeded — chain stops at check #2."""
    broker = _FakeBroker()
    result = await place_live_order(
        _make_request(strategy.id),
        user_id=user.id,
        db_session=db,
        broker_factory=_factory_returning(broker),
    )
    assert result.success is False
    assert result.broker_guard_passed is False
    assert (
        result.safety_chain_result.blocking_check is not None
        and result.safety_chain_result.blocking_check.check_name
        == "paper_sessions"
    )
    assert "Sirf 0/7" in result.failure_reason_hinglish
    # Broker must NOT have been called.
    assert broker.place_calls == []


@pytest.mark.asyncio
async def test_kill_switch_tripped_blocks_at_check_one(
    all_passing_with_strategy_dsl: tuple[User, Strategy],
    db: AsyncSession,
    redis: fake_aioredis.FakeRedis,
) -> None:
    user, strategy = all_passing_with_strategy_dsl
    await redis_client.set_kill_switch_status(
        user.id, redis_client.KILL_SWITCH_TRIPPED
    )
    broker = _FakeBroker()
    result = await place_live_order(
        _make_request(strategy.id),
        user_id=user.id,
        db_session=db,
        broker_factory=_factory_returning(broker),
    )
    assert result.success is False
    assert (
        result.safety_chain_result.blocking_check is not None
        and result.safety_chain_result.blocking_check.check_name
        == "auto_kill_switch"
    )
    assert "Auto Kill Switch active hai" in result.failure_reason_hinglish
    assert broker.place_calls == []


@pytest.mark.asyncio
async def test_trust_score_low_blocks_with_score_in_message(
    all_passing_with_strategy_dsl: tuple[User, Strategy],
    db: AsyncSession,
    redis: fake_aioredis.FakeRedis,
) -> None:
    _user, strategy = all_passing_with_strategy_dsl
    strategy.last_trust_score = Decimal("60.00")
    await db.flush()
    broker = _FakeBroker()
    result = await place_live_order(
        _make_request(strategy.id),
        user_id=_user.id,
        db_session=db,
        broker_factory=_factory_returning(broker),
    )
    assert result.success is False
    assert "Trust Score 60/100 hai" in result.failure_reason_hinglish
    assert broker.place_calls == []


# ─── 5. Broker Guard subset (no DSL) ──────────────────────────────────


@pytest.mark.asyncio
async def test_strategy_without_dsl_blocked_by_broker_guard(
    all_passing: tuple[User, Strategy],
    db: AsyncSession,
    redis: fake_aioredis.FakeRedis,
) -> None:
    """all_passing seeds NULL strategy_json → guard subset fails."""
    user, strategy = all_passing
    # No broker FK — but the guard fails BEFORE broker resolution.
    broker = _FakeBroker()
    result = await place_live_order(
        _make_request(strategy.id),
        user_id=user.id,
        db_session=db,
        broker_factory=_factory_returning(broker),
    )
    assert result.success is False
    assert result.broker_guard_passed is False
    assert "Strategy has no DSL" in result.failure_reason_hinglish
    assert broker.place_calls == []


# ─── 6-7. Dry-run mode ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dry_run_with_all_checks_pass_returns_simulated_id(
    all_passing_with_strategy_dsl: tuple[User, Strategy],
    db: AsyncSession,
    redis: fake_aioredis.FakeRedis,
) -> None:
    user, strategy = all_passing_with_strategy_dsl
    broker = _FakeBroker()

    result = await place_live_order(
        _make_request(strategy.id, dry_run=True),
        user_id=user.id,
        db_session=db,
        broker_factory=_factory_returning(broker),
    )

    assert result.success is True
    assert result.is_dry_run is True
    assert result.order_id == "DRY_RUN_SIMULATED"
    assert result.broker_response is None
    # Critical: no broker call in dry-run.
    assert broker.place_calls == []
    assert broker.login_calls == 0


@pytest.mark.asyncio
async def test_dry_run_with_safety_fail_returns_no_broker_call(
    db: AsyncSession,
    user: User,
    strategy: Strategy,
    redis: fake_aioredis.FakeRedis,
) -> None:
    broker = _FakeBroker()
    result = await place_live_order(
        _make_request(strategy.id, dry_run=True),
        user_id=user.id,
        db_session=db,
        broker_factory=_factory_returning(broker),
    )
    assert result.success is False
    assert result.is_dry_run is True
    assert broker.place_calls == []


# ─── 8-10. Broker behaviour on the place call ────────────────────────


@pytest.mark.asyncio
async def test_session_expired_one_shot_relogin_then_succeeds(
    all_passing_with_strategy_dsl: tuple[User, Strategy],
    db: AsyncSession,
    redis: fake_aioredis.FakeRedis,
) -> None:
    user, strategy = all_passing_with_strategy_dsl
    broker = _FakeBroker(
        raise_on_first_place=BrokerSessionExpiredError(
            "expired", BrokerName.DHAN.value
        )
    )
    result = await place_live_order(
        _make_request(strategy.id),
        user_id=user.id,
        db_session=db,
        broker_factory=_factory_returning(broker),
    )
    assert result.success is True
    assert result.order_id == "FAKE-2"  # second attempt placed it.
    assert broker.login_calls == 1
    assert len(broker.place_calls) == 2


@pytest.mark.asyncio
async def test_session_expired_relogin_fails_raises_offline_error(
    all_passing_with_strategy_dsl: tuple[User, Strategy],
    db: AsyncSession,
    redis: fake_aioredis.FakeRedis,
) -> None:
    user, strategy = all_passing_with_strategy_dsl
    broker = _FakeBroker(
        raise_on_first_place=BrokerSessionExpiredError(
            "expired", BrokerName.DHAN.value
        ),
        raise_on_relogin=BrokerAuthError("relogin failed", BrokerName.DHAN.value),
    )
    with pytest.raises(BrokerOfflineError):
        await place_live_order(
            _make_request(strategy.id),
            user_id=user.id,
            db_session=db,
            broker_factory=_factory_returning(broker),
        )


@pytest.mark.asyncio
async def test_broker_connection_error_propagates(
    all_passing_with_strategy_dsl: tuple[User, Strategy],
    db: AsyncSession,
    redis: fake_aioredis.FakeRedis,
) -> None:
    """Non-session-expired broker errors propagate; the API layer
    maps them to 503."""
    user, strategy = all_passing_with_strategy_dsl
    broker = _FakeBroker(
        always_raise=BrokerConnectionError(
            "network down", BrokerName.DHAN.value
        )
    )
    with pytest.raises(BrokerConnectionError):
        await place_live_order(
            _make_request(strategy.id),
            user_id=user.id,
            db_session=db,
            broker_factory=_factory_returning(broker),
        )


# ─── 11-13. Audit log emissions ──────────────────────────────────────


@pytest.mark.asyncio
async def test_pre_audit_event_emitted_on_success(
    all_passing_with_strategy_dsl: tuple[User, Strategy],
    db: AsyncSession,
    redis: fake_aioredis.FakeRedis,
) -> None:
    user, strategy = all_passing_with_strategy_dsl
    broker = _FakeBroker()
    await place_live_order(
        _make_request(strategy.id),
        user_id=user.id,
        db_session=db,
        broker_factory=_factory_returning(broker),
    )
    events = query_events(
        user_id=user.id, strategy_id=strategy.id, event_type="live_order_attempted"
    )
    # PRE + POST = exactly two emissions for a successful live order.
    assert events.filtered_count == 2


@pytest.mark.asyncio
async def test_blocked_audit_event_emitted_on_safety_fail(
    db: AsyncSession,
    user: User,
    strategy: Strategy,
    redis: fake_aioredis.FakeRedis,
) -> None:
    broker = _FakeBroker()
    await place_live_order(
        _make_request(strategy.id),
        user_id=user.id,
        db_session=db,
        broker_factory=_factory_returning(broker),
    )
    blocked = query_events(
        user_id=user.id, strategy_id=strategy.id, event_type="live_order_blocked"
    )
    assert blocked.filtered_count == 1
    assert blocked.events[0].severity == "critical"


@pytest.mark.asyncio
async def test_dry_run_emits_only_pre_audit_event(
    all_passing_with_strategy_dsl: tuple[User, Strategy],
    db: AsyncSession,
    redis: fake_aioredis.FakeRedis,
) -> None:
    """Dry-run emits PRE only — the absence of a POST is the audit-
    trail signal that no broker call happened. The closed Phase 11
    EventType set has no dedicated dry-run literal, so this contract
    must stay readable from the count alone."""
    user, strategy = all_passing_with_strategy_dsl
    broker = _FakeBroker()
    await place_live_order(
        _make_request(strategy.id, dry_run=True),
        user_id=user.id,
        db_session=db,
        broker_factory=_factory_returning(broker),
    )
    events = query_events(
        user_id=user.id, strategy_id=strategy.id, event_type="live_order_attempted"
    )
    assert events.filtered_count == 1


# ─── 14. Cross-user enumeration ──────────────────────────────────────


@pytest.mark.asyncio
async def test_cross_user_strategy_raises_lookup_error(
    all_passing_with_strategy_dsl: tuple[User, Strategy],
    db: AsyncSession,
    redis: fake_aioredis.FakeRedis,
) -> None:
    """An intruder cannot place an order on someone else's strategy."""
    _owner, strategy = all_passing_with_strategy_dsl
    intruder_id = uuid.uuid4()
    broker = _FakeBroker()
    with pytest.raises(LookupError):
        await place_live_order(
            _make_request(strategy.id),
            user_id=intruder_id,
            db_session=db,
            broker_factory=_factory_returning(broker),
        )
    assert broker.place_calls == []


# ─── 15. Determinism + concurrency ───────────────────────────────────


@pytest.mark.asyncio
async def test_same_request_same_response_shape(
    all_passing_with_strategy_dsl: tuple[User, Strategy],
    db: AsyncSession,
    redis: fake_aioredis.FakeRedis,
) -> None:
    """Two back-to-back calls with the same request produce identical
    success / blocking_check / safety check names. The
    ``placed_at`` timestamp + ``order_id`` differ between runs by
    design — exclude them from the comparison."""
    user, strategy = all_passing_with_strategy_dsl
    broker = _FakeBroker()
    factory = _factory_returning(broker)

    first = await place_live_order(
        _make_request(strategy.id),
        user_id=user.id,
        db_session=db,
        broker_factory=factory,
    )
    second = await place_live_order(
        _make_request(strategy.id),
        user_id=user.id,
        db_session=db,
        broker_factory=factory,
    )
    assert first.success == second.success
    assert tuple(c.check_name for c in first.safety_chain_result.checks) == tuple(
        c.check_name for c in second.safety_chain_result.checks
    )


@pytest.mark.asyncio
async def test_concurrent_orders_both_succeed(
    all_passing_with_strategy_dsl: tuple[User, Strategy],
    redis: fake_aioredis.FakeRedis,
) -> None:
    """Five chain runs in parallel, each through its own DB session
    pointing at the same shared in-memory database, all succeed."""
    from datetime import date as _date

    from sqlalchemy.ext.asyncio import (
        async_sessionmaker,
        create_async_engine,
    )
    from sqlalchemy.pool import StaticPool

    from app.core.security import encrypt_credential
    from app.db.base import Base
    from app.db.models.broker_credential import BrokerCredential
    from app.db.models.strategy import Strategy as StrategyORM
    from app.db.models.user import User as UserORM
    from app.strategy_engine.feature_flags import set_flag
    from app.strategy_engine.paper_trading import store as paper_store

    engine = create_async_engine(
        "sqlite+aiosqlite:///file:tradetri-router-conc?mode=memory&cache=shared&uri=true",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False, "uri": True},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with maker() as s:
        u = UserORM(
            email="conc-router@x",
            password_hash="p",
            is_active=True,
            live_trading_enabled=True,
        )
        s.add(u)
        await s.flush()
        strat = StrategyORM(
            user_id=u.id,
            name="conc-router",
            is_active=True,
            strategy_json={
                "id": "conc",
                "name": "Conc",
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
            },
        )
        s.add(strat)
        await s.flush()
        base = _date(2026, 5, 1)
        for i in range(7):
            row = await paper_store.create_session(
                s,
                user_id=u.id,
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
        cred = BrokerCredential(
            user_id=u.id,
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
        user_id = u.id
        strat_id = strat.id

    set_flag("LIVE_TRADING_ENABLED", True)

    async def _one_run() -> Any:
        broker = _FakeBroker()
        async with maker() as session:
            return await place_live_order(
                _make_request(strat_id),
                user_id=user_id,
                db_session=session,
                broker_factory=_factory_returning(broker),
            )

    results = await asyncio.gather(*(_one_run() for _ in range(5)))
    await engine.dispose()
    for r in results:
        assert r.success is True


# ═══════════════════════════════════════════════════════════════════════
# Paper-mode gate (safety fix #3)
# ═══════════════════════════════════════════════════════════════════════


class TestPaperModeGate:
    """``place_live_order`` must raise :class:`PaperModeActiveError`
    immediately when ``settings.strategy_paper_mode`` is True. No
    SafetyChain runs, no broker is built, no broker call is made.

    The module-level autouse fixture in ``conftest.py`` forces paper
    OFF; this nested autouse re-enables it for this class only."""

    @pytest.fixture(autouse=True)
    def _force_paper_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.core.config import get_settings

        monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_place_live_order_raises_in_paper_mode(
        self,
        all_passing_with_strategy_dsl: tuple[User, Strategy],
        db: AsyncSession,
        redis: fake_aioredis.FakeRedis,
    ) -> None:
        """SafetyChain would otherwise pass on this seed; paper-mode
        guard fires earlier and aborts the call."""
        user, strategy = all_passing_with_strategy_dsl
        broker = _FakeBroker()

        with pytest.raises(PaperModeActiveError) as exc_info:
            await place_live_order(
                _make_request(strategy.id),
                user_id=user.id,
                db_session=db,
                broker_factory=_factory_returning(broker),
            )

        # Hinglish detail + July 2026 reference (frontend modal copy).
        assert "paper mode" in str(exc_info.value).lower()
        assert "July 2026" in str(exc_info.value)
        # Broker was never touched.
        assert broker.place_calls == []
        assert broker.login_calls == 0


@pytest.mark.asyncio
async def test_place_live_order_works_in_live_mode(
    all_passing_with_strategy_dsl: tuple[User, Strategy],
    db: AsyncSession,
    redis: fake_aioredis.FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression guard for safety fix #3: with paper mode OFF, the
    existing live-mode contract is unchanged — SafetyChain runs,
    broker is built, ``place_order`` is called once."""
    from app.core.config import get_settings

    monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
    get_settings.cache_clear()

    user, strategy = all_passing_with_strategy_dsl
    broker = _FakeBroker()

    result = await place_live_order(
        _make_request(strategy.id),
        user_id=user.id,
        db_session=db,
        broker_factory=_factory_returning(broker),
    )

    assert result.success is True
    assert result.order_id == "FAKE-1"
    assert len(broker.place_calls) == 1
