"""Indicator orchestrator — dispatch + caching + response assembly.

Single public coroutine :func:`compute_indicator` takes an
:class:`IndicatorRequest` (plus auth + db handles) and returns an
:class:`IndicatorResponse`. The orchestrator owns:

    * The R2 cache key (``indicator:{symbol}:{tf}:{name}:{params_hash}:
      {last_closed_candle_ts}``) — built only after the closed-candle
      filter so two requests within the same in-progress bar hash to
      the same key.
    * Redis 5-min TTL caching (read-through + write-back).
    * Dispatch to the per-indicator implementation via :data:`REGISTRY`.
    * NaN → ``None`` conversion at the JSON boundary so the response
      stays Pydantic-strict-compatible.
    * Empty / insufficient-data handling per the NaN policy (200 OK
      with all-None series, never 400).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import numpy as np

from app.core.logging import get_logger
from app.core.redis_client import cache_get, cache_set
from app.db.models.user import User
from app.schemas.candle import Candle
from app.schemas.indicator import (
    IndicatorName,
    IndicatorRequest,
    IndicatorResponse,
)
from app.services.indicator_candles import fetch_closed_candles
from app.services.indicators import REGISTRY

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


_logger = get_logger("services.indicator_service")


#: Cache TTL for indicator responses. Matches the chart-history cache —
#: keeps memory bounded between candle-roll events.
_CACHE_TTL_SECONDS = 300


# ═══════════════════════════════════════════════════════════════════════
# Cache key
# ═══════════════════════════════════════════════════════════════════════


def _params_hash(params_dict: dict[str, Any]) -> str:
    """Stable 8-char hash of the params dict — order-insensitive."""
    # Drop the discriminator since it's already in the key prefix.
    canonical = {k: v for k, v in params_dict.items() if k != "indicator"}
    raw = json.dumps(canonical, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]


def build_cache_key(
    *,
    symbol: str,
    timeframe: str,
    indicator: IndicatorName,
    params_dict: dict[str, Any],
    last_closed_candle_ts: datetime,
) -> str:
    """Final R2 cache key shape.

    Two requests at different points within the same in-progress bar
    hash to the same key because ``last_closed_candle_ts`` is the most
    recent CLOSED bar (not the requested ``to_ts``).
    """
    return (
        f"indicator:{symbol.upper()}:{timeframe}:{indicator.value}"
        f":{_params_hash(params_dict)}:{int(last_closed_candle_ts.timestamp())}"
    )


# ═══════════════════════════════════════════════════════════════════════
# Response assembly
# ═══════════════════════════════════════════════════════════════════════


def _nan_to_none(arr: np.ndarray) -> list[float | None]:
    """Convert a float64 array's NaN positions to ``None`` for JSON.

    Pydantic v2 strict mode rejects ``float('nan')`` in JSON output
    (NaN is not valid JSON per RFC 8259); ``None`` serialises cleanly
    and round-trips through every JSON deserialiser.
    """
    return [None if np.isnan(v) else float(v) for v in arr.tolist()]


def _build_empty_response(
    *, request: IndicatorRequest, indicator: IndicatorName
) -> IndicatorResponse:
    """Construct the all-NaN / empty response shape for "no closed
    candles in range" — returned as 200, never 400, per the NaN policy.
    """
    impl = REGISTRY[indicator]
    return IndicatorResponse(
        symbol=request.symbol,
        timeframe=request.timeframe,
        indicator=indicator,
        from_ts=request.from_ts,
        to_ts=request.to_ts,
        last_closed_candle_ts=None,
        candle_timestamps=[],
        series={name: [] for name in impl.output_names},
        cached=False,
    )


def _assemble_response(
    *,
    request: IndicatorRequest,
    indicator: IndicatorName,
    candles: list[Candle],
    series_arrays: dict[str, np.ndarray],
) -> IndicatorResponse:
    """Combine candles + computed series into the wire shape."""
    timestamps = [c.timestamp for c in candles]
    last_closed = timestamps[-1] if timestamps else None
    series_json: dict[str, list[float | None]] = {
        name: _nan_to_none(arr) for name, arr in series_arrays.items()
    }
    return IndicatorResponse(
        symbol=request.symbol,
        timeframe=request.timeframe,
        indicator=indicator,
        from_ts=request.from_ts,
        to_ts=request.to_ts,
        last_closed_candle_ts=last_closed,
        candle_timestamps=timestamps,
        series=series_json,
        cached=False,
    )


# ═══════════════════════════════════════════════════════════════════════
# Orchestrator
# ═══════════════════════════════════════════════════════════════════════


async def compute_indicator(
    *,
    request: IndicatorRequest,
    user: User,
    db: AsyncSession,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    candle_fetcher: Callable[..., Any] | None = None,
) -> IndicatorResponse:
    """End-to-end compute for one indicator request.

    Order of operations:

        1. Fetch candles via :func:`fetch_closed_candles` (R1 filter
           applied inside).
        2. If no closed candles → return 200 with empty series.
        3. Build the R2 cache key. Read-through Redis; on hit, return
           the cached response with ``cached=True``.
        4. Dispatch to ``REGISTRY[indicator]`` and compute.
        5. Assemble :class:`IndicatorResponse`, write to cache, return.

    HTTP error propagation: any ``HTTPException`` raised by
    :func:`fetch_closed_candles` (auth, params, rate-limit, upstream,
    404) flows through to the API route unchanged.
    """
    indicator: IndicatorName = request.params.indicator

    # Step 1: fetch closed candles.
    fetcher = candle_fetcher or fetch_closed_candles
    candles = await fetcher(
        user=user,
        db=db,
        symbol=request.symbol,
        exchange=request.exchange,
        timeframe=request.timeframe,
        from_ts=request.from_ts,
        to_ts=request.to_ts,
        now=now,
    )

    # Step 2: empty / insufficient (no closed candles in range).
    if not candles:
        _logger.info(
            "indicator.empty_window",
            symbol=request.symbol,
            timeframe=request.timeframe.value,
            indicator=indicator.value,
        )
        return _build_empty_response(request=request, indicator=indicator)

    last_closed = candles[-1].timestamp
    params_dict = request.params.model_dump(mode="json")
    cache_key = build_cache_key(
        symbol=request.symbol,
        timeframe=request.timeframe.value,
        indicator=indicator,
        params_dict=params_dict,
        last_closed_candle_ts=last_closed,
    )

    # Step 3: cache read-through.
    cached_str = await cache_get(cache_key)
    if cached_str is not None:
        try:
            cached_resp = IndicatorResponse.model_validate_json(cached_str)
            return cached_resp.model_copy(update={"cached": True})
        except Exception:  # noqa: BLE001 — corrupt JSON / schema drift
            _logger.warning(
                "indicator.cache_corrupt",
                cache_key=cache_key,
                symbol=request.symbol,
            )
            # Fall through to recompute.

    # Step 4: dispatch.
    impl = REGISTRY[indicator]
    series_arrays = impl.compute(candles, request.params)

    # Step 5: assemble + cache + return.
    response = _assemble_response(
        request=request,
        indicator=indicator,
        candles=candles,
        series_arrays=series_arrays,
    )

    try:
        await cache_set(
            cache_key, response.model_dump_json(), ttl_seconds=_CACHE_TTL_SECONDS
        )
    except Exception as exc:  # noqa: BLE001
        # Cache write failure NEVER fails the request.
        _logger.warning(
            "indicator.cache_set_failed",
            cache_key=cache_key,
            error=type(exc).__name__,
        )

    return response


__all__ = [
    "build_cache_key",
    "compute_indicator",
]
