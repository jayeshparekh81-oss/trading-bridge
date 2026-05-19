"""Standard Deviation — TradingView-parity rolling population stdev.

Definition (matches ``ta.stdev`` in Pine v5/v6):
    For each bar i with ``i >= period - 1``:
        mean[i] = (1 / period) * sum(values[i - period + 1 .. i])
        var[i]  = (1 / period) * sum((values[k] - mean[i])^2
                                     for k in [i - period + 1 .. i])
        stdev[i] = sqrt(var[i])

    Population variance (divisor ``period``), NOT sample variance
    (divisor ``period - 1``) — this matches Pine's behaviour.
    Positions ``0 .. period - 2`` are ``None``.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``
    * ``period > len(values)`` -> ``[]``
    * ``period == 1`` -> stdev is exactly 0 at every position
      (single-value window has zero variance)

Source: TradingView ``ta.stdev`` reference; standard statistics.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def standard_deviation(values: Sequence[float], period: int = 20) -> list[float | None]:
    """Rolling population standard deviation (Pine ``ta.stdev`` parity)."""
    _check_period(period)
    n = len(values)
    if n == 0 or period > n:
        return []

    out: list[float | None] = [None] * (period - 1)
    inv_period = 1.0 / period

    # Rolling sum + rolling sum-of-squares lets us compute mean + variance
    # in O(1) per step after the initial O(period) seed.
    window_sum = 0.0
    window_sq_sum = 0.0
    for k in range(period):
        v = float(values[k])
        window_sum += v
        window_sq_sum += v * v

    # First defined position: index = period - 1
    mean = window_sum * inv_period
    var = window_sq_sum * inv_period - mean * mean
    # Floating-point safety: variance can come out very slightly negative
    # for windows where all values are equal (e.g. -1e-17 from rounding).
    if var < 0.0:
        var = 0.0
    out.append(math.sqrt(var))

    for i in range(period, n):
        old = float(values[i - period])
        new = float(values[i])
        window_sum += new - old
        window_sq_sum += new * new - old * old
        mean = window_sum * inv_period
        var = window_sq_sum * inv_period - mean * mean
        if var < 0.0:
            var = 0.0
        out.append(math.sqrt(var))

    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["standard_deviation"]
