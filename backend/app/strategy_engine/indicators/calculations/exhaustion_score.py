"""Exhaustion Score - 0..100 multi-factor exhaustion signal.

Three components::

    rsi_part      = clamp((|rsi - 50| - 25) / 25, 0, 1)    * 30
    bar_blowoff   = clamp((bar_range - avg_range) /
                          max(avg_range, eps), 0, 2) / 2   * 35
    stretch_part  = clamp(|close - sma| / (3 * atr), 0, 1) * 35
    score         = sum

Captures the "trend has gone too far too fast" pattern: extreme
RSI + abnormally large recent bar + price stretched far from its
moving average. Output 0..100. ``> 70`` = high exhaustion risk.
Edge cases:
    * Empty input -> ``[]``.
    * ``period < 2`` -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.atr import atr
from app.strategy_engine.indicators.calculations.rsi import rsi
from app.strategy_engine.indicators.calculations.sma import sma


def exhaustion_score(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Composite 0..100 exhaustion score."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")
    n = len(closes)
    if n != len(highs) or n != len(lows):
        raise ValueError(
            f"highs/lows/closes must have the same length; "
            f"got {len(highs)}, {len(lows)}, {n}."
        )
    if n == 0:
        return []

    rsi_line = rsi(closes, period)
    sma_line = sma(closes, period)
    atr_line = atr(highs, lows, closes, period)
    if not rsi_line or not sma_line or not atr_line:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(n):
        r = rsi_line[i]
        s = sma_line[i]
        t = atr_line[i]
        if r is None or s is None or t is None or t == 0:
            continue
        if i < period:
            continue
        rsi_part = _clamp((abs(r - 50.0) - 25.0) / 25.0, 0.0, 1.0) * 30.0

        avg_range = sum(highs[j] - lows[j] for j in range(i - period + 1, i + 1)) / period
        if avg_range <= 0:
            blowoff_part = 0.0
        else:
            bar_range = highs[i] - lows[i]
            blowoff_part = _clamp((bar_range - avg_range) / avg_range, 0.0, 2.0) / 2.0 * 35.0

        stretch_part = _clamp(abs(closes[i] - s) / (3.0 * t), 0.0, 1.0) * 35.0
        out[i] = rsi_part + blowoff_part + stretch_part
    return out


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


__all__ = ["exhaustion_score"]
