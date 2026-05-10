"""Z-Score — standardised distance of current bar from rolling mean.

Definition:

    mean[i] = sum(values[i - period + 1..i]) / period
    var[i]  = sum((v - mean[i]) ** 2) / period             (population)
    std[i]  = sqrt(var[i])

    zscore[i] = (values[i] - mean[i]) / std[i]

Used for mean-reversion entries (extreme |z| → reversion expected)
and for normalising any input series before feeding into a
threshold-based rule.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period > len(values)`` -> ``[]``.
    * Window with zero stdev (constant values) -> ``None`` (z is
      undefined when there's no variance).
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def zscore(values: Sequence[float], period: int = 20) -> list[float | None]:
    """Rolling z-score of ``values`` over the trailing ``period``."""
    _check_period(period)
    n = len(values)
    if n == 0 or period > n:
        return []

    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        window = values[i - period + 1 : i + 1]
        mean = sum(window) / period
        var = sum((v - mean) ** 2 for v in window) / period
        std = math.sqrt(var)
        if std == 0.0:
            continue
        out[i] = (values[i] - mean) / std
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["zscore"]
