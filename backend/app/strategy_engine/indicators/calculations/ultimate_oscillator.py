"""Ultimate Oscillator (Williams, 1976).

Definition::

    BP[i] = close[i] - min(low[i], close[i - 1])                  # buying pressure
    TR[i] = max(high[i], close[i - 1]) - min(low[i], close[i - 1])

    For the three windows (default 7, 14, 28)::
        avgN = sum(BP[i - N + 1 .. i]) / sum(TR[i - N + 1 .. i])

    UO = 100 * (4 * avg7 + 2 * avg14 + avg28) / 7

The weighted average over short / medium / long windows softens
divergences in any single window. Output range is 0-100.

Output length equals input length. Indices ``0 .. period_long - 1``
are ``None`` (the longest window's first defined value is at
``period_long - 1``; we additionally need ``close[i - 1]`` so the
true first defined index is ``period_long`` — see invariants below).

Edge cases:
    * Empty input or mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period_long > len(highs)`` -> empty.
    * Periods must satisfy ``short < medium < long`` and be positive
      ints; violation -> ``ValueError``.
    * ``sum(TR_window) == 0`` (perfectly flat window) -> ``avg = 0``.
"""

from __future__ import annotations

from collections.abc import Sequence


def ultimate_oscillator(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    short_period: int = 7,
    medium_period: int = 14,
    long_period: int = 28,
) -> list[float | None]:
    """Williams Ultimate Oscillator over the three configured windows."""
    _check_period(short_period, "short_period")
    _check_period(medium_period, "medium_period")
    _check_period(long_period, "long_period")
    if not (short_period < medium_period < long_period):
        raise ValueError(
            "Periods must satisfy short < medium < long; got "
            f"{short_period}, {medium_period}, {long_period}."
        )

    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n <= long_period:
        return []

    bp = [0.0] * n
    tr = [0.0] * n
    for i in range(1, n):
        prev_close = closes[i - 1]
        true_low = min(lows[i], prev_close)
        true_high = max(highs[i], prev_close)
        bp[i] = closes[i] - true_low
        tr[i] = true_high - true_low

    out: list[float | None] = [None] * n
    for i in range(long_period, n):
        avg_short = _ratio(bp, tr, i, short_period)
        avg_medium = _ratio(bp, tr, i, medium_period)
        avg_long = _ratio(bp, tr, i, long_period)
        out[i] = 100.0 * (4 * avg_short + 2 * avg_medium + avg_long) / 7.0
    return out


def _ratio(bp: list[float], tr: list[float], end: int, period: int) -> float:
    bp_sum = sum(bp[end - period + 1 : end + 1])
    tr_sum = sum(tr[end - period + 1 : end + 1])
    if tr_sum == 0:
        return 0.0
    return bp_sum / tr_sum


def _check_period(period: int, name: str) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"{name} must be a positive int; got {period!r}.")


__all__ = ["ultimate_oscillator"]
