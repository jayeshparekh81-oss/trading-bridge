"""Correlation with volume — close vs volume Pearson correlation.

Convenience wrapper over the existing :mod:`correlation_coefficient`
formula with fixed inputs (close, volume). Distinct from
:mod:`correlation_coefficient` (generic between any two series)
in that this is a named indicator with semantic meaning:
"is price moving with volume support?"

Definition::

    CWV[i] = Pearson(close[i - period + 1..i], volume[i - period + 1..i])

Output range is ``[-1, +1]``. Sustained > +0.6 = healthy
trending (price + volume in step); < -0.6 = divergent
(potential reversal candidate).

Default ``period = 20``.

Output length equals input length. Indices ``0 .. period - 2``
are ``None``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period > n`` -> ``[]``.
    * Window with zero variance in either series -> ``None`` for
      that bar (Pearson is undefined when stddev = 0).
"""

from __future__ import annotations

from collections.abc import Sequence
from math import sqrt


def correlation_with_volume(
    closes: Sequence[float],
    volumes: Sequence[float],
    period: int = 20,
) -> list[float | None]:
    """Rolling Pearson correlation of close vs volume."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")
    n = len(closes)
    if n != len(volumes):
        raise ValueError(
            f"closes and volumes must have the same length; got {n}, {len(volumes)}."
        )
    if n == 0 or period > n:
        return []

    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        c_window = closes[i - period + 1 : i + 1]
        v_window = volumes[i - period + 1 : i + 1]
        c_mean = sum(c_window) / period
        v_mean = sum(v_window) / period
        cov = sum((c - c_mean) * (v - v_mean) for c, v in zip(c_window, v_window, strict=True))
        c_var = sum((c - c_mean) ** 2 for c in c_window)
        v_var = sum((v - v_mean) ** 2 for v in v_window)
        if c_var == 0 or v_var == 0:
            continue
        out[i] = cov / sqrt(c_var * v_var)
    return out


__all__ = ["correlation_with_volume"]
