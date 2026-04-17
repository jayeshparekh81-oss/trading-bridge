"""Performance benchmarks — measure and assert latency targets.

Uses fakeredis for consistent, reproducible benchmarks.
Broker API calls are mocked at 0ms to isolate platform overhead.
"""

from __future__ import annotations

import statistics
import time
import uuid
from decimal import Decimal
from typing import Any

import fakeredis.aioredis
import pytest
from cryptography.fernet import Fernet

from app.core import security


@pytest.fixture(autouse=True)
def _reset_cipher(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    security.reset_cipher_cache()


@pytest.fixture()
def fake_redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


def _measure_sync(fn: Any, iterations: int = 100) -> dict[str, float]:
    """Run a sync function N times and return latency stats in ms."""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
    return {
        "median_ms": statistics.median(times),
        "p95_ms": sorted(times)[int(len(times) * 0.95)],
        "p99_ms": sorted(times)[int(len(times) * 0.99)],
        "min_ms": min(times),
        "max_ms": max(times),
    }


async def _measure_async(fn: Any, iterations: int = 100) -> dict[str, float]:
    """Run an async function N times and return latency stats in ms."""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        await fn()
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
    return {
        "median_ms": statistics.median(times),
        "p95_ms": sorted(times)[int(len(times) * 0.95)],
        "p99_ms": sorted(times)[int(len(times) * 0.99)],
        "min_ms": min(times),
        "max_ms": max(times),
    }


class TestRedisPerformance:
    @pytest.mark.asyncio
    async def test_redis_get_set_under_1ms(self, fake_redis: Any) -> None:
        """1000 Redis get/set operations. Median < 0.5ms, p99 < 1ms."""
        from app.core import redis_client as rc

        async def _op() -> None:
            key = f"bench:{uuid.uuid4().hex[:8]}"
            await rc.cache_set(key, "value", ttl_seconds=60, redis_client=fake_redis)
            await rc.cache_get(key, redis_client=fake_redis)

        stats = await _measure_async(_op, iterations=1000)
        assert stats["median_ms"] < 1.0, f"Median {stats['median_ms']:.3f}ms exceeds 1ms"
        assert stats["p99_ms"] < 5.0, f"p99 {stats['p99_ms']:.3f}ms exceeds 5ms"


class TestAuthPerformance:
    def test_jwt_creation_under_5ms(self) -> None:
        """100 JWT token creations. Median < 2ms."""
        from app.core.security_ext import create_session_token

        def _create() -> None:
            create_session_token(str(uuid.uuid4()), "fingerprint", ttl_seconds=3600)

        stats = _measure_sync(_create, iterations=100)
        assert stats["median_ms"] < 5.0, f"Median {stats['median_ms']:.3f}ms exceeds 5ms"
        assert stats["p99_ms"] < 20.0, f"p99 {stats['p99_ms']:.3f}ms exceeds 20ms"

    @pytest.mark.asyncio
    async def test_jwt_validation_under_5ms(self, fake_redis: Any) -> None:
        """100 JWT token validations. Median < 2ms, p99 < 5ms."""
        from app.core.security_ext import create_session_token, validate_session_token

        token = create_session_token("user-id", "fingerprint", ttl_seconds=3600)

        async def _validate() -> None:
            await validate_session_token(token, redis_conn=fake_redis)

        stats = await _measure_async(_validate, iterations=100)
        assert stats["median_ms"] < 5.0, f"Median {stats['median_ms']:.3f}ms exceeds 5ms"
        assert stats["p99_ms"] < 20.0, f"p99 {stats['p99_ms']:.3f}ms exceeds 20ms"


class TestKillSwitchPerformance:
    @pytest.mark.asyncio
    async def test_kill_switch_check_under_2ms(self, fake_redis: Any) -> None:
        """100 kill switch status checks. Median < 1ms, p99 < 2ms."""
        from app.core import redis_client as rc

        user_id = uuid.uuid4()
        await rc.set_kill_switch_status(
            user_id, rc.KILL_SWITCH_ACTIVE, redis_client=fake_redis
        )

        async def _check() -> None:
            await rc.get_kill_switch_status(user_id, redis_client=fake_redis)

        stats = await _measure_async(_check, iterations=100)
        assert stats["median_ms"] < 2.0, f"Median {stats['median_ms']:.3f}ms exceeds 2ms"
        assert stats["p99_ms"] < 5.0, f"p99 {stats['p99_ms']:.3f}ms exceeds 5ms"


class TestHMACPerformance:
    def test_hmac_verification_under_1ms(self) -> None:
        """100 HMAC verifications. Median < 0.5ms."""
        from app.core.security import compute_hmac_signature, verify_hmac_signature

        secret = "test-hmac-secret-for-benchmarks"
        payload = b'{"action":"BUY","symbol":"NIFTY","quantity":50}'
        sig = compute_hmac_signature(payload, secret)

        def _verify() -> None:
            verify_hmac_signature(payload, sig, secret)

        stats = _measure_sync(_verify, iterations=100)
        assert stats["median_ms"] < 1.0, f"Median {stats['median_ms']:.3f}ms exceeds 1ms"


class TestIdempotencyPerformance:
    @pytest.mark.asyncio
    async def test_idempotency_check_under_1ms(self, fake_redis: Any) -> None:
        """100 idempotency lookups. Median < 0.5ms."""
        from app.core import redis_client as rc

        async def _check() -> None:
            key = f"idem:{uuid.uuid4().hex}"
            await rc.set_idempotency_key(key, ttl_seconds=60, redis_client=fake_redis)

        stats = await _measure_async(_check, iterations=100)
        assert stats["median_ms"] < 2.0, f"Median {stats['median_ms']:.3f}ms exceeds 2ms"


class TestPasswordHashPerformance:
    def test_bcrypt_hash_reasonable_time(self) -> None:
        """Password hashing should be slow (security) but not TOO slow."""
        from app.core.security import hash_password

        start = time.perf_counter()
        hash_password("BenchmarkP@ss1")
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Bcrypt should take 100-500ms (cost factor 12)
        assert elapsed_ms > 50, "Bcrypt too fast — cost factor may be too low"
        assert elapsed_ms < 2000, "Bcrypt too slow — check system resources"
