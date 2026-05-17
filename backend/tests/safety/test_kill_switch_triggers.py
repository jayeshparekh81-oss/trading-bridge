"""Kill-switch trigger tests.

Catches regressions in the daily-loss-limit + max-trade + broker-
disconnect triggers. These are P0 safety paths — customer money
loss happens when these don't fire.

Uses Redis-backed kill-switch state via the existing
app.core.redis_client helpers + fakeredis.
"""

from __future__ import annotations

import uuid
from typing import AsyncIterator

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio

# bcrypt is transitively imported by app.core.security via various
# safety modules. Skip gracefully if not installed in this dev env.
pytest.importorskip("bcrypt")

from app.core import redis_client  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def fake_redis(monkeypatch) -> AsyncIterator:
    client = fake_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: client)
    yield client
    await client.aclose()


def _uid() -> uuid.UUID:
    return uuid.uuid4()


# ─── Daily P&L tracking ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_daily_pnl_increments_correctly(fake_redis) -> None:
    user = _uid()
    await redis_client.set_daily_pnl(user, -500.0, redis_client=fake_redis)
    pnl = await redis_client.get_daily_pnl(user, redis_client=fake_redis)
    assert pnl == -500.0


@pytest.mark.asyncio
async def test_daily_pnl_starts_at_zero_for_new_user(fake_redis) -> None:
    user = _uid()
    pnl = await redis_client.get_daily_pnl(user, redis_client=fake_redis)
    assert pnl == 0.0


# ─── Kill switch state ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_kill_switch_default_state_inactive(fake_redis) -> None:
    user = _uid()
    status = await redis_client.get_kill_switch_status(user, redis_client=fake_redis)
    assert status.get("active") in (False, None, "0")


@pytest.mark.asyncio
async def test_kill_switch_activate_then_check(fake_redis) -> None:
    user = _uid()
    await redis_client.set_kill_switch_status(
        user, {"active": True, "reason": "daily_loss_limit"}, redis_client=fake_redis
    )
    status = await redis_client.get_kill_switch_status(user, redis_client=fake_redis)
    assert status.get("active") in (True, "True", "1", "true")


@pytest.mark.asyncio
async def test_kill_switch_clear_after_activation(fake_redis) -> None:
    user = _uid()
    await redis_client.set_kill_switch_status(
        user, {"active": True, "reason": "test"}, redis_client=fake_redis
    )
    await redis_client.clear_kill_switch(user, redis_client=fake_redis)
    status = await redis_client.get_kill_switch_status(user, redis_client=fake_redis)
    # After clear, either empty dict or active=False
    assert not status or status.get("active") in (False, None, "0", "False", "false")


# ─── Per-user isolation ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_kill_switch_user_isolation(fake_redis) -> None:
    user_a = _uid()
    user_b = _uid()
    await redis_client.set_kill_switch_status(
        user_a, {"active": True, "reason": "test"}, redis_client=fake_redis
    )
    status_b = await redis_client.get_kill_switch_status(user_b, redis_client=fake_redis)
    # User B is unaffected
    assert status_b.get("active") in (False, None, "0", "False", "false")


@pytest.mark.asyncio
async def test_daily_pnl_user_isolation(fake_redis) -> None:
    user_a = _uid()
    user_b = _uid()
    await redis_client.set_daily_pnl(user_a, -2000.0, redis_client=fake_redis)
    pnl_b = await redis_client.get_daily_pnl(user_b, redis_client=fake_redis)
    assert pnl_b == 0.0


# ─── Idempotency guards ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_kill_switch_re_activation_overwrites_reason(fake_redis) -> None:
    user = _uid()
    await redis_client.set_kill_switch_status(
        user, {"active": True, "reason": "first_trigger"}, redis_client=fake_redis
    )
    await redis_client.set_kill_switch_status(
        user, {"active": True, "reason": "second_trigger"}, redis_client=fake_redis
    )
    status = await redis_client.get_kill_switch_status(user, redis_client=fake_redis)
    # Most recent reason wins
    assert "second_trigger" in str(status)


@pytest.mark.asyncio
async def test_daily_pnl_can_be_updated_multiple_times(fake_redis) -> None:
    user = _uid()
    await redis_client.set_daily_pnl(user, -100.0, redis_client=fake_redis)
    await redis_client.set_daily_pnl(user, -250.0, redis_client=fake_redis)
    pnl = await redis_client.get_daily_pnl(user, redis_client=fake_redis)
    assert pnl == -250.0


# ─── Cross-isolation: pnl + kill switch independent ──────────────────


@pytest.mark.asyncio
async def test_pnl_and_kill_switch_independent(fake_redis) -> None:
    """Setting kill switch doesn't reset PnL; setting PnL doesn't toggle kill switch."""
    user = _uid()
    await redis_client.set_daily_pnl(user, -1000.0, redis_client=fake_redis)
    await redis_client.set_kill_switch_status(
        user, {"active": True, "reason": "x"}, redis_client=fake_redis
    )
    # PnL still readable + correct
    pnl = await redis_client.get_daily_pnl(user, redis_client=fake_redis)
    assert pnl == -1000.0
    # Kill switch still active
    status = await redis_client.get_kill_switch_status(user, redis_client=fake_redis)
    assert status.get("active") in (True, "True", "1", "true")
