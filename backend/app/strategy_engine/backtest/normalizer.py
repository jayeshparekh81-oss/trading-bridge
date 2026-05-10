"""Candle input normalizer — validate, sort, and dedupe before simulation.

Phase 3 input contract:
    * Candles are tz-aware (Phase 1 schema enforces this for Candle).
    * The normalizer sorts by ``timestamp`` ascending so the simulator
      can iterate without a sort step in its hot loop.
    * Duplicate timestamps raise ``NormalizerError`` — two bars at the
      same instant is almost always a data-pipeline bug; failing loudly
      is safer than picking one silently.
    * An empty candle list is rejected — there's nothing to backtest.
    * A single-candle input is rejected — the simulator needs at least
      one prior bar to evaluate crossover / breakout / next-bar entry.

The OHLC invariant is checked at :class:`Candle` construction time
(Phase 1), so normalizer assumes that's already handled.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.strategy_engine.schema.ohlcv import Candle


class NormalizerError(ValueError):
    """Raised when the candle list cannot be normalised for simulation."""


#: Minimum candle count for a runnable backtest. Two bars is the absolute
#: floor: bar 0 establishes context (prior values for crossovers), bar 1
#: is the first bar where entry can be evaluated.
MIN_CANDLES_FOR_SIMULATION = 2


def normalize_candles(candles: Iterable[Candle]) -> list[Candle]:
    """Return a sorted, deduped, validated list of candles.

    Args:
        candles: Iterable of :class:`Candle` (tz-aware timestamps).

    Returns:
        A new list, sorted ascending by timestamp.

    Raises:
        NormalizerError: Empty input, fewer than two candles, naive
            timestamps, or duplicate timestamps.
    """
    materialised = list(candles)
    if not materialised:
        raise NormalizerError("Candle list is empty; nothing to backtest.")
    if len(materialised) < MIN_CANDLES_FOR_SIMULATION:
        raise NormalizerError(
            f"Need at least {MIN_CANDLES_FOR_SIMULATION} candles to run a "
            f"backtest; got {len(materialised)}."
        )

    for idx, candle in enumerate(materialised):
        if candle.timestamp.tzinfo is None:
            raise NormalizerError(
                f"Candle at index {idx} has a naive timestamp; tz-aware datetimes are required."
            )

    sorted_candles = sorted(materialised, key=lambda c: c.timestamp)

    for i in range(1, len(sorted_candles)):
        if sorted_candles[i].timestamp == sorted_candles[i - 1].timestamp:
            raise NormalizerError(
                "Duplicate timestamps detected in candle list at "
                f"{sorted_candles[i].timestamp.isoformat()}."
            )

    return sorted_candles


__all__ = ["MIN_CANDLES_FOR_SIMULATION", "NormalizerError", "normalize_candles"]
