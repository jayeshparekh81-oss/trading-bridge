"""Linear Regression (LSMA) value at the end of the trailing window.

Often called the "Least Squares Moving Average" or "Linear Regression
Curve". For every bar we fit ``y = a*x + b`` to the last ``period``
samples (``x = 0 .. period - 1``) and emit the regressed value at the
*current* bar — i.e. ``a * (period - 1) + b``.

Closed-form OLS coefficients (with mean-centred x to avoid catastrophic
cancellation on long windows)::

    n  = period
    sx = (n - 1) / 2
    Sxx = sum((x - sx) ** 2)            # = (n^3 - n) / 12
    Sxy = sum((x - sx) * (y - mean(y)))
    a  = Sxy / Sxx
    b  = mean(y) - a * sx
    LSMA[i] = a * (n - 1) + b
            = mean(y) + a * ((n - 1) - sx)
            = mean(y) + a * (n - 1) / 2

Output length equals input length. Indices ``0 .. period - 2`` are
``None``; from ``period - 1`` onward the regression value lives.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period > len(values)`` -> ``[]``.
    * ``period < 2`` rejected — a single-point regression is undefined.
"""

from __future__ import annotations

from collections.abc import Sequence


def linear_regression(values: Sequence[float], period: int = 14) -> list[float | None]:
    """LSMA value at the end of every ``period``-bar window."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")

    n = len(values)
    if n == 0 or period > n:
        return []

    n_f = float(period)
    sx = (n_f - 1) / 2.0
    sxx = (period ** 3 - period) / 12.0  # closed form for sum((x - sx) ** 2)

    out: list[float | None] = [None] * (period - 1)
    for end in range(period - 1, n):
        window = values[end - period + 1 : end + 1]
        mean_y = sum(window) / n_f
        sxy = sum((k - sx) * (window[k] - mean_y) for k in range(period))
        slope = sxy / sxx
        # LSMA at the most recent bar.
        out.append(mean_y + slope * (n_f - 1) / 2.0)
    return out


__all__ = ["linear_regression"]
