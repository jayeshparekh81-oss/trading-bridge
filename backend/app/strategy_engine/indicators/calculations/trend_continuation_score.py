"""Trend Continuation Score - 0..100 likelihood the trend persists.

Synthesises three Pack 2-16 primitives::

    adx_part        = clamp(adx / 40, 0, 1)            * 40
    consistency_part = (count of last `period` bars where
                        sign(close - sma) matches the
                        current trend / period)        * 30
    macd_align_part = (macd_hist sign matches trend)   * 30
    score           = adx_part + consistency_part + macd_align_part

Different from ``trend_quality_score`` (which weights distance-
from-mean as a strength tag). Continuation is about *persistence
forecast* - momentum aligned with trend + price consistently on
one side of the MA.

Output 0..100. ``> 70`` = strong continuation candidate.
Edge cases mirror ``trend_quality_score``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.adx import adx
from app.strategy_engine.indicators.calculations.macd import macd
from app.strategy_engine.indicators.calculations.sma import sma


def trend_continuation_score(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Composite 0..100 trend-continuation score."""
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
    sma_line = sma(closes, period)
    _macd_line, _sig_line, hist_line = macd(closes)
    if not adx_line or not sma_line or not hist_line:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(n):
        a = adx_line[i]
        s = sma_line[i]
        h = hist_line[i]
        if a is None or s is None or h is None:
            continue
        if i < period:
            continue
        adx_part = _clamp(a / 40.0, 0.0, 1.0) * 40.0
        trend_dir = 1 if closes[i] >= s else -1
        aligned = 0
        for j in range(i - period + 1, i + 1):
            sj = sma_line[j]
            if sj is None:
                continue
            this_dir = 1 if closes[j] >= sj else -1
            if this_dir == trend_dir:
                aligned += 1
        consistency_part = (aligned / period) * 30.0
        macd_align_part = 30.0 if (h >= 0 and trend_dir == 1) or (h < 0 and trend_dir == -1) else 0.0
        out[i] = adx_part + consistency_part + macd_align_part
    return out


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


__all__ = ["trend_continuation_score"]
