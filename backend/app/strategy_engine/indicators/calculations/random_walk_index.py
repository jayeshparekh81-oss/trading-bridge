"""Random Walk Index (RWI) — Michael Poulos.

No Pine canonical; standard Poulos formulation.

Definition (LOCKED per reference doc):
    For each n in 2..max_length:
        RWI_high_n[t] = (high[t] - low[t - n]) / (ATR(atr_period) * sqrt(n))
        RWI_low_n[t]  = (high[t - n] - low[t]) / (ATR(atr_period) * sqrt(n))

    Returns the per-bar maximum across all n:
        RWI_high[t] = max over n of RWI_high_n[t]
        RWI_low[t]  = max over n of RWI_low_n[t]

    Defaults: max_length = 10, atr_period = 10.
    sqrt divisor uses ``n`` (NOT n-1).
    ATR uses Wilder smoothing (existing ``atr`` calc).

Output: tuple of (rwi_high_list, rwi_low_list), each length n.

First defined index: max(max_length, atr_period - 1). With defaults,
that's index 10 (need 10 prior bars for n=10 lookback AND ATR seed).

Edge cases:
    * Empty / length-mismatch -> ([], [])
    * Series too short for ATR + max_length -> all-None tuples
    * ATR == 0 (flat market) -> None for that bar
    * Invalid period -> ValueError

Source: Michael Poulos, "Of Trends and Random Walks" (Stocks &
Commodities V9:2, 1991).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.atr import atr


def random_walk_index(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    max_length: int = 10,
    atr_period: int = 10,
) -> tuple[list[float | None], list[float | None]]:
    """Random Walk Index — returns (rwi_high, rwi_low)."""
    _check_period(max_length, "max_length")
    _check_period(atr_period, "atr_period")
    if max_length < 2:
        raise ValueError(f"max_length must be >= 2; got {max_length}.")
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must be same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0:
        return ([], [])

    atr_values = atr(highs, lows, closes, period=atr_period)
    if not atr_values:
        return ([None] * n, [None] * n)

    rwi_high: list[float | None] = [None] * n
    rwi_low: list[float | None] = [None] * n

    # Earliest bar where ALL window sizes 2..max_length are valid AND
    # ATR is defined. ATR Wilder: first non-None at index atr_period - 1.
    first_defined = max(max_length, atr_period - 1)

    for t in range(first_defined, n):
        atr_t = atr_values[t]
        if atr_t is None or atr_t == 0.0:
            continue

        best_high: float | None = None
        best_low: float | None = None
        for nn in range(2, max_length + 1):
            if t - nn < 0:
                break
            denom = atr_t * math.sqrt(nn)
            val_high = (highs[t] - lows[t - nn]) / denom
            val_low = (highs[t - nn] - lows[t]) / denom
            if best_high is None or val_high > best_high:
                best_high = val_high
            if best_low is None or val_low > best_low:
                best_low = val_low
        rwi_high[t] = best_high
        rwi_low[t] = best_low

    return (rwi_high, rwi_low)


def _check_period(period: int, name: str) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"{name} must be a positive int; got {period!r}.")


__all__ = ["random_walk_index"]
