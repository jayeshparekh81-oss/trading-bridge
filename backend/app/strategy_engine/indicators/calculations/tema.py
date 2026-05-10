"""Triple Exponential Moving Average (Mulloy, 1994).

Definition (matches Pine ``ta.tema``):

    EMA1 = ema(values, period)
    EMA2 = ema(EMA1, period)
    EMA3 = ema(EMA2, period)
    TEMA = 3 * EMA1 - 3 * EMA2 + EMA3

Output length equals input length; bars where any of the three
EMAs are undefined yield ``None``.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``3 * period - 2 > len(values)`` -> EMA3 cannot seed; those
      bars are ``None``.
"""

from __future__ import annotations

from collections.abc import Sequence


def tema(values: Sequence[float], period: int = 20) -> list[float | None]:
    """Triple EMA over ``period`` bars."""
    _check_period(period)
    n = len(values)
    if n == 0 or period > n:
        return []

    ema1 = _ema(values, period)
    ema1_defined = [v for v in ema1 if v is not None]
    ema2_dense = _ema(ema1_defined, period)
    ema2_defined = [v for v in ema2_dense if v is not None]
    ema3_dense = _ema(ema2_defined, period)

    # Each "dense" series starts at the first index where its parent
    # is defined; offset them back into the original index space.
    first_ema1_idx = period - 1
    first_ema2_idx = first_ema1_idx + (period - 1)
    out: list[float | None] = [None] * n

    # Build dense -> sparse alignment for EMA2 first.
    ema2_aligned: list[float | None] = [None] * n
    for j, e2 in enumerate(ema2_dense):
        if e2 is None:
            continue
        i = first_ema1_idx + j
        if i >= n:
            break
        ema2_aligned[i] = e2

    # Then EMA3 (parent series is ema2_dense; align relative to
    # first_ema2_idx in the original index space).
    for j, e3 in enumerate(ema3_dense):
        if e3 is None:
            continue
        i = first_ema2_idx + j
        if i >= n:
            break
        e1 = ema1[i]
        e2 = ema2_aligned[i]
        if e1 is None or e2 is None:
            continue
        out[i] = 3.0 * e1 - 3.0 * e2 + e3
    return out


def _ema(values: Sequence[float], period: int) -> list[float | None]:
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


__all__ = ["tema"]
