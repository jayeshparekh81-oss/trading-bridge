"""Consolidation Breakout Score - 0..100 squeeze-with-duration composite.

Distinct from ``breakout_probability_score`` - that one weights
*volume rising* (build-up) while this one weights *consolidation
duration* (the longer the squeeze, the bigger the eventual move).

    bbw_squeeze_part   = clamp((bbw_avg - bbw_now) / bbw_avg,
                               0, 1)                             * 40
    range_tight_part   = clamp(1 - r_short / r_long, 0, 1)       * 30
    duration_part      = (consecutive bars with bbw < bbw_avg
                          / period)                              * 30
    score              = sum

Output 0..100. Edge cases:
    * Empty input -> ``[]``.
    * ``period < 5`` -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.bollinger_bandwidth import (
    bollinger_bandwidth,
)


def consolidation_breakout_score(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Composite 0..100 consolidation-breakout score."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 5:
        raise ValueError(f"period must be an int >= 5; got {period!r}.")
    n = len(closes)
    if n != len(highs) or n != len(lows):
        raise ValueError(
            f"highs/lows/closes must have the same length; "
            f"got {len(highs)}, {len(lows)}, {n}."
        )
    if n == 0:
        return []

    bbw_line = bollinger_bandwidth(closes, 20, 2.0)
    if not bbw_line:
        return [None] * n
    short_window = max(2, period // 4)

    out: list[float | None] = [None] * n
    for i in range(n):
        if i < period:
            continue
        bbw_now = bbw_line[i]
        if bbw_now is None:
            continue
        window_vals = [bbw_line[j] for j in range(i - period + 1, i + 1)]
        defined = [v for v in window_vals if v is not None]
        if not defined:
            continue
        bbw_avg = sum(defined) / len(defined)
        if bbw_avg == 0:
            continue
        squeeze_part = _clamp((bbw_avg - bbw_now) / bbw_avg, 0.0, 1.0) * 40.0

        r_short = sum(highs[j] - lows[j] for j in range(i - short_window + 1, i + 1)) / short_window
        r_long = sum(highs[j] - lows[j] for j in range(i - period + 1, i + 1)) / period
        tight_part = 0.0 if r_long == 0 else _clamp(1.0 - r_short / r_long, 0.0, 1.0) * 30.0

        run = 0
        for j in range(i, i - period, -1):
            v = bbw_line[j]
            if v is None or v >= bbw_avg:
                break
            run += 1
        duration_part = (run / period) * 30.0

        out[i] = squeeze_part + tight_part + duration_part
    return out


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


__all__ = ["consolidation_breakout_score"]
