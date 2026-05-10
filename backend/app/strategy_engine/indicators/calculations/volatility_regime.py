"""Volatility regime classifier — Calm / Normal / Elevated / Extreme.

Per bar, compares the current ATR-percent reading to its trailing
``lookback`` window and returns a regime code:

     0.0 → Calm     (ATR_pct in the bottom 25 % of the window)
     1.0 → Normal   (25-50 %)
     2.0 → Elevated (50-75 %)
     3.0 → Extreme  (top 25 %)

Uses ATR-percent (volatility normalised by price) so the
classification is comparable across symbols. The lookback should
be wide enough to span at least one volatility cycle on the
target timeframe — default ``lookback = 100`` bars works for
daily Indian-equity data.

Output length equals input length. ``None`` until the lookback
window is full (and ATR-percent has warmed up).

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``lookback >= n`` -> ``[]``.
    * Constant-ATR window → returns 1.0 (Normal) by default since
      every reading equals the median.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.atr_percent import atr_percent


def volatility_regime(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    lookback: int = 100,
    atr_period: int = 14,
) -> list[float | None]:
    """Per-bar volatility regime code (0..3)."""
    if not isinstance(lookback, int) or isinstance(lookback, bool) or lookback < 4:
        raise ValueError(f"lookback must be an int >= 4; got {lookback!r}.")
    if not isinstance(atr_period, int) or isinstance(atr_period, bool) or atr_period <= 0:
        raise ValueError(f"atr_period must be a positive int; got {atr_period!r}.")
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0 or lookback >= n:
        return []

    series = atr_percent(highs, lows, closes, atr_period)
    if not series:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(lookback, n):
        window = [v for v in series[i - lookback : i + 1] if v is not None]
        if len(window) < lookback // 2:
            continue
        sorted_w = sorted(window)
        cutoffs = (
            sorted_w[len(sorted_w) // 4],
            sorted_w[len(sorted_w) // 2],
            sorted_w[len(sorted_w) * 3 // 4],
        )
        cur = series[i]
        if cur is None:
            continue
        if cur <= cutoffs[0]:
            out[i] = 0.0
        elif cur <= cutoffs[1]:
            out[i] = 1.0
        elif cur <= cutoffs[2]:
            out[i] = 2.0
        else:
            out[i] = 3.0
    return out


__all__ = ["volatility_regime"]
