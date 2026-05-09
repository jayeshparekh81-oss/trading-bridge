"""Standard Deviation — population variant (n denominator).

Matches Pine ``ta.stdev(source, length)`` which uses the biased
(n-denominator) variance internally.

    mean[i] = sum(values[i - period + 1..i]) / period
    var[i]  = sum((values[j] - mean[i]) ** 2 for j in window) / period
    std[i]  = sqrt(var[i])

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period > len(values)`` -> ``[]``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def std_dev(values: Sequence[float], period: int = 20) -> list[float | None]:
    """Population standard deviation over ``period`` bars."""
    _check_period(period)
    n = len(values)
    if n == 0 or period > n:
        return []

    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        window = values[i - period + 1 : i + 1]
        mean = sum(window) / period
        var = sum((v - mean) ** 2 for v in window) / period
        out[i] = math.sqrt(var)
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["std_dev"]
