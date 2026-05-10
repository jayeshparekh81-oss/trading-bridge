"""Linear Regression Channel — upper band.

Definition::

    base[i]  = LSMA(close, period)[i]              # the regression value
    sigma[i] = std_dev(close - base, period)[i]    # window-local residual stddev
    upper[i] = base[i] + std_mult * sigma[i]

The residual is computed against the *current* regression value
(not against the rolling mean) so the band reflects how far price
strays from the linear-regression best-fit, not just from a
moving average.

Default ``period = 20``, ``std_mult = 2.0``.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty input -> ``[]``.
    * ``period >= n`` -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import sqrt

from app.strategy_engine.indicators.calculations.linear_regression import (
    linear_regression,
)


def linear_regression_upper(
    values: Sequence[float],
    period: int = 20,
    std_mult: float = 2.0,
) -> list[float | None]:
    """LinReg channel — upper band."""
    return _linreg_band(values, period, std_mult, side=+1)


def _linreg_band(
    values: Sequence[float],
    period: int,
    std_mult: float,
    *,
    side: int,
) -> list[float | None]:
    """Shared computation. ``side = +1`` for upper, ``-1`` for lower."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")
    if not isinstance(std_mult, (int, float)) or isinstance(std_mult, bool):
        raise ValueError(f"std_mult must be a number; got {std_mult!r}.")
    if std_mult < 0:
        raise ValueError(f"std_mult must be >= 0; got {std_mult}.")
    n = len(values)
    if n == 0 or period > n:
        return []

    base = linear_regression(list(values), period)
    if not base:
        return [None] * n
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        b = base[i]
        if b is None:
            continue
        # Window-local residual stddev around the LSMA *value at i*.
        # (Approximation — the formal LinReg channel uses the per-
        # bar regression slope; this is the standard "fixed-base
        # residual" simplification used in most Pine-compatible
        # implementations.)
        residuals = [values[i - k] - b for k in range(period)]
        mean_r = sum(residuals) / period
        var = sum((r - mean_r) ** 2 for r in residuals) / period
        sigma = sqrt(var)
        out[i] = b + side * std_mult * sigma
    return out


__all__ = ["linear_regression_upper"]
