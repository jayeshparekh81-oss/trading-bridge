"""Trend Quality Score - 0..100 composite of trend strength signals.

Synthesises three Pack 2-16 primitives into a single 0..100 score::

    adx_part         = clamp(adx / 50, 0, 1)              * 40
    distance_part    = clamp(|close - sma| / (2 * atr),
                             0, 1)                        * 30
    alignment_part   = (count of last `period` bars where
                        sign(close - sma) is consistent
                        with the current trend direction
                        / period)                         * 30
    score            = adx_part + distance_part + alignment_part

Higher score = stronger, more consistent trend. The breakdown is
not a forecast - it's a regime tag (use ``> 60`` as "trending",
``< 30`` as "ranging" rule-of-thumb).

Output length matches input. ``None`` until ADX has seeded
(``2 * period - 1`` bars).

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period < 2`` -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.adx import adx
from app.strategy_engine.indicators.calculations.atr import atr
from app.strategy_engine.indicators.calculations.sma import sma


def trend_quality_score(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Composite 0..100 trend-quality score over ``period`` bars."""
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

    adx_line, _plus, _minus = adx(highs, lows, closes, period)
    atr_line = atr(highs, lows, closes, period)
    sma_line = sma(closes, period)
    if not adx_line or not atr_line or not sma_line:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(n):
        a = adx_line[i]
        t = atr_line[i]
        s = sma_line[i]
        if a is None or t is None or s is None or t == 0:
            continue
        if i < period:
            continue
        adx_part = _clamp(a / 50.0, 0.0, 1.0) * 40.0
        distance_part = _clamp(abs(closes[i] - s) / (2.0 * t), 0.0, 1.0) * 30.0
        trend_dir = 1 if closes[i] >= s else -1
        aligned = 0
        for j in range(i - period + 1, i + 1):
            sj = sma_line[j]
            if sj is None:
                continue
            this_dir = 1 if closes[j] >= sj else -1
            if this_dir == trend_dir:
                aligned += 1
        alignment_part = (aligned / period) * 30.0
        out[i] = adx_part + distance_part + alignment_part
    return out


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


__all__ = ["trend_quality_score"]
