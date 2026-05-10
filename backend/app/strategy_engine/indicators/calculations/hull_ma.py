"""Hull Moving Average (Alan Hull, 2005).

Definition (matches Pine ``ta.hma``):

    sqrt_period = int(sqrt(period))
    raw         = 2 * wma(values, period // 2) - wma(values, period)
    HMA         = wma(raw, sqrt_period)

HMA reacts faster than EMA / WMA while staying smooth — popular
on Indian-retail intraday charts.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * Insufficient bars for any of the inner WMAs -> ``None`` at
      those indices.
    * ``period < 2`` -> ``ValueError`` (sqrt would collapse).
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def hull_ma(values: Sequence[float], period: int = 20) -> list[float | None]:
    """Hull MA over ``period`` bars."""
    _check_period(period)
    n = len(values)
    if n == 0 or period > n:
        return []

    half = period // 2
    sqrt_p = int(math.sqrt(period))
    if half < 1 or sqrt_p < 1:
        raise ValueError(f"period={period!r} too small for HMA.")

    wma_half = _wma(values, half)
    wma_full = _wma(values, period)

    raw: list[float | None] = [None] * n
    for i in range(n):
        a = wma_half[i]
        b = wma_full[i]
        if a is None or b is None:
            continue
        raw[i] = 2.0 * a - b

    # WMA on the raw series. Inner None-runs propagate as None.
    raw_defined = [v for v in raw if v is not None]
    if sqrt_p > len(raw_defined):
        return [None] * n

    inner = _wma(raw_defined, sqrt_p)
    first_raw_idx = max(half, period) - 1
    out: list[float | None] = [None] * n
    for j, v in enumerate(inner):
        if v is None:
            continue
        i = first_raw_idx + j
        if i >= n:
            break
        out[i] = v
    return out


def _wma(values: Sequence[float], period: int) -> list[float | None]:
    n = len(values)
    if n == 0 or period > n:
        return [None] * n

    weight_total = period * (period + 1) / 2.0
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        s = 0.0
        for k in range(period):
            s += values[i - period + 1 + k] * (k + 1)
        out[i] = s / weight_total
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")


__all__ = ["hull_ma"]
