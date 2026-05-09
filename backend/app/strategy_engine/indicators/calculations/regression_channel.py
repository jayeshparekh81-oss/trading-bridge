"""Linear Regression Channel — best-fit line + ±k * residual stddev.

Three outputs: ``(middle, upper, lower)``.

Definition:

    For each window of ``period`` closes ending at index ``i``:
        Fit y = a + b * x where x = 0..period-1 (least squares).
        Compute residuals r[k] = y[k] - (a + b * k).
        sigma = stdev(r[0..period-1]) using the population
                (n-denominator) variance to match Pine's ta.stdev.

        middle[i] = a + b * (period - 1)        (line value at last bar)
        upper[i]  = middle[i] + std_dev * sigma
        lower[i]  = middle[i] - std_dev * sigma

Edge cases per Phase 1 contract:
    * Empty input -> ``([], [], [])``.
    * ``period > len(values)`` -> ``([], [], [])``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def regression_channel(
    values: Sequence[float],
    period: int = 20,
    std_dev: float = 2.0,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Return ``(middle, upper, lower)`` linear-regression channel."""
    if not isinstance(period, int) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")
    if std_dev <= 0:
        raise ValueError(f"std_dev must be > 0; got {std_dev!r}.")
    n = len(values)
    if n == 0 or period > n:
        return ([], [], [])

    middle: list[float | None] = [None] * n
    upper: list[float | None] = [None] * n
    lower: list[float | None] = [None] * n

    # Pre-compute the constants that depend only on ``period``.
    xs = list(range(period))
    mean_x = (period - 1) / 2.0
    sum_xx = sum((k - mean_x) ** 2 for k in xs)

    for i in range(period - 1, n):
        window = values[i - period + 1 : i + 1]
        mean_y = sum(window) / period
        sum_xy = sum((xs[k] - mean_x) * (window[k] - mean_y) for k in xs)
        if sum_xx == 0.0:
            continue  # period == 1 was rejected above; this is defensive.
        slope = sum_xy / sum_xx
        intercept = mean_y - slope * mean_x
        line_values = [intercept + slope * k for k in xs]
        residuals = [window[k] - line_values[k] for k in xs]
        var = sum(r * r for r in residuals) / period
        sigma = math.sqrt(var)
        m = intercept + slope * (period - 1)
        middle[i] = m
        upper[i] = m + std_dev * sigma
        lower[i] = m - std_dev * sigma
    return (middle, upper, lower)


__all__ = ["regression_channel"]
