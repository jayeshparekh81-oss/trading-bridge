"""Tests for :mod:`app.services.anomaly_shield_service`.

Covers the six paths the design proposal called out:
* default OFF short-circuits everything
* cold start (< 50 bars) returns warming_up
* normal data passes through with composite=0
* multivariate trip returns tripped + populated extreme list
* activate_block / is_block_active TTL behaviour
* check_and_consume_release fires once and clears
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio

from app.core import config as app_config
from app.core import redis_client
from app.services import anomaly_shield_service as svc


@pytest_asyncio.fixture(autouse=True)
async def _patch_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[fake_aioredis.FakeRedis]:
    client = fake_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: client)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    """Bust the lru_cache on get_settings so per-test env tweaks take
    effect. Each test mutates settings via the env-aware
    ``Settings(**override)`` constructor, then restores defaults."""
    app_config.get_settings.cache_clear()
    yield
    app_config.get_settings.cache_clear()


def _enable_shield(
    monkeypatch: pytest.MonkeyPatch,
    *,
    composite_threshold: float = 70.0,
    z_threshold: float = 2.5,
    block_bars: int = 4,
) -> None:
    monkeypatch.setenv("BLACK_SWAN_SHIELD_ENABLED", "true")
    monkeypatch.setenv("ANOMALY_COMPOSITE_THRESHOLD", str(composite_threshold))
    monkeypatch.setenv("ANOMALY_Z_THRESHOLD", str(z_threshold))
    monkeypatch.setenv("ANOMALY_BLOCK_BARS", str(block_bars))
    app_config.get_settings.cache_clear()


def _flat_indicators(value: float = 1.0) -> dict[str, float]:
    """Return a payload where every DNA key has the same value — so the
    rolling distribution has zero variance and z-scores are all 0 / NaN."""
    return {k: value for k in svc._DNA_KEYS}


def _normal_indicators(seed: int) -> dict[str, float]:
    """Deterministic 'normal' values that vary slightly per seed so the
    rolling window has positive std (otherwise z-score is undefined and
    the shield can't trip even on extreme inputs)."""
    return {k: 1.0 + 0.01 * (seed + i) for i, k in enumerate(svc._DNA_KEYS)}


# ═══════════════════════════════════════════════════════════════════════
# Default OFF
# ═══════════════════════════════════════════════════════════════════════


class TestDefaultOff:
    async def test_is_enabled_false_by_default(self) -> None:
        # No env var set → default False.
        assert svc.is_enabled() is False

    async def test_evaluate_short_circuits_when_disabled(self) -> None:
        sid = uuid4()
        result = await svc.evaluate(sid, _normal_indicators(0))
        assert result.tripped is False
        assert result.reason == "disabled"
        assert result.composite_score == 0.0

    async def test_record_is_noop_when_disabled(
        self, _patch_redis: fake_aioredis.FakeRedis
    ) -> None:
        sid = uuid4()
        await svc.record_indicator_bar(sid, _normal_indicators(0))
        # No keys should have been written.
        keys = await _patch_redis.keys("*")
        assert keys == []

    async def test_is_block_active_false_when_disabled(self) -> None:
        sid = uuid4()
        assert await svc.is_block_active(sid) is False


# ═══════════════════════════════════════════════════════════════════════
# Cold start (< 50 bars)
# ═══════════════════════════════════════════════════════════════════════


class TestColdStart:
    async def test_warming_up_under_threshold(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_shield(monkeypatch)
        sid = uuid4()

        for i in range(svc.MIN_BARS_REQUIRED - 1):
            await svc.record_indicator_bar(sid, _normal_indicators(i))

        result = await svc.evaluate(sid, _normal_indicators(99))
        assert result.tripped is False
        assert result.reason == "warming_up"
        assert result.bars_collected == svc.MIN_BARS_REQUIRED - 1

    async def test_records_during_cold_start(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Recording must happen even while the shield is cold so the
        baseline grows toward the eval threshold."""
        _enable_shield(monkeypatch)
        sid = uuid4()
        for i in range(10):
            await svc.record_indicator_bar(sid, _normal_indicators(i))

        result = await svc.evaluate(sid, _normal_indicators(10))
        assert result.bars_collected == 10


# ═══════════════════════════════════════════════════════════════════════
# Normal bar — no extreme indicators
# ═══════════════════════════════════════════════════════════════════════


class TestNormal:
    async def test_no_trip_on_in_distribution_bar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_shield(monkeypatch)
        sid = uuid4()

        for i in range(svc.MIN_BARS_REQUIRED + 5):
            await svc.record_indicator_bar(sid, _normal_indicators(i))

        # Next bar drawn from the same distribution.
        result = await svc.evaluate(sid, _normal_indicators(svc.MIN_BARS_REQUIRED + 5))
        assert result.tripped is False
        assert result.reason == "normal"
        assert result.composite_score == 0.0


# ═══════════════════════════════════════════════════════════════════════
# Trip — multivariate extreme
# ═══════════════════════════════════════════════════════════════════════


class TestTrip:
    async def test_extreme_bar_trips(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_shield(monkeypatch)
        sid = uuid4()

        for i in range(60):
            await svc.record_indicator_bar(sid, _normal_indicators(i))

        # Construct a bar where every indicator is 100σ above mean.
        # mean ≈ 1.0, std ≈ 0.17 — so 50.0 is far outside any threshold.
        extreme_payload = {k: 50.0 for k in svc._DNA_KEYS}
        result = await svc.evaluate(sid, extreme_payload)

        assert result.tripped is True
        assert result.reason == "tripped"
        assert result.composite_score > 70.0
        assert len(result.extreme_indicators) >= 5
        # Sorted descending by z.
        zs = [e["z"] for e in result.extreme_indicators]
        assert zs == sorted(zs, reverse=True)

    async def test_partial_extreme_below_composite_threshold(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A single moderate outlier (z just over threshold) shouldn't
        trip on its own. Composite formula = (count/22)*50 + (avg_z/5)*50;
        with z≈2.6 and count=1 we get ~28 — below the 70 trip line."""
        _enable_shield(monkeypatch)
        sid = uuid4()

        for i in range(60):
            await svc.record_indicator_bar(sid, _normal_indicators(i))

        # mean ≈ 1.295, std ≈ 0.063 across the 60 normal bars; bumping
        # one indicator by ~0.18 puts z just past 2.5 without exploding.
        bar = _normal_indicators(60)
        bar[svc._DNA_KEYS[0]] += 0.18
        result = await svc.evaluate(sid, bar)

        assert len(result.extreme_indicators) == 1
        assert result.composite_score < 70.0
        assert result.tripped is False

    async def test_severe_single_outlier_trips_via_avg_z(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Even ONE indicator at extreme z (e.g. flash-crash-class spike)
        trips the shield — that's the legacy formula's intent. The avg-z
        term dominates when count is small, so a 100σ event = composite
        capped at 100 = trip. Documenting this on purpose."""
        _enable_shield(monkeypatch)
        sid = uuid4()

        for i in range(60):
            await svc.record_indicator_bar(sid, _normal_indicators(i))

        bar = _normal_indicators(60)
        bar[svc._DNA_KEYS[0]] = 50.0  # ≈ 280σ above mean
        result = await svc.evaluate(sid, bar)

        assert len(result.extreme_indicators) == 1
        assert result.tripped is True
        assert result.composite_score == 100.0


# ═══════════════════════════════════════════════════════════════════════
# Block lifecycle
# ═══════════════════════════════════════════════════════════════════════


class TestBlockLifecycle:
    async def test_activate_block_sets_active_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_shield(monkeypatch)
        sid = uuid4()
        assert await svc.is_block_active(sid) is False

        cooldown = await svc.activate_block(sid)
        assert cooldown == 4 * 15 * 60

        assert await svc.is_block_active(sid) is True

    async def test_block_ttl_matches_configured_bars(
        self,
        monkeypatch: pytest.MonkeyPatch,
        _patch_redis: fake_aioredis.FakeRedis,
    ) -> None:
        _enable_shield(monkeypatch, block_bars=2)
        sid = uuid4()
        await svc.activate_block(sid)

        ttl = await _patch_redis.ttl(f"cache:{svc._block_key(sid)}")
        # 2 bars × 15 min = 1800 s. Allow a 1-second drift.
        assert 1799 <= ttl <= 1800

    async def test_release_alert_fires_once(
        self,
        monkeypatch: pytest.MonkeyPatch,
        _patch_redis: fake_aioredis.FakeRedis,
    ) -> None:
        _enable_shield(monkeypatch)
        sid = uuid4()
        await svc.activate_block(sid)

        # While block active → no release.
        assert await svc.check_and_consume_release(sid) is False

        # Manually expire the block flag (simulate TTL elapsed).
        await _patch_redis.delete(f"cache:{svc._block_key(sid)}")

        # First call after expiry → release fires.
        assert await svc.check_and_consume_release(sid) is True
        # Second call → marker consumed, no double-fire.
        assert await svc.check_and_consume_release(sid) is False

    async def test_release_check_disabled_when_shield_off(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Shield disabled → release check is a no-op even if a stale
        # marker exists from before the toggle was flipped.
        sid = uuid4()
        assert await svc.check_and_consume_release(sid) is False
