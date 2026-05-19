"""Standard Error Channel — OLS regression line with SEE bands.

Definition (LOCKED per reference doc):
    At each bar ``t`` with ``t >= length - 1``:
        Fit OLS line y_hat[i] = a + b*x[i] where x = 0..length-1,
        y = closes[t - length + 1 .. t].

        residuals[i] = y[i] - y_hat[i]
        SEE  = sqrt(sum(residuals²) / (length - 2))   # standard error of estimate

        line[t]  = a + b * (length - 1)
        upper[t] = line[t] + multiplier * SEE
        lower[t] = line[t] - multiplier * SEE

    Defaults: ``length = 20``, ``multiplier = 2.0``.
    First defined index = ``length - 1``.

    NOTE: SEE divides by ``length - 2`` (not ``length`` like a raw stdev).
    This distinguishes the channel from a "raw-stdev channel" — the
    extra two degrees of freedom are consumed by fitting the slope +
    intercept of the regression.

Output: tuple (line, upper, lower), each list of length ``n``.

Edge cases:
    * Empty input -> ([], [], [])
    * ``length > n`` -> all-None triples
    * ``length < 3`` -> ValueError (SEE divisor would be 0 or negative)
    * Window variance == 0 (vertical price stack) -> b = 0; line = y_mean

Source: standard OLS statistics; widely-used Pine indicator pattern.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def standard_error_channel(
    closes: Sequence[float],
    length: int = 20,
    multiplier: float = 2.0,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """OLS regression channel with Standard Error of Estimate bands."""
    if not isinstance(length, int) or isinstance(length, bool) or length < 3:
        raise ValueError(
            f"length must be int >= 3 (for SEE divisor n-2); got {length!r}."
        )
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

    # Pre-compute x stats (constant across windows of fixed length)
    x_vals = list(range(length))
    x_mean = (length - 1) / 2.0
    x_var = sum((xi - x_mean) ** 2 for xi in x_vals)
    last_x = length - 1

    for t in range(length - 1, n):
        window = [float(closes[t - length + 1 + k]) for k in range(length)]
        y_mean = sum(window) / length
        cov_xy = sum((x_vals[i] - x_mean) * (window[i] - y_mean) for i in range(length))
        if x_var == 0.0:  # length=1 would hit this, but length>=3 guarantees x_var>0
            b = 0.0
        else:
            b = cov_xy / x_var
        a = y_mean - b * x_mean

        line_t = a + b * last_x
        residuals_sq = 0.0
        for i in range(length):
            y_hat_i = a + b * x_vals[i]
            r = window[i] - y_hat_i
            residuals_sq += r * r
        # SEE divisor: length - 2 (degrees of freedom for OLS slope+intercept)
        see = math.sqrt(residuals_sq / (length - 2))

        line[t] = line_t
        upper[t] = line_t + multiplier * see
        lower[t] = line_t - multiplier * see

    return (line, upper, lower)


__all__ = ["standard_error_channel"]
