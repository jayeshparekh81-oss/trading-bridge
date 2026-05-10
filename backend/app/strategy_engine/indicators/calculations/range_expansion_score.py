"""Range expansion score - short-window vs long-window true range.

ML-style feature. Output is the unitless ratio::

    short_range = mean(high[j] - low[j]) over last `short` bars
    long_range  = mean(high[j] - low[j]) over last `long` bars
    score       = short_range / long_range - 1.0

So ``0`` = neutral (recent ranges match the long-window average),
positive = expanding, negative = contracting. Useful as an ML
feature for breakout / consolidation context.

Output length matches input. Positions ``0 .. long - 1`` are
``None``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``short < 1`` or ``long < short`` -> ``ValueError``.
    * ``long > n`` -> ``[]``.
    * ``long_range == 0`` for a bar -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence


def range_expansion_score(
    highs: Sequence[float],
    lows: Sequence[float],
    short: int = 5,
    long: int = 20,
) -> list[float | None]:
    """short-window range / long-window range - 1."""
    if not isinstance(short, int) or isinstance(short, bool) or short < 1:
        raise ValueError(f"short must be a positive int; got {short!r}.")
    if not isinstance(long, int) or isinstance(long, bool) or long < short:
        raise ValueError(
            f"long must be an int >= short; got short={short!r}, long={long!r}."
        )
    n = len(highs)
    if n != len(lows):
        raise ValueError(
            f"highs and lows must have the same length; got {n}, {len(lows)}."
        )
    if n == 0 or long > n:
        return []
    out: list[float | None] = [None] * n
    for i in range(long - 1, n):
        s_sum = 0.0
        for j in range(i - short + 1, i + 1):
            s_sum += highs[j] - lows[j]
        l_sum = 0.0
        for j in range(i - long + 1, i + 1):
            l_sum += highs[j] - lows[j]
        long_avg = l_sum / long
        if long_avg == 0:
            continue
        out[i] = (s_sum / short) / long_avg - 1.0
    return out


__all__ = ["range_expansion_score"]
