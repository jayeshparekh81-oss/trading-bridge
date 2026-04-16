"""Tests for :mod:`app.core.redis_client`.

Uses ``fakeredis.aioredis`` — a fast in-memory stand-in that respects
Redis semantics (TTLs, NX, pipelines). Network-less and deterministic.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from uuid import uuid4

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio

from app.core import redis_client


@pytest_asyncio.fixture
async def redis() -> AsyncIterator[fake_aioredis.FakeRedis]:
    client = fake_aioredis.FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


# ═══════════════════════════════════════════════════════════════════════
# Connection pool singleton
# ═══════════════════════════════════════════════════════════════════════


class TestConnectionPool:
    def test_get_redis_is_cached(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = {"n": 0}

        def fake_from_url(*_a: object, **_kw: object) -> object:
            calls["n"] += 1
            return object()

        monkeypatch.setattr("redis.asyncio.from_url", fake_from_url)
        redis_client.get_redis.cache_clear()
        a = redis_client.get_redis()
        b = redis_client.get_redis()
        assert a is b
        assert calls["n"] == 1
        redis_client.get_redis.cache_clear()

    async def test_close_redis_drops_cache(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dummy = fake_aioredis.FakeRedis(decode_responses=True)
        monkeypatch.setattr(
            "redis.asyncio.from_url", lambda *a, **kw: dummy
        )
        redis_client.get_redis.cache_clear()
        _ = redis_client.get_redis()
        await redis_client.close_redis()
        assert redis_client.get_redis.cache_info().currsize == 0


# ═══════════════════════════════════════════════════════════════════════
# Cache helpers
# ═══════════════════════════════════════════════════════════════════════


class TestCache:
    async def test_set_and_get(self, redis: fake_aioredis.FakeRedis) -> None:
        await redis_client.cache_set("k1", "v1", ttl_seconds=60, redis_client=redis)
        assert await redis_client.cache_get("k1", redis_client=redis) == "v1"

    async def test_get_missing_returns_none(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        assert await redis_client.cache_get("missing", redis_client=redis) is None

    async def test_delete(self, redis: fake_aioredis.FakeRedis) -> None:
        await redis_client.cache_set("k", "v", ttl_seconds=60, redis_client=redis)
        assert await redis_client.cache_delete("k", redis_client=redis) is True
        assert await redis_client.cache_delete("k", redis_client=redis) is False

    async def test_set_rejects_non_positive_ttl(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        with pytest.raises(ValueError, match="ttl_seconds must be positive"):
            await redis_client.cache_set("k", "v", ttl_seconds=0, redis_client=redis)

    async def test_set_get_json(self, redis: fake_aioredis.FakeRedis) -> None:
        payload = {"a": 1, "b": [2, 3]}
        await redis_client.cache_set_json(
            "j", payload, ttl_seconds=60, redis_client=redis
        )
        assert await redis_client.cache_get_json("j", redis_client=redis) == payload

    async def test_get_json_miss_returns_none(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        assert await redis_client.cache_get_json("miss", redis_client=redis) is None

    async def test_get_json_handles_corrupt(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        await redis.set(f"cache:bad", "not-json")
        assert await redis_client.cache_get_json("bad", redis_client=redis) is None


# ═══════════════════════════════════════════════════════════════════════
# Rate limiting
# ═══════════════════════════════════════════════════════════════════════


class TestRateLimit:
    async def test_allows_up_to_max(self, redis: fake_aioredis.FakeRedis) -> None:
        for _ in range(3):
            ok = await redis_client.rate_limit_check(
                "user:1", max_requests=3, window_seconds=60, redis_client=redis
            )
            assert ok is True

    async def test_rejects_over_max(self, redis: fake_aioredis.FakeRedis) -> None:
        for _ in range(3):
            await redis_client.rate_limit_check(
                "user:1", max_requests=3, window_seconds=60, redis_client=redis
            )
        ok = await redis_client.rate_limit_check(
            "user:1", max_requests=3, window_seconds=60, redis_client=redis
        )
        assert ok is False

    async def test_reset_clears_counter(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        for _ in range(3):
            await redis_client.rate_limit_check(
                "user:2", max_requests=3, window_seconds=60, redis_client=redis
            )
        await redis_client.rate_limit_reset("user:2", redis_client=redis)
        ok = await redis_client.rate_limit_check(
            "user:2", max_requests=3, window_seconds=60, redis_client=redis
        )
        assert ok is True

    async def test_rejects_bad_parameters(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        with pytest.raises(ValueError):
            await redis_client.rate_limit_check(
                "k", max_requests=0, window_seconds=60, redis_client=redis
            )
        with pytest.raises(ValueError):
            await redis_client.rate_limit_check(
                "k", max_requests=5, window_seconds=0, redis_client=redis
            )


# ═══════════════════════════════════════════════════════════════════════
# Kill switch
# ═══════════════════════════════════════════════════════════════════════


class TestKillSwitch:
    async def test_default_is_active(self, redis: fake_aioredis.FakeRedis) -> None:
        uid = uuid4()
        status = await redis_client.get_kill_switch_status(uid, redis_client=redis)
        assert status == redis_client.KILL_SWITCH_ACTIVE

    async def test_set_and_read_tripped(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        uid = uuid4()
        await redis_client.set_kill_switch_status(
            uid, redis_client.KILL_SWITCH_TRIPPED, redis_client=redis
        )
        assert (
            await redis_client.get_kill_switch_status(uid, redis_client=redis)
            == redis_client.KILL_SWITCH_TRIPPED
        )

    async def test_clear_switches_back_to_active(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        uid = uuid4()
        await redis_client.set_kill_switch_status(
            uid, redis_client.KILL_SWITCH_TRIPPED, redis_client=redis
        )
        await redis_client.clear_kill_switch(uid, redis_client=redis)
        assert (
            await redis_client.get_kill_switch_status(uid, redis_client=redis)
            == redis_client.KILL_SWITCH_ACTIVE
        )

    async def test_rejects_invalid_status(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        with pytest.raises(ValueError):
            await redis_client.set_kill_switch_status(
                uuid4(), "MAYBE", redis_client=redis
            )

    async def test_corrupt_value_falls_back_to_active(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        uid = uuid4()
        await redis.set(f"kill:{uid}", "GARBAGE")
        assert (
            await redis_client.get_kill_switch_status(uid, redis_client=redis)
            == redis_client.KILL_SWITCH_ACTIVE
        )


# ═══════════════════════════════════════════════════════════════════════
# Daily P&L
# ═══════════════════════════════════════════════════════════════════════


class TestDailyPnl:
    async def test_default_zero(self, redis: fake_aioredis.FakeRedis) -> None:
        uid = uuid4()
        assert await redis_client.get_daily_pnl(uid, redis_client=redis) == Decimal("0")

    async def test_set_and_get(self, redis: fake_aioredis.FakeRedis) -> None:
        uid = uuid4()
        await redis_client.set_daily_pnl(
            uid, Decimal("1234.56"), redis_client=redis
        )
        assert await redis_client.get_daily_pnl(uid, redis_client=redis) == Decimal(
            "1234.56"
        )

    async def test_increment(self, redis: fake_aioredis.FakeRedis) -> None:
        uid = uuid4()
        total = await redis_client.increment_daily_pnl(
            uid, Decimal("100"), redis_client=redis
        )
        assert total == Decimal("100")
        total = await redis_client.increment_daily_pnl(
            uid, Decimal("-50.25"), redis_client=redis
        )
        assert total == Decimal("49.75")

    async def test_corrupt_value_returns_zero(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        uid = uuid4()
        await redis.set(f"pnl:{uid}", "not-a-number")
        assert await redis_client.get_daily_pnl(uid, redis_client=redis) == Decimal("0")


# ═══════════════════════════════════════════════════════════════════════
# Positions cache
# ═══════════════════════════════════════════════════════════════════════


class TestPositionsCache:
    async def test_roundtrip(self, redis: fake_aioredis.FakeRedis) -> None:
        uid = uuid4()
        payload = [{"symbol": "RELIANCE", "quantity": 10}]
        await redis_client.set_positions_cache(
            uid, payload, redis_client=redis
        )
        got = await redis_client.get_positions_cache(uid, redis_client=redis)
        assert got == payload

    async def test_miss_returns_empty_list(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        assert await redis_client.get_positions_cache(uuid4(), redis_client=redis) == []

    async def test_corrupt_returns_empty(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        uid = uuid4()
        await redis.set(f"pos:{uid}", "not-json")
        assert await redis_client.get_positions_cache(uid, redis_client=redis) == []

    async def test_corrupt_shape_returns_empty(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        uid = uuid4()
        await redis.set(f"pos:{uid}", '{"not": "a list"}')
        assert await redis_client.get_positions_cache(uid, redis_client=redis) == []


# ═══════════════════════════════════════════════════════════════════════
# Idempotency
# ═══════════════════════════════════════════════════════════════════════


class TestIdempotency:
    async def test_first_claim_succeeds(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        assert (
            await redis_client.set_idempotency_key("abc", redis_client=redis) is True
        )

    async def test_second_claim_fails(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        await redis_client.set_idempotency_key("abc", redis_client=redis)
        assert (
            await redis_client.set_idempotency_key("abc", redis_client=redis) is False
        )

    async def test_get_idempotency_key(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        assert (
            await redis_client.get_idempotency_key("new", redis_client=redis) is False
        )
        await redis_client.set_idempotency_key("new", redis_client=redis)
        assert (
            await redis_client.get_idempotency_key("new", redis_client=redis) is True
        )

    async def test_rejects_non_positive_ttl(
        self, redis: fake_aioredis.FakeRedis
    ) -> None:
        with pytest.raises(ValueError):
            await redis_client.set_idempotency_key(
                "x", ttl_seconds=0, redis_client=redis
            )
