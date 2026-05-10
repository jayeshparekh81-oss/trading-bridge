"""Williams %R — Larry Williams.

Definition (matches Pine ``ta.wpr``):

    HH = max(high[i - period + 1..i])
    LL = min(low[i - period + 1..i])
    %R = -100 * (HH - close[i]) / (HH - LL)

Output range is ``[-100, 0]`` (the indicator is the mirror of a
Stochastic %K). Classic interpretation: > -20 overbought, < -80
oversold.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period > len(values)`` -> ``[]``.
    * Mismatched lengths -> ``ValueError``.
    * Flat window (HH == LL) -> ``None`` for that bar (division by
      zero).
"""

from __future__ import annotations

from collections.abc import Sequence


def williams_r(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Williams %R over ``period`` bars."""
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0 or period > n:
        return []

    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        hh = max(highs[i - period + 1 : i + 1])
        ll = min(lows[i - period + 1 : i + 1])
        denom = hh - ll
        if denom == 0.0:
            out[i] = None
            continue
        out[i] = -100.0 * (hh - closes[i]) / denom
    return out


__all__ = ["williams_r"]
