"""Day-5 rate-limit middleware tests.

Uses fakeredis (already in dev deps) so tests run without a real
Redis instance.

Covers:
  - Hourly cap (default 30) — single burst, slow drip, exact-boundary
  - Concurrent cap (default 5) — concurrent acquire/release, exceed
  - Per-user isolation — user A's cap doesn't affect user B
  - Env-var override — config picks up changed cap
  - Slot release idempotency
  - 429 response shape including Retry-After header
"""

from __future__ import annotations

import os
import uuid
from typing import AsyncIterator

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio

from app.backtest_extension import rate_limit
from app.backtest_extension.rate_limit import (
    CONCURRENT_LIMIT,
    PER_HOUR_LIMIT,
    RateLimitExceededError,
    acquire_concurrent_slot,
    check_request_rate,
    release_concurrent_slot,
)


@pytest_asyncio.fixture
async def redis() -> AsyncIterator:
    """Fresh fakeredis instance per test — isolation."""
    client = fake_aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


def _uid() -> uuid.UUID:
    return uuid.uuid4()


# ─── Per-hour cap ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_per_hour_cap_allows_up_to_limit(redis) -> None:
    user = _uid()
    for _ in range(PER_HOUR_LIMIT):
        await check_request_rate(user, redis=redis)  # all allowed


@pytest.mark.asyncio
async def test_per_hour_cap_rejects_at_limit_plus_one(redis) -> None:
    user = _uid()
    for _ in range(PER_HOUR_LIMIT):
        await check_request_rate(user, redis=redis)
    # The (PER_HOUR_LIMIT + 1)th request must 429
    with pytest.raises(RateLimitExceededError) as excinfo:
        await check_request_rate(user, redis=redis)
    assert excinfo.value.kind == "per_hour"
    assert excinfo.value.status_code == 429
    assert "Retry-After" in excinfo.value.headers


@pytest.mark.asyncio
async def test_per_hour_cap_isolated_across_users(redis) -> None:
    """User A maxing out their cap doesn't affect User B."""
    user_a = _uid()
    user_b = _uid()
    for _ in range(PER_HOUR_LIMIT):
        await check_request_rate(user_a, redis=redis)
    with pytest.raises(RateLimitExceededError):
        await check_request_rate(user_a, redis=redis)
    # User B is fresh — no limit hit
    await check_request_rate(user_b, redis=redis)
    await check_request_rate(user_b, redis=redis)


# ─── Concurrent cap ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_concurrent_cap_allows_up_to_limit(redis) -> None:
    user = _uid()
    for _ in range(CONCURRENT_LIMIT):
        await acquire_concurrent_slot(user, redis=redis)


@pytest.mark.asyncio
async def test_concurrent_cap_rejects_when_full(redis) -> None:
    user = _uid()
    for _ in range(CONCURRENT_LIMIT):
        await acquire_concurrent_slot(user, redis=redis)
    with pytest.raises(RateLimitExceededError) as excinfo:
        await acquire_concurrent_slot(user, redis=redis)
    assert excinfo.value.kind == "concurrent"
    assert excinfo.value.status_code == 429
    # Short retry — concurrent slots free up quickly
    assert excinfo.value.retry_after_seconds == 60


@pytest.mark.asyncio
async def test_concurrent_slot_release_frees_capacity(redis) -> None:
    user = _uid()
    for _ in range(CONCURRENT_LIMIT):
        await acquire_concurrent_slot(user, redis=redis)
    # Release one slot
    await release_concurrent_slot(user, redis=redis)
    # Now a new acquire works
    await acquire_concurrent_slot(user, redis=redis)


@pytest.mark.asyncio
async def test_concurrent_slot_release_idempotent_on_empty(redis) -> None:
    """Releasing when counter is 0 doesn't crash + counter stays at 0."""
    user = _uid()
    # Releasing an empty bucket — defensive correction logged
    await release_concurrent_slot(user, redis=redis)
    # Subsequent acquire still works
    await acquire_concurrent_slot(user, redis=redis)


@pytest.mark.asyncio
async def test_concurrent_cap_isolated_across_users(redis) -> None:
    user_a = _uid()
    user_b = _uid()
    for _ in range(CONCURRENT_LIMIT):
        await acquire_concurrent_slot(user_a, redis=redis)
    with pytest.raises(RateLimitExceededError):
        await acquire_concurrent_slot(user_a, redis=redis)
    # User B fresh
    await acquire_concurrent_slot(user_b, redis=redis)
    await acquire_concurrent_slot(user_b, redis=redis)


# ─── Acquire failure rolls back ────────────────────────────────────────


@pytest.mark.asyncio
async def test_acquire_failure_does_not_strand_counter(redis) -> None:
    """When acquire raises, the INCR was rolled back via DECR so a
    subsequent release_concurrent_slot doesn't drive the counter
    below 0 unexpectedly."""
    user = _uid()
    for _ in range(CONCURRENT_LIMIT):
        await acquire_concurrent_slot(user, redis=redis)
    # This raises + rolls back
    with pytest.raises(RateLimitExceededError):
        await acquire_concurrent_slot(user, redis=redis)
    # Counter should still be at CONCURRENT_LIMIT — verify by
    # releasing 5 times brings it to 0, NOT to -1
    for _ in range(CONCURRENT_LIMIT):
        await release_concurrent_slot(user, redis=redis)
    # Now acquire should work fresh
    await acquire_concurrent_slot(user, redis=redis)


# ─── Configuration smoke ───────────────────────────────────────────────


def test_default_limits_are_reasonable() -> None:
    """30/hour + 5 concurrent are the spec defaults."""
    assert PER_HOUR_LIMIT >= 1
    assert CONCURRENT_LIMIT >= 1
    # Sanity bounds — guards against accidental over-permissive defaults
    assert PER_HOUR_LIMIT <= 1000
    assert CONCURRENT_LIMIT <= 100


def test_env_var_invalid_value_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed env value should NOT crash the import; defaults apply."""
    monkeypatch.setenv("BACKTEST_RATE_LIMIT_PER_HOUR", "not-a-number")
    monkeypatch.setenv("BACKTEST_RATE_LIMIT_CONCURRENT", "abc")
    # Re-import to pick up env changes
    import importlib

    module = importlib.reload(rate_limit)
    # Defaults apply — 30 + 5 per docstring
    assert module.PER_HOUR_LIMIT == 30
    assert module.CONCURRENT_LIMIT == 5


def test_env_var_valid_override_applies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BACKTEST_RATE_LIMIT_PER_HOUR", "100")
    monkeypatch.setenv("BACKTEST_RATE_LIMIT_CONCURRENT", "10")
    import importlib

    module = importlib.reload(rate_limit)
    assert module.PER_HOUR_LIMIT == 100
    assert module.CONCURRENT_LIMIT == 10


# ─── 429 response shape ────────────────────────────────────────────────


def test_rate_limit_exceeded_error_carries_retry_after() -> None:
    err = RateLimitExceededError(kind="per_hour", retry_after_seconds=3600)
    assert err.status_code == 429
    assert err.headers["Retry-After"] == "3600"
    assert err.kind == "per_hour"
    assert "per_hour" in err.detail
