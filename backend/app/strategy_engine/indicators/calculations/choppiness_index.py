"""Choppiness Index (E. W. Dreiss).

Definition::

    TR_sum  = sum(true_range over period)
    HH      = max(high  over period)
    LL      = min(low   over period)
    CI      = 100 * log10(TR_sum / (HH - LL)) / log10(period)

Output range is roughly 0-100. High values (> ~61.8) indicate a
choppy / range-bound market; low values (< ~38.2) indicate a
trending market. The asymmetric thresholds come from Fibonacci
levels and are operator preference, not a property of the formula.

Default ``period = 14``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period < 2`` -> ``ValueError`` (log10(1) = 0 → div-by-zero).
    * ``HH == LL`` over the window -> ``None`` for that bar (range
      collapsed; the formula's input is undefined). Real markets
      almost never hit this; documented for completeness.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def choppiness_index(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """E. W. Dreiss' Choppiness Index over a rolling window."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(
            f"period must be an int >= 2 (log10 base); got {period!r}."
        )
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0 or period >= n:
        return []

    # Pre-compute true range so the rolling sum is cheap.
    true_range = [highs[0] - lows[0]]
    for i in range(1, n):
        prev_close = closes[i - 1]
        true_range.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - prev_close),
                abs(lows[i] - prev_close),
            )
        )

    log_period = math.log10(period)
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        tr_sum = sum(true_range[i - period + 1 : i + 1])
        hh = max(highs[i - period + 1 : i + 1])
        ll = min(lows[i - period + 1 : i + 1])
        rng = hh - ll
        if rng == 0 or tr_sum == 0:
            continue  # leave as None
        out[i] = 100.0 * math.log10(tr_sum / rng) / log_period
    return out


__all__ = ["choppiness_index"]
