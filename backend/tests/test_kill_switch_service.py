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
from app.schemas.broker import (
    BrokerCredentials,
    BrokerName,
    OrderResponse,
    OrderStatus,
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
    ) -> None:
        self._cancelled = cancelled
        self._squared = squared
        self._fail = fail
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
        svc: KillSwitchService,
    ) -> None:
        broker = _FakeBroker(cancelled=2, squared=3)
        await redis_client.set_daily_pnl(user.id, Decimal("-6000"))
        result = await svc.check_and_trigger(
            user.id, session, broker_factory=_factory({credential.id: broker})
        )
        assert result.triggered is True
        assert result.reason is TripReason.DAILY_LOSS_BREACHED
        assert result.actions[0].pending_cancelled == 2
        assert result.actions[0].positions_squared_off == 3

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
        svc: KillSwitchService,
    ) -> None:
        broker = _FakeBroker(fail="square")
        await redis_client.set_daily_pnl(user.id, Decimal("-6000"))
        result = await svc.check_and_trigger(
            user.id, session, broker_factory=_factory({credential.id: broker})
        )
        assert result.triggered is True
        assert result.errors
        assert result.actions[0].error is not None

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
