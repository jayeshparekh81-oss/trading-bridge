"""Consecutive Higher Lows - count of consecutive HL bars (capped at lookback).

Running-count line. At each bar i::

    count[i] = count[i - 1] + 1   if low[i] > low[i - 1]
    count[i] = 0                  otherwise
    count[i] = min(count[i], lookback)   # cap at the lookback window

Output is in ``[0, lookback]``. Useful as a structural-uptrend detector
- many breakout strategies require N consecutive HLs before a
trigger.

Output length matches input. Position 0 is ``0.0`` (no prior bar).

Edge cases:
    * Empty input -> ``[]``.
    * ``lookback < 1`` -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence


def consecutive_higher_lows(
    lows: Sequence[float],
    lookback: int = 10,
) -> list[float | None]:
    """Running count of consecutive HL bars, capped at ``lookback``."""
    if not isinstance(lookback, int) or isinstance(lookback, bool) or lookback < 1:
        raise ValueError(f"lookback must be a positive int; got {lookback!r}.")
    n = len(lows)
    if n == 0:
        return []
    out: list[float | None] = [0.0]
    count = 0
    for i in range(1, n):
        count = min(count + 1, lookback) if lows[i] > lows[i - 1] else 0
        out.append(float(count))
    return out


__all__ = ["consecutive_higher_lows"]
