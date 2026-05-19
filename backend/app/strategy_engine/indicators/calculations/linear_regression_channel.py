"""Linear Regression Channel — regression line with raw-stdev bands.

Locked variant (per reference doc):
    length     = 100
    multiplier = 2.0
    centerline = existing linear_regression() calc (LSMA value at window end)
    residual_std = RAW STDEV of (actual - predicted) over window
                   (divides by n, NOT n-2)
    upper = centerline + multiplier * residual_std
    lower = centerline - multiplier * residual_std

DISTINCTION from standard_error_channel:
    SEC uses SEE = sqrt(SS_residuals / (n - 2))   — OLS degrees of freedom
    LRC uses raw stdev = sqrt(SS_residuals / n)   — just n

Returns: (line, upper, lower) — each list of length n.

Source: standard Pine community pattern; "DonovanWall" and other
public Pine variants typically use raw stdev for this indicator.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def linear_regression_channel(
    closes: Sequence[float],
    length: int = 100,
    multiplier: float = 2.0,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Linear regression line with raw-stdev residual bands."""
    if not isinstance(length, int) or isinstance(length, bool) or length < 2:
        raise ValueError(f"length must be int >= 2; got {length!r}.")
    if not isinstance(multiplier, (int, float)) or isinstance(multiplier, bool):
        raise ValueError(f"multiplier must be numeric; got {multiplier!r}.")
    if multiplier < 0:
        raise ValueError(f"multiplier must be >= 0; got {multiplier}.")
    n = len(closes)
    if n == 0:
        return ([], [], [])

    line: list[float | None] = [None] * n
    upper: list[float | None] = [None] * n
    lower: list[float | None] = [None] * n
    if length > n:
        return (line, upper, lower)

    x_vals = list(range(length))
    x_mean = (length - 1) / 2.0
    x_var = sum((xi - x_mean) ** 2 for xi in x_vals)
    last_x = length - 1

    for t in range(length - 1, n):
        window = [float(closes[t - length + 1 + k]) for k in range(length)]
        y_mean = sum(window) / length
        cov = sum((x_vals[i] - x_mean) * (window[i] - y_mean) for i in range(length))
        b = cov / x_var if x_var > 0 else 0.0
        a = y_mean - b * x_mean

        line_t = a + b * last_x
        residuals_sq = 0.0
        for i in range(length):
            y_hat_i = a + b * x_vals[i]
            r = window[i] - y_hat_i
            residuals_sq += r * r
        # RAW stdev: divisor = n (not n-2 like SEE).
        raw_std = math.sqrt(residuals_sq / length)

        line[t] = line_t
        upper[t] = line_t + multiplier * raw_std
        lower[t] = line_t - multiplier * raw_std

    return (line, upper, lower)


__all__ = ["linear_regression_channel"]
