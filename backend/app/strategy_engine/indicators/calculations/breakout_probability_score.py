"""Breakout Probability Score - 0..100 squeeze + volume composite.

Synthesises three Pack 2-16 / volume primitives::

    bbw_part   = clamp(1 - bbw_now / mean(bbw[last period]),
                       0, 1)                                 * 50
    range_part = clamp(1 - range_short / range_long,
                       0, 1)                                 * 30
    vol_part   = clamp(vol_now / mean(vol[last period]) - 1,
                       0, 1)                                 * 20
    score      = bbw_part + range_part + vol_part

The intuition: bandwidth contracted vs trailing average + recent
ranges contracted vs the longer window + volume rising = setup
for a breakout. Output 0..100. ``> 70`` is the rule-of-thumb
"watch for a breakout" zone.

Output length matches input.
Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period < 5`` -> ``ValueError`` (need usable trailing window).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.bollinger_bandwidth import (
    bollinger_bandwidth,
)


def breakout_probability_score(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
    period: int = 20,
) -> list[float | None]:
    """Composite 0..100 breakout-probability score."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 5:
        raise ValueError(f"period must be an int >= 5; got {period!r}.")
    n = len(closes)
    if n != len(highs) or n != len(lows) or n != len(volumes):
        raise ValueError(
            f"all input series must have the same length; got "
            f"highs={len(highs)}, lows={len(lows)}, closes={n}, "
            f"volumes={len(volumes)}."
        )
    if n == 0:
        return []

    bbw_line = bollinger_bandwidth(closes, period, 2.0)
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
        bbw_window = [bbw_line[j] for j in range(i - period + 1, i + 1)]
        bbw_defined = [v for v in bbw_window if v is not None]
        if not bbw_defined:
            continue
        bbw_avg = sum(bbw_defined) / len(bbw_defined)
        if bbw_avg == 0:
            continue
        bbw_part = _clamp(1.0 - bbw_now / bbw_avg, 0.0, 1.0) * 50.0

        r_short = sum(highs[j] - lows[j] for j in range(i - short_window + 1, i + 1)) / short_window
        r_long = sum(highs[j] - lows[j] for j in range(i - period + 1, i + 1)) / period
        if r_long == 0:
            continue
        range_part = _clamp(1.0 - r_short / r_long, 0.0, 1.0) * 30.0

        vol_avg = sum(volumes[j] for j in range(i - period + 1, i + 1)) / period
        vol_part = 0.0 if vol_avg == 0 else _clamp(volumes[i] / vol_avg - 1.0, 0.0, 1.0) * 20.0

        out[i] = bbw_part + range_part + vol_part
    return out


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


__all__ = ["breakout_probability_score"]
