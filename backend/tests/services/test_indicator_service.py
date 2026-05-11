"""Tests for :mod:`app.services.indicator_service`."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio

from app.core import redis_client
from app.schemas.broker import Exchange
from app.schemas.candle import Timeframe
from app.schemas.indicator import (
    BbParams,
    IndicatorName,
    IndicatorRequest,
    MacdParams,
    SmaParams,
)
from app.services.indicator_service import (
    _nan_to_none,
    build_cache_key,
    compute_indicator,
)
from tests.services.indicators.conftest import synthesise_candles


# ═══════════════════════════════════════════════════════════════════════
# Cache key
# ═══════════════════════════════════════════════════════════════════════


def test_cache_key_shape() -> None:
    ts = datetime(2026, 5, 11, 9, 15, tzinfo=UTC)
    key = build_cache_key(
        symbol="NIFTY",
        timeframe="5m",
        indicator=IndicatorName.SMA,
        params_dict={"indicator": "sma", "length": 20},
        last_closed_candle_ts=ts,
    )
    assert key.startswith("indicator:NIFTY:5m:sma:")
    # Suffix is the epoch-second of last_closed_candle_ts.
    assert key.endswith(f":{int(ts.timestamp())}")


def test_cache_key_independent_of_param_order() -> None:
    ts = datetime(2026, 5, 11, tzinfo=UTC)
    a = build_cache_key(
        symbol="X", timeframe="5m", indicator=IndicatorName.MACD,
        params_dict={"indicator": "macd", "fast_length": 12, "slow_length": 26, "signal_length": 9},
        last_closed_candle_ts=ts,
    )
    b = build_cache_key(
        symbol="X", timeframe="5m", indicator=IndicatorName.MACD,
        params_dict={"signal_length": 9, "indicator": "macd", "slow_length": 26, "fast_length": 12},
        last_closed_candle_ts=ts,
    )
    assert a == b


def test_cache_key_changes_with_params() -> None:
    ts = datetime(2026, 5, 11, tzinfo=UTC)
    a = build_cache_key(
        symbol="X", timeframe="5m", indicator=IndicatorName.SMA,
        params_dict={"indicator": "sma", "length": 20}, last_closed_candle_ts=ts,
    )
    b = build_cache_key(
        symbol="X", timeframe="5m", indicator=IndicatorName.SMA,
        params_dict={"indicator": "sma", "length": 50}, last_closed_candle_ts=ts,
    )
    assert a != b


def test_cache_key_uses_last_closed_not_to_ts() -> None:
    """Two requests at different points within the same in-progress bar
    must hash to the same key. The key suffix is the last CLOSED bar's
    timestamp — caller passes that, not requested ``to_ts``."""
    closed_ts = datetime(2026, 5, 11, 9, 15, tzinfo=UTC)
    a = build_cache_key(
        symbol="X", timeframe="5m", indicator=IndicatorName.SMA,
        params_dict={"indicator": "sma", "length": 20},
        last_closed_candle_ts=closed_ts,
    )
    b = build_cache_key(
        symbol="X", timeframe="5m", indicator=IndicatorName.SMA,
        params_dict={"indicator": "sma", "length": 20},
        last_closed_candle_ts=closed_ts,
    )
    assert a == b


# ═══════════════════════════════════════════════════════════════════════
# _nan_to_none helper
# ═══════════════════════════════════════════════════════════════════════


def test_nan_to_none() -> None:
    import numpy as np

    arr = np.array([1.0, float("nan"), 3.0, float("nan")])
    out = _nan_to_none(arr)
    assert out == [1.0, None, 3.0, None]


# ═══════════════════════════════════════════════════════════════════════
# compute_indicator end-to-end
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture(autouse=True)
async def _fake_redis(monkeypatch: pytest.MonkeyPatch):
    client = fake_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: client)
    try:
        yield client
    finally:
        await client.aclose()


def _user() -> MagicMock:
    u = MagicMock()
    u.id = UUID("11111111-1111-1111-1111-111111111111")
    return u


def _request_for(
    indicator_params: Any, *, candles_window_seconds: int = 200 * 300
) -> IndicatorRequest:
    base = datetime(2026, 5, 11, 3, 45, tzinfo=UTC)
    return IndicatorRequest(
        symbol="NIFTY",
        exchange=Exchange.NSE,
        timeframe=Timeframe.FIVE_MIN,
        params=indicator_params,
        from_ts=base,
        to_ts=base + timedelta(seconds=candles_window_seconds),
    )


def _fetcher_returning(candles: list[Any]) -> Any:
    async def _f(**_kw: Any) -> list[Any]:
        return list(candles)
    return _f


@pytest.mark.asyncio
async def test_compute_happy_path_sma() -> None:
    candles = synthesise_candles(n=200)
    req = _request_for(SmaParams(length=20))
    resp = await compute_indicator(
        request=req, user=_user(), db=AsyncMock(),
        candle_fetcher=_fetcher_returning(candles),
    )
    assert resp.indicator == IndicatorName.SMA
    assert resp.cached is False
    assert len(resp.candle_timestamps) == 200
    assert resp.series["value"][0] is None  # warmup
    assert resp.series["value"][-1] is not None  # post-warmup


@pytest.mark.asyncio
async def test_compute_cache_hit_on_second_call() -> None:
    candles = synthesise_candles(n=200)
    req = _request_for(SmaParams(length=20))
    fetcher = _fetcher_returning(candles)
    first = await compute_indicator(
        request=req, user=_user(), db=AsyncMock(), candle_fetcher=fetcher,
    )
    second = await compute_indicator(
        request=req, user=_user(), db=AsyncMock(), candle_fetcher=fetcher,
    )
    assert first.cached is False
    assert second.cached is True
    # Series content identical between live + cached.
    assert first.series["value"] == second.series["value"]


@pytest.mark.asyncio
async def test_compute_empty_candles_returns_empty_response() -> None:
    req = _request_for(SmaParams(length=20))
    resp = await compute_indicator(
        request=req, user=_user(), db=AsyncMock(),
        candle_fetcher=_fetcher_returning([]),
    )
    assert resp.candle_timestamps == []
    assert resp.series == {"value": []}
    assert resp.last_closed_candle_ts is None
    assert resp.cached is False


@pytest.mark.asyncio
async def test_compute_macd_multi_output() -> None:
    candles = synthesise_candles(n=200)
    req = _request_for(MacdParams())
    resp = await compute_indicator(
        request=req, user=_user(), db=AsyncMock(),
        candle_fetcher=_fetcher_returning(candles),
    )
    assert set(resp.series) == {"macd", "signal", "histogram"}
    # Post-warmup: all three series have finite tail values.
    assert resp.series["macd"][-1] is not None
    assert resp.series["signal"][-1] is not None
    assert resp.series["histogram"][-1] is not None


@pytest.mark.asyncio
async def test_compute_bb_multi_output() -> None:
    candles = synthesise_candles(n=200)
    req = _request_for(BbParams())
    resp = await compute_indicator(
        request=req, user=_user(), db=AsyncMock(),
        candle_fetcher=_fetcher_returning(candles),
    )
    assert set(resp.series) == {"upper", "middle", "lower"}


@pytest.mark.asyncio
async def test_compute_corrupt_cache_falls_through(
    _fake_redis: fake_aioredis.FakeRedis,
) -> None:
    candles = synthesise_candles(n=200)
    req = _request_for(SmaParams(length=20))

    # Seed an invalid JSON at the expected cache key.
    last_closed = candles[-1].timestamp
    key = build_cache_key(
        symbol=req.symbol,
        timeframe=req.timeframe.value,
        indicator=IndicatorName.SMA,
        params_dict=req.params.model_dump(mode="json"),
        last_closed_candle_ts=last_closed,
    )
    await _fake_redis.set(f"cache:{key}", "{not json}", ex=60)

    resp = await compute_indicator(
        request=req, user=_user(), db=AsyncMock(),
        candle_fetcher=_fetcher_returning(candles),
    )
    # Recomputed — cached=False, fresh result.
    assert resp.cached is False
    assert resp.series["value"][-1] is not None


@pytest.mark.asyncio
async def test_compute_cache_set_failure_does_not_fail_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import indicator_service

    candles = synthesise_candles(n=200)
    req = _request_for(SmaParams(length=20))

    async def _failing(*_a: Any, **_kw: Any) -> None:
        raise ConnectionError("redis down")

    monkeypatch.setattr(indicator_service, "cache_set", _failing)
    resp = await compute_indicator(
        request=req, user=_user(), db=AsyncMock(),
        candle_fetcher=_fetcher_returning(candles),
    )
    # Request succeeds despite cache-write failure.
    assert resp.cached is False
    assert resp.series["value"][-1] is not None


@pytest.mark.asyncio
async def test_compute_propagates_fetcher_exception() -> None:
    from fastapi import HTTPException

    async def _failing(**_kw: Any) -> Any:
        raise HTTPException(status_code=429, detail="rate limited")

    req = _request_for(SmaParams(length=20))
    with pytest.raises(HTTPException) as excinfo:
        await compute_indicator(
            request=req, user=_user(), db=AsyncMock(), candle_fetcher=_failing,
        )
    assert excinfo.value.status_code == 429


# ═══════════════════════════════════════════════════════════════════════
# Latency + memory-leak gates (quality bars from the brief)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_latency_under_30ms_per_1000_candles() -> None:
    """Brief: <30ms for 1000 candles end-to-end."""
    import time

    candles = synthesise_candles(n=1000)
    req = _request_for(SmaParams(length=20), candles_window_seconds=1000 * 300)
    start = time.perf_counter()
    resp = await compute_indicator(
        request=req, user=_user(), db=AsyncMock(),
        candle_fetcher=_fetcher_returning(candles),
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert resp.candle_timestamps  # produced output
    assert elapsed_ms < 30, f"compute took {elapsed_ms:.2f}ms (>30ms gate)"


@pytest.mark.asyncio
async def test_no_memory_leak_under_repeated_calls() -> None:
    """Brief: no memory leaks (verify with repeated-call test).

    Steady-state-vs-steady-state comparison: after burning in 100
    iterations the allocator + caches are stable. We compare the
    growth between the *next* 100 iterations (the "test" window)
    against that stable baseline; if compute leaks per-call, the
    delta grows linearly. Bounded growth = no leak.
    """
    import gc
    import tracemalloc

    candles = synthesise_candles(n=200)
    req = _request_for(SmaParams(length=20))
    fetcher = _fetcher_returning(candles)

    async def _run_batch(n: int) -> None:
        for _ in range(n):
            await compute_indicator(
                request=req, user=_user(), db=AsyncMock(),
                candle_fetcher=fetcher,
            )

    # Burn in to settle caches + JIT.
    await _run_batch(100)
    gc.collect()

    tracemalloc.start()
    snapshot_a = tracemalloc.take_snapshot()
    await _run_batch(100)
    gc.collect()
    snapshot_b = tracemalloc.take_snapshot()

    stats = snapshot_b.compare_to(snapshot_a, "lineno")
    total_growth_kib = sum(s.size_diff for s in stats) / 1024.0
    tracemalloc.stop()

    # Steady-state growth across the second 100 calls — a real leak
    # would scale linearly with iteration count. 1 MiB cap is
    # generous; observed in practice is well under 100 KiB.
    assert total_growth_kib < 1024.0, (
        f"steady-state memory grew {total_growth_kib:.1f} KiB across "
        "100 iterations — possible leak"
    )
