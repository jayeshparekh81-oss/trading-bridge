"""Tests for the Celery task layer.

Tasks are sync wrappers around async coroutines. We run them with
``.apply()`` (synchronous execution) and patch the DB sessionmaker +
Redis to use the same fakeredis instance the async code sees.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
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
from app.db.base import Base
from app.db.models.kill_switch import KillSwitchConfig
from app.db.models.user import User
from app.tasks import kill_switch_tasks


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    m = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield m
    await engine.dispose()


@pytest.fixture
def fake_redis() -> Iterator[fake_aioredis.FakeRedis]:
    client = fake_aioredis.FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        import asyncio

        asyncio.get_event_loop().run_until_complete(client.aclose())


@pytest.fixture(autouse=True)
def _wire(
    monkeypatch: pytest.MonkeyPatch,
    maker: async_sessionmaker[AsyncSession],
    fake_redis: fake_aioredis.FakeRedis,
) -> None:
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake_redis)
    monkeypatch.setattr("app.db.session.get_sessionmaker", lambda: maker)


@pytest.fixture
def celery_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run every @shared_task eagerly in-process (no broker needed)."""
    from app.tasks.celery_app import celery_app

    celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)


# ═══════════════════════════════════════════════════════════════════════
# Individual tasks
# ═══════════════════════════════════════════════════════════════════════


class TestDailyReset:
    async def test_reset_all(
        self,
        celery_sync: None,
        maker: async_sessionmaker[AsyncSession],
        fake_redis: fake_aioredis.FakeRedis,
    ) -> None:
        # Seed some user-scoped keys.
        from uuid import uuid4

        uid = uuid4()
        await redis_client.set_daily_pnl(uid, Decimal("-500"))
        await fake_redis.set(f"daily_trades:{uid}", 5)

        result = kill_switch_tasks.daily_pnl_reset.apply().get()
        assert result["keys_removed"] >= 1


class TestAutoSquareOff:
    async def test_runs(
        self,
        celery_sync: None,
        maker: async_sessionmaker[AsyncSession],
    ) -> None:
        async with maker() as s:
            u = User(email="a@x", password_hash="p", is_active=True)
            s.add(u)
            await s.flush()
            s.add(
                KillSwitchConfig(
                    user_id=u.id,
                    max_daily_loss_inr=Decimal("1000"),
                    max_daily_trades=5,
                    enabled=True,
                    auto_square_off=True,
                )
            )
            await s.commit()
        result = kill_switch_tasks.auto_square_off_intraday.apply().get()
        assert "users_touched" in result


class TestMarketStatus:
    async def test_status_written(
        self,
        celery_sync: None,
        fake_redis: fake_aioredis.FakeRedis,
    ) -> None:
        result = kill_switch_tasks.check_market_status.apply().get()
        assert result["status"] in ("open", "closed")
        assert await fake_redis.get("market:status") == result["status"]


class TestCleanupSessions:
    async def test_sweep(
        self,
        celery_sync: None,
        fake_redis: fake_aioredis.FakeRedis,
    ) -> None:
        # Pre-seed one expired-ish key (fakeredis supports TTLs).
        await fake_redis.set("session_blacklist:alive", "1", ex=60)
        result = kill_switch_tasks.cleanup_expired_sessions.apply().get()
        assert "scanned" in result
        assert "removed" in result


class TestRotateIdempotency:
    async def test_removes_expired(
        self,
        celery_sync: None,
        maker: async_sessionmaker[AsyncSession],
    ) -> None:
        from uuid import uuid4

        from app.db.models.idempotency import IdempotencyKey

        async with maker() as s:
            u = User(email="a@x", password_hash="p", is_active=True)
            s.add(u)
            await s.flush()
            s.add(
                IdempotencyKey(
                    user_id=u.id,
                    signal_hash=f"e-{uuid4()}",
                    expires_at=datetime(2020, 1, 1, tzinfo=UTC),
                )
            )
            await s.commit()

        result = kill_switch_tasks.rotate_idempotency_keys.apply().get()
        assert result["rows_removed"] >= 1


class TestEmergencySquareOff:
    async def test_invokes_service(
        self,
        celery_sync: None,
        maker: async_sessionmaker[AsyncSession],
        fake_redis: fake_aioredis.FakeRedis,
    ) -> None:
        async with maker() as s:
            u = User(email="a@x", password_hash="p", is_active=True)
            s.add(u)
            await s.flush()
            s.add(
                KillSwitchConfig(
                    user_id=u.id,
                    max_daily_loss_inr=Decimal("100"),
                    max_daily_trades=5,
                    enabled=True,
                    auto_square_off=True,
                )
            )
            await s.commit()
            uid = u.id
        await redis_client.set_daily_pnl(uid, Decimal("-500"))
        result = (
            kill_switch_tasks.execute_emergency_square_off.apply(
                args=[str(uid)]
            ).get()
        )
        # Service returns a KillSwitchResult — serialised.
        assert "triggered" in result


class TestNotification:
    def test_queue_payload_shape(
        self, celery_sync: None
    ) -> None:
        payload = kill_switch_tasks.send_kill_switch_notification.apply(
            args=["u-1", {"reason": "test"}]
        ).get()
        assert payload["user_id"] == "u-1"
        assert "email" in payload["channels"]


class TestDailyReport:
    async def test_generates_per_user(
        self,
        celery_sync: None,
        maker: async_sessionmaker[AsyncSession],
        fake_redis: fake_aioredis.FakeRedis,
    ) -> None:
        async with maker() as s:
            u = User(email="a@x", password_hash="p", is_active=True)
            s.add(u)
            await s.flush()
            s.add(
                KillSwitchConfig(
                    user_id=u.id,
                    max_daily_loss_inr=Decimal("1000"),
                    max_daily_trades=5,
                    enabled=True,
                    auto_square_off=True,
                )
            )
            await s.commit()

        result = kill_switch_tasks.generate_daily_trade_report.apply().get()
        assert result["users"]


# ═══════════════════════════════════════════════════════════════════════
# Celery wiring
# ═══════════════════════════════════════════════════════════════════════


class TestCeleryApp:
    def test_beat_schedule_populated(self) -> None:
        from app.tasks.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        assert "daily-pnl-reset" in schedule
        assert "auto-square-off" in schedule
        assert "check-market-status" in schedule

    def test_tasks_registered(self) -> None:
        from app.tasks.celery_app import celery_app

        registered = celery_app.tasks
        assert "app.tasks.kill_switch_tasks.daily_pnl_reset" in registered
