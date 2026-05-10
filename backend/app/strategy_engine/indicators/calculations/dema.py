"""Double Exponential Moving Average (Mulloy, 1994).

Definition (matches Pine ``ta.dema``):

    EMA1 = ema(values, period)
    EMA2 = ema(EMA1, period)
    DEMA = 2 * EMA1 - EMA2

DEMA reacts faster than a single EMA at the cost of slightly more
noise. Output length equals input length; positions where either
EMA is undefined are ``None``.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``2 * period - 1 > len(values)`` -> the second EMA cannot
      seed; the bars where EMA2 is undefined are ``None``.
"""

from __future__ import annotations

from collections.abc import Sequence


def dema(values: Sequence[float], period: int = 20) -> list[float | None]:
    """Double EMA over ``period`` bars."""
    _check_period(period)
    n = len(values)
    if n == 0 or period > n:
        return []

    ema1 = _ema(values, period)
    # Build a defined-only series for EMA2's input, preserving index.
    ema1_defined = [v for v in ema1 if v is not None]
    ema2_dense = _ema(ema1_defined, period)

    # Re-align EMA2 back into the original index space. The first
    # ``period - 1`` values of ``ema1`` are None; EMA2 then needs
    # another ``period - 1`` warm-up bars.
    out: list[float | None] = [None] * n
    first_ema1_idx = period - 1
    for j, e2 in enumerate(ema2_dense):
        if e2 is None:
            continue
        i = first_ema1_idx + j
        if i >= n:
            break
        e1 = ema1[i]
        if e1 is None:
            continue
        out[i] = 2.0 * e1 - e2
    return out


def _ema(values: Sequence[float], period: int) -> list[float | None]:
    """SMA-seeded EMA (matches Pine ``ta.ema``)."""
    n = len(values)
    if n == 0 or period > n:
        return [None] * n

    out: list[float | None] = [None] * n
    seed = sum(values[i] for i in range(period)) / period
    out[period - 1] = seed
    alpha = 2.0 / (period + 1)
    prev = seed
    for i in range(period, n):
        prev = alpha * values[i] + (1.0 - alpha) * prev
        out[i] = prev
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["dema"]
