"""Volume Weighted Moving Average.

Definition (matches Pine ``ta.vwma``):

    VWMA[i] = sum(price[j] * volume[j] for j in i-period+1..i)
              / sum(volume[j]          for j in i-period+1..i)

    Positions ``0 .. period - 2`` are ``None`` (warm-up).

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period > len(values)`` -> ``[]``.
    * Mismatched lengths -> ``ValueError``.
    * Window with zero total volume -> ``None`` for that bar (the
      mean is undefined, not zero).
"""

from __future__ import annotations

from collections.abc import Sequence


def vwma(
    values: Sequence[float],
    volumes: Sequence[float],
    period: int = 20,
) -> list[float | None]:
    """Volume-weighted moving average over ``period`` bars."""
    _check_period(period)
    n = len(values)
    if n != len(volumes):
        raise ValueError(
            f"values and volumes must have the same length; got {n} and {len(volumes)}."
        )
    if n == 0 or period > n:
        return []

    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        v_total = 0.0
        pv_total = 0.0
        for j in range(i - period + 1, i + 1):
            v = volumes[j]
            v_total += v
            pv_total += values[j] * v
        out[i] = (pv_total / v_total) if v_total != 0.0 else None
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["vwma"]
