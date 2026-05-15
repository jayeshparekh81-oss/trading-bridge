"""Tests for :mod:`app.services.kill_switch_service`."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core import redis_client
from app.core.security import encrypt_credential
from app.db.base import Base
from app.db.models.broker_credential import BrokerCredential
from app.db.models.kill_switch import KillSwitchConfig, KillSwitchEvent
from app.db.models.user import User
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.db.models.webhook_token import WebhookToken
from app.schemas.broker import (
    BrokerCredentials,
    BrokerName,
    Exchange,
    OrderRequest,
    OrderResponse,
    OrderSide,
    OrderStatus,
    OrderType,
    ProductType,
)
from app.schemas.kill_switch import (
    KillSwitchConfigCreate,
    KillSwitchState,
    TripReason,
)
from app.services.kill_switch_service import (
    KillSwitchService,
    delete_expired_idempotency,
    kill_switch_service,
)


# ═══════════════════════════════════════════════════════════════════════
# Fake broker used for emergency-square-off testing
# ═══════════════════════════════════════════════════════════════════════


class _FakeBroker:
    broker_name = BrokerName.FYERS

    def __init__(
        self,
        *,
        cancelled: int = 0,
        squared: int = 0,
        fail: str | None = None,
        place_order_fail: bool = False,
    ) -> None:
        self._cancelled = cancelled
        self._squared = squared
        self._fail = fail
        self._place_order_fail = place_order_fail
        self.place_order_calls: list[OrderRequest] = []
        self.login_called = False

    async def login(self) -> bool:
        self.login_called = True
        return True

    async def is_session_valid(self) -> bool:
        return True

    async def cancel_all_pending(self) -> int:
        if self._fail == "cancel":
            raise RuntimeError("cancel failed")
        return self._cancelled

    async def square_off_all(self) -> list[OrderResponse]:
        if self._fail == "square":
            raise RuntimeError("square failed")
        return [
            OrderResponse(
                broker_order_id=f"OID-{i}",
                status=OrderStatus.COMPLETE,
                message="closed",
            )
            for i in range(self._squared)
        ]

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        self.place_order_calls.append(order)
        if self._place_order_fail:
            raise RuntimeError(f"place_order failed for {order.symbol}")
        return OrderResponse(
            broker_order_id=f"KS-{order.symbol}-{len(self.place_order_calls)}",
            status=OrderStatus.COMPLETE,
            message="kill-switch close placed",
            raw_response={"symbol": order.symbol, "qty": order.quantity},
        )


def _factory(by_cred_id: dict[Any, _FakeBroker]) -> Any:
    def _f(creds: BrokerCredentials) -> _FakeBroker:
        # Any broker works — we keep one per credential by matching any.
        # For per-credential behaviour, the test calls this indirectly.
        for v in by_cred_id.values():
            return v
        raise RuntimeError("no broker configured")
    return _f


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _force_live_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """All tests in this module exercise the LIVE-mode square-off path
    (real ``_FakeBroker.place_order`` calls). Safety fix #2 added a
    paper-mode short-circuit that would otherwise zero out the broker
    interactions these tests assert on, so force ``STRATEGY_PAPER_MODE``
    off and clear the ``get_settings`` lru_cache before each test.

    Paper-mode behaviour is covered in ``test_kill_switch_paper_mode.py``.
    """
    from app.core.config import get_settings

    monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def redis(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[fake_aioredis.FakeRedis]:
    client = fake_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: client)
    try:
        yield client
    finally:
        await client.aclose()


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def user(session: AsyncSession) -> User:
    u = User(email="t@x", password_hash="p", is_active=True)
    session.add(u)
    await session.flush()
    return u


@pytest_asyncio.fixture
async def config(session: AsyncSession, user: User) -> KillSwitchConfig:
    row = KillSwitchConfig(
        user_id=user.id,
        max_daily_loss_inr=Decimal("5000"),
        max_daily_trades=10,
        enabled=True,
        auto_square_off=True,
    )
    session.add(row)
    await session.flush()
    return row


@pytest_asyncio.fixture
async def credential(session: AsyncSession, user: User) -> BrokerCredential:
    cred = BrokerCredential(
        user_id=user.id,
        broker_name=BrokerName.FYERS,
        client_id_enc=encrypt_credential("CID"),
        api_key_enc=encrypt_credential("KEY"),
        api_secret_enc=encrypt_credential("SEC"),
        access_token_enc=encrypt_credential("TOK"),
        token_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        is_active=True,
    )
    session.add(cred)
    await session.flush()
    return cred


@pytest_asyncio.fixture
async def strategy(
    session: AsyncSession, user: User, credential: BrokerCredential
) -> Strategy:
    token = WebhookToken(
        user_id=user.id,
        token_hash="x" * 64,
        hmac_secret_enc=encrypt_credential("secret"),
        label="t",
    )
    session.add(token)
    await session.flush()
    strat = Strategy(
        user_id=user.id,
        name="test-strategy",
        webhook_token_id=token.id,
        broker_credential_id=credential.id,
        is_active=True,
    )
    session.add(strat)
    await session.flush()
    return strat


async def _seed_open_position(
    session: AsyncSession,
    *,
    user: User,
    strategy: Strategy,
    credential: BrokerCredential,
    symbol: str = "NIFTY24DEC25000CE",
    side: str = "buy",
    qty: int = 75,
) -> StrategyPosition:
    pos = StrategyPosition(
        user_id=user.id,
        strategy_id=strategy.id,
        broker_credential_id=credential.id,
        symbol=symbol,
        side=side,
        total_quantity=qty,
        remaining_quantity=qty,
        avg_entry_price=Decimal("100.0"),
        status="open",
    )
    session.add(pos)
    await session.flush()
    return pos


@pytest.fixture
def svc() -> KillSwitchService:
    return kill_switch_service


# ═══════════════════════════════════════════════════════════════════════
# Config + status
# ═══════════════════════════════════════════════════════════════════════


class TestConfigAndStatus:
    async def test_get_config_from_db(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        svc: KillSwitchService,
    ) -> None:
        row = await svc.get_config(user.id, session)
        assert row is not None
        assert row.max_daily_loss_inr == Decimal("5000")

    async def test_update_config(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        svc: KillSwitchService,
    ) -> None:
        row = await svc.update_config(
            user.id,
            KillSwitchConfigCreate(
                max_daily_loss_inr=Decimal("25000"),
                max_daily_trades=100,
                enabled=True,
                auto_square_off=False,
            ),
            session,
        )
        assert row.max_daily_loss_inr == Decimal("25000")
        assert row.auto_square_off is False

    async def test_status_within_limits(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        svc: KillSwitchService,
    ) -> None:
        status = await svc.get_status(user.id, session)
        assert status.state is KillSwitchState.ACTIVE
        assert status.remaining_loss_budget == Decimal("5000")
        assert status.remaining_trades == 10


# ═══════════════════════════════════════════════════════════════════════
# Trigger
# ═══════════════════════════════════════════════════════════════════════


class TestTrigger:
    async def test_no_trigger_when_within_limit(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        svc: KillSwitchService,
    ) -> None:
        await redis_client.set_daily_pnl(user.id, Decimal("-1000"))
        result = await svc.check_and_trigger(user.id, session)
        assert result.triggered is False

    async def test_no_trigger_exactly_at_limit(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        svc: KillSwitchService,
    ) -> None:
        await redis_client.set_daily_pnl(user.id, Decimal("-5000"))
        result = await svc.check_and_trigger(user.id, session)
        # "Only when exceeded" — ``-max_loss`` does NOT fire.
        assert result.triggered is False

    async def test_triggers_when_exceeded(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        credential: BrokerCredential,
        strategy: Strategy,
        svc: KillSwitchService,
    ) -> None:
        await _seed_open_position(
            session, user=user, strategy=strategy, credential=credential
        )
        broker = _FakeBroker()
        await redis_client.set_daily_pnl(user.id, Decimal("-6000"))
        result = await svc.check_and_trigger(
            user.id, session, broker_factory=_factory({credential.id: broker})
        )
        assert result.triggered is True
        assert result.reason is TripReason.DAILY_LOSS_BREACHED
        # cancel_all_pending removed from emergency path (Layer 2 scope fix)
        assert result.actions[0].pending_cancelled == 0
        assert result.actions[0].positions_squared_off == 1
        assert len(broker.place_order_calls) == 1
        assert broker.place_order_calls[0].side is OrderSide.SELL

    async def test_trip_flips_redis(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        credential: BrokerCredential,
        svc: KillSwitchService,
    ) -> None:
        broker = _FakeBroker()
        await redis_client.set_daily_pnl(user.id, Decimal("-6000"))
        await svc.check_and_trigger(
            user.id, session, broker_factory=_factory({credential.id: broker})
        )
        assert (
            await redis_client.get_kill_switch_status(user.id)
            == redis_client.KILL_SWITCH_TRIPPED
        )

    async def test_event_written(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        credential: BrokerCredential,
        svc: KillSwitchService,
    ) -> None:
        broker = _FakeBroker()
        await redis_client.set_daily_pnl(user.id, Decimal("-6000"))
        result = await svc.check_and_trigger(
            user.id, session, broker_factory=_factory({credential.id: broker})
        )
        from sqlalchemy import select

        row = (
            await session.execute(
                select(KillSwitchEvent).where(KillSwitchEvent.id == result.event_id)
            )
        ).scalar_one()
        assert row.reason == TripReason.DAILY_LOSS_BREACHED.value

    async def test_broker_failure_collected_not_raised(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        credential: BrokerCredential,
        strategy: Strategy,
        svc: KillSwitchService,
    ) -> None:
        await _seed_open_position(
            session, user=user, strategy=strategy, credential=credential
        )
        broker = _FakeBroker(place_order_fail=True)
        await redis_client.set_daily_pnl(user.id, Decimal("-6000"))
        result = await svc.check_and_trigger(
            user.id, session, broker_factory=_factory({credential.id: broker})
        )
        assert result.triggered is True
        assert result.errors
        assert result.actions[0].error is not None
        assert result.actions[0].positions_squared_off == 0

    async def test_disabled_never_triggers(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        svc: KillSwitchService,
    ) -> None:
        # Fresh config row with enabled=False — avoids fixture relationship issues.
        session.add(
            KillSwitchConfig(
                user_id=user.id,
                max_daily_loss_inr=Decimal("5000"),
                max_daily_trades=10,
                enabled=False,
                auto_square_off=False,
            )
        )
        await session.flush()
        await redis_client.set_daily_pnl(user.id, Decimal("-50000"))
        result = await svc.check_and_trigger(user.id, session)
        assert result.triggered is False

    async def test_no_positions_graceful(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        svc: KillSwitchService,
    ) -> None:
        # No credential → nothing to close. Should still fire the trip.
        await redis_client.set_daily_pnl(user.id, Decimal("-6000"))
        result = await svc.check_and_trigger(user.id, session)
        assert result.triggered is True
        assert result.actions == []


# ═══════════════════════════════════════════════════════════════════════
# Layer 1 gate + Layer 2 scoped close (2026-05-10)
# ═══════════════════════════════════════════════════════════════════════


class TestScopedSquareOff:
    """Verifies the Friday-2026-05-08-incident architectural fix.

    Layer 1: ``auto_square_off=False`` in config gates the broker call.
    Layer 2: when broker call is allowed, only ``strategy_positions``
    rows are closed — personal broker positions are untouched (we
    don't even fetch them).
    """

    async def test_layer1_gate_skips_broker_when_auto_off(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        credential: BrokerCredential,
        strategy: Strategy,
        svc: KillSwitchService,
    ) -> None:
        session.add(
            KillSwitchConfig(
                user_id=user.id,
                max_daily_loss_inr=Decimal("5000"),
                max_daily_trades=10,
                enabled=True,
                auto_square_off=False,
            )
        )
        await session.flush()
        await _seed_open_position(
            session, user=user, strategy=strategy, credential=credential
        )
        broker = _FakeBroker()
        await redis_client.set_daily_pnl(user.id, Decimal("-6000"))
        result = await svc.check_and_trigger(
            user.id, session, broker_factory=_factory({credential.id: broker})
        )
        assert result.triggered is True
        assert result.actions == []
        assert result.errors == []
        # Critical: broker.place_order MUST NOT have been called.
        assert broker.place_order_calls == []

    async def test_layer2_no_open_positions_no_broker_call(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        credential: BrokerCredential,
        svc: KillSwitchService,
    ) -> None:
        broker = _FakeBroker()
        await redis_client.set_daily_pnl(user.id, Decimal("-6000"))
        result = await svc.check_and_trigger(
            user.id, session, broker_factory=_factory({credential.id: broker})
        )
        assert result.triggered is True
        assert result.actions == []
        # No system positions => broker untouched. Personal positions safe.
        assert broker.place_order_calls == []

    async def test_layer2_closes_long_via_sell_market(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        credential: BrokerCredential,
        strategy: Strategy,
        svc: KillSwitchService,
    ) -> None:
        pos = await _seed_open_position(
            session,
            user=user,
            strategy=strategy,
            credential=credential,
            side="buy",
            qty=75,
        )
        broker = _FakeBroker()
        await redis_client.set_daily_pnl(user.id, Decimal("-6000"))
        result = await svc.check_and_trigger(
            user.id, session, broker_factory=_factory({credential.id: broker})
        )
        assert result.triggered is True
        assert result.actions[0].positions_squared_off == 1
        assert len(broker.place_order_calls) == 1
        call = broker.place_order_calls[0]
        assert call.side is OrderSide.SELL
        assert call.quantity == 75
        assert call.order_type is OrderType.MARKET
        assert call.product_type is ProductType.INTRADAY
        assert call.tag == "kill-switch"
        await session.refresh(pos)
        assert pos.status == "closed"
        assert pos.remaining_quantity == 0
        assert pos.exit_reason == "kill_switch"
        assert pos.last_action == "kill_switch"
        # broker info captured in action_history (broker_exit_response
        # column is unmapped on ORM today — see service note).
        kill_event = next(
            h for h in pos.action_history if h["action"] == "kill_switch"
        )
        assert kill_event["broker_order_id"]
        assert kill_event["broker_status"]

    async def test_layer2_closes_short_via_buy_market(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        credential: BrokerCredential,
        strategy: Strategy,
        svc: KillSwitchService,
    ) -> None:
        await _seed_open_position(
            session,
            user=user,
            strategy=strategy,
            credential=credential,
            side="sell",
            qty=50,
        )
        broker = _FakeBroker()
        await redis_client.set_daily_pnl(user.id, Decimal("-6000"))
        await svc.check_and_trigger(
            user.id, session, broker_factory=_factory({credential.id: broker})
        )
        assert broker.place_order_calls[0].side is OrderSide.BUY
        assert broker.place_order_calls[0].quantity == 50

    async def test_layer2_continues_on_per_position_failure(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        credential: BrokerCredential,
        strategy: Strategy,
        svc: KillSwitchService,
    ) -> None:
        await _seed_open_position(
            session, user=user, strategy=strategy, credential=credential,
            symbol="NIFTY1", side="buy", qty=75,
        )
        await _seed_open_position(
            session, user=user, strategy=strategy, credential=credential,
            symbol="NIFTY2", side="sell", qty=25,
        )
        broker = _FakeBroker(place_order_fail=True)
        await redis_client.set_daily_pnl(user.id, Decimal("-6000"))
        result = await svc.check_and_trigger(
            user.id, session, broker_factory=_factory({credential.id: broker})
        )
        # Trip fired; both attempted; both failed; trip not aborted.
        assert result.triggered is True
        assert len(broker.place_order_calls) == 2
        assert result.actions[0].positions_squared_off == 0
        assert result.actions[0].error is not None
        assert "NIFTY1" in result.actions[0].error
        assert "NIFTY2" in result.actions[0].error


# ═══════════════════════════════════════════════════════════════════════
# Paper-mode square-off (safety fix #2)
# ═══════════════════════════════════════════════════════════════════════


class TestPaperModeSquareOff:
    """Kill switch trips while ``strategy_paper_mode=True`` must close
    positions in DB only — no broker login, no ``broker.place_order``.
    The module-level autouse fixture forces paper OFF; this nested
    autouse re-enables it for this class only."""

    @pytest.fixture(autouse=True)
    def _force_paper_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.core.config import get_settings

        monkeypatch.setenv("STRATEGY_PAPER_MODE", "true")
        get_settings.cache_clear()

    async def test_kill_switch_paper_mode_no_broker_call(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        credential: BrokerCredential,
        strategy: Strategy,
        svc: KillSwitchService,
    ) -> None:
        """Broker is NEVER touched in paper mode."""
        await _seed_open_position(
            session, user=user, strategy=strategy, credential=credential,
            side="buy", qty=75,
        )
        broker = _FakeBroker()
        await redis_client.set_daily_pnl(user.id, Decimal("-6000"))

        result = await svc.check_and_trigger(
            user.id, session, broker_factory=_factory({credential.id: broker})
        )

        assert result.triggered is True
        assert broker.place_order_calls == []
        assert broker.login_called is False
        # Result still surfaces the action so the caller's audit row is
        # populated with positions_squared_off > 0.
        assert len(result.actions) == 1
        assert result.actions[0].positions_squared_off == 1
        assert result.actions[0].error is None
        assert result.errors == []

    async def test_kill_switch_paper_mode_positions_closed_in_db(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        credential: BrokerCredential,
        strategy: Strategy,
        svc: KillSwitchService,
    ) -> None:
        """Each position's state mutation mirrors the live path: status
        flips to ``closed``, ``remaining_quantity`` zeroed,
        ``exit_reason='kill_switch'``, paper marker in action_history."""
        pos = await _seed_open_position(
            session, user=user, strategy=strategy, credential=credential,
            side="buy", qty=75,
        )
        await redis_client.set_daily_pnl(user.id, Decimal("-6000"))

        await svc.check_and_trigger(
            user.id, session, broker_factory=_factory({credential.id: _FakeBroker()})
        )
        await session.refresh(pos)

        assert pos.status == "closed"
        assert pos.remaining_quantity == 0
        assert pos.exit_reason == "kill_switch"
        assert pos.last_action == "kill_switch"
        assert pos.closed_at is not None
        # action_history carries the paper-mode marker + synthetic id.
        history = pos.action_history or []
        kill_event = next(h for h in history if h["action"] == "kill_switch")
        assert kill_event["paper_mode"] is True
        assert kill_event["broker_order_id"].startswith("PAPER-KILL-SWITCH-")
        assert kill_event["broker_status"] == "complete"
        # Sell side recorded (long → close via sell).
        assert kill_event["side"] == "sell"
        assert kill_event["qty"] == 75

    async def test_kill_switch_paper_mode_audit_event_written(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        credential: BrokerCredential,
        strategy: Strategy,
        svc: KillSwitchService,
    ) -> None:
        """The caller (``check_and_trigger``) writes a
        :class:`KillSwitchEvent` row regardless of paper/live mode —
        verify the audit trail survives the paper short-circuit."""
        await _seed_open_position(
            session, user=user, strategy=strategy, credential=credential,
            side="buy", qty=50,
        )
        await redis_client.set_daily_pnl(user.id, Decimal("-7000"))

        await svc.check_and_trigger(
            user.id, session, broker_factory=_factory({credential.id: _FakeBroker()})
        )

        from sqlalchemy import select as _select

        events = (
            await session.execute(
                _select(KillSwitchEvent).where(KillSwitchEvent.user_id == user.id)
            )
        ).scalars().all()
        assert len(events) == 1
        event = events[0]
        # positions_squared_off list carries one entry with the paper count.
        assert event.positions_squared_off
        assert event.positions_squared_off[0]["positions_squared_off"] == 1

    async def test_kill_switch_paper_mode_no_open_positions_returns_empty(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        credential: BrokerCredential,
        svc: KillSwitchService,
    ) -> None:
        """Edge case: paper mode + no open positions → no broker call,
        no paper close, ``actions=[]`` (matches live-mode behaviour)."""
        broker = _FakeBroker()
        await redis_client.set_daily_pnl(user.id, Decimal("-6000"))
        result = await svc.check_and_trigger(
            user.id, session, broker_factory=_factory({credential.id: broker})
        )
        assert result.triggered is True
        assert result.actions == []
        assert broker.place_order_calls == []
        assert broker.login_called is False


# ═══════════════════════════════════════════════════════════════════════
# Max daily trades
# ═══════════════════════════════════════════════════════════════════════


class TestMaxDailyTrades:
    async def test_under_limit_allows(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        svc: KillSwitchService,
    ) -> None:
        for _ in range(5):
            await svc.increment_daily_trades(user.id)
        ok, count, cap = await svc.check_max_daily_trades(user.id, session)
        assert ok is True
        assert count == 5
        assert cap == 10

    async def test_at_limit_rejects(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        svc: KillSwitchService,
    ) -> None:
        for _ in range(10):
            await svc.increment_daily_trades(user.id)
        ok, *_ = await svc.check_max_daily_trades(user.id, session)
        assert ok is False

    async def test_no_config_is_pass(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        svc: KillSwitchService,
    ) -> None:
        ok, count, cap = await svc.check_max_daily_trades(user.id, session)
        assert ok is True


# ═══════════════════════════════════════════════════════════════════════
# Manual reset
# ═══════════════════════════════════════════════════════════════════════


class TestReset:
    async def test_reset_without_token(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        svc: KillSwitchService,
    ) -> None:
        with pytest.raises(PermissionError):
            await svc.manual_reset(
                user.id,
                reset_by=user.id,
                confirmation_token="invalid",
                session=session,
            )

    async def test_reset_wrong_token(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        svc: KillSwitchService,
    ) -> None:
        await svc.create_reset_token(user.id)
        with pytest.raises(PermissionError):
            await svc.manual_reset(
                user.id,
                reset_by=user.id,
                confirmation_token="wrong-token-still-long-enough",
                session=session,
            )

    async def test_reset_happy_path(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        credential: BrokerCredential,
        svc: KillSwitchService,
    ) -> None:
        broker = _FakeBroker()
        await redis_client.set_daily_pnl(user.id, Decimal("-6000"))
        await svc.check_and_trigger(
            user.id, session, broker_factory=_factory({credential.id: broker})
        )
        token = await svc.create_reset_token(user.id)
        await svc.manual_reset(
            user.id,
            reset_by=user.id,
            confirmation_token=token,
            session=session,
        )
        # Redis state cleared.
        assert (
            await redis_client.get_kill_switch_status(user.id)
            == redis_client.KILL_SWITCH_ACTIVE
        )
        assert await redis_client.get_daily_pnl(user.id) == Decimal("0")


# ═══════════════════════════════════════════════════════════════════════
# Simulation
# ═══════════════════════════════════════════════════════════════════════


class TestSimulation:
    async def test_dry_run_no_side_effects(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        svc: KillSwitchService,
    ) -> None:
        await redis_client.set_daily_pnl(user.id, Decimal("-6000"))
        res = await svc.test_trip(user.id, session)
        assert res.would_trigger is True
        assert res.reason is TripReason.DAILY_LOSS_BREACHED
        # Real state untouched.
        assert (
            await redis_client.get_kill_switch_status(user.id)
            == redis_client.KILL_SWITCH_ACTIVE
        )


# ═══════════════════════════════════════════════════════════════════════
# Daily jobs
# ═══════════════════════════════════════════════════════════════════════


class TestDailyJobs:
    async def test_daily_reset_clears_keys(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        svc: KillSwitchService,
    ) -> None:
        await redis_client.set_daily_pnl(user.id, Decimal("-1000"))
        await svc.increment_daily_trades(user.id)
        removed = await svc.daily_reset_all(session)
        assert removed >= 2

    async def test_auto_square_off_intraday(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        config: KillSwitchConfig,
        credential: BrokerCredential,
        svc: KillSwitchService,
    ) -> None:
        broker = _FakeBroker(squared=1)
        touched = await svc.auto_square_off_intraday(
            session, broker_factory=_factory({credential.id: broker})
        )
        assert user.id in touched


class TestTripHistory:
    async def test_returns_events_sorted(
        self,
        redis: fake_aioredis.FakeRedis,
        session: AsyncSession,
        user: User,
        svc: KillSwitchService,
    ) -> None:
        for pnl in (-10_000, -20_000, -30_000):
            event = KillSwitchEvent(
                user_id=user.id,
                reason="daily_loss_breached",
                daily_pnl_at_trigger=Decimal(pnl),
                positions_squared_off=[],
            )
            session.add(event)
        await session.flush()
        events = await svc.get_trip_history(user.id, session, limit=2)
        assert len(events) == 2


# ═══════════════════════════════════════════════════════════════════════
# Cleanup helper
# ═══════════════════════════════════════════════════════════════════════


class TestIdempotencyCleanup:
    async def test_deletes_expired(
        self,
        session: AsyncSession,
        user: User,
    ) -> None:
        from app.db.models.idempotency import IdempotencyKey

        session.add(
            IdempotencyKey(
                user_id=user.id,
                signal_hash="expired",
                expires_at=datetime(2020, 1, 1, tzinfo=UTC),
            )
        )
        session.add(
            IdempotencyKey(
                user_id=user.id,
                signal_hash="fresh",
                expires_at=datetime(2099, 1, 1, tzinfo=UTC),
            )
        )
        await session.flush()
        removed = await delete_expired_idempotency(session)
        assert removed == 1
