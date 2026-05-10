"""Pearson Correlation Coefficient — rolling window between two series.

Matches Pine ``ta.correlation(source_a, source_b, length)``:

    mean_a    = mean(a[i - period + 1..i])
    mean_b    = mean(b[i - period + 1..i])
    cov       = sum((a[j] - mean_a) * (b[j] - mean_b)) / period
    std_a     = sqrt(sum((a[j] - mean_a) ** 2) / period)
    std_b     = sqrt(sum((b[j] - mean_b) ** 2) / period)
    corr      = cov / (std_a * std_b)

Output range is ``[-1, +1]``.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period > len(values)`` -> ``[]``.
    * Mismatched lengths -> ``ValueError``.
    * Either series flat (std == 0) over a window -> ``None``
      (correlation is undefined when one variable doesn't move).
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def correlation_coefficient(
    values_a: Sequence[float],
    values_b: Sequence[float],
    period: int = 20,
) -> list[float | None]:
    """Pearson correlation between ``values_a`` and ``values_b``."""
    _check_period(period)
    n = len(values_a)
    if n != len(values_b):
        raise ValueError(
            f"values_a and values_b must have the same length; "
            f"got {n} and {len(values_b)}."
        )
    if n == 0 or period > n:
        return []

    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        a = values_a[i - period + 1 : i + 1]
        b = values_b[i - period + 1 : i + 1]
        mean_a = sum(a) / period
        mean_b = sum(b) / period
        cov = sum((aj - mean_a) * (bj - mean_b) for aj, bj in zip(a, b, strict=True)) / period
        var_a = sum((aj - mean_a) ** 2 for aj in a) / period
        var_b = sum((bj - mean_b) ** 2 for bj in b) / period
        std_a = math.sqrt(var_a)
        std_b = math.sqrt(var_b)
        if std_a == 0.0 or std_b == 0.0:
            continue
        out[i] = cov / (std_a * std_b)
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["correlation_coefficient"]
