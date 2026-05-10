"""Exponential regression slope.

Fits ``y = a * exp(b * x)`` to the trailing window by linearising:
``log(y) = log(a) + b*x``, then OLS-fit log(y) on x. Emits the
``b`` slope — the per-bar exponential growth rate.

    > 0 -> exponential growth fit
    < 0 -> exponential decay fit

Default ``period = 30``.

Output length equals input length. ``None`` for the warm-up
plus any bar where any window value is non-positive (log
undefined).

Edge cases:
    * Empty input -> ``[]``.
    * ``period < 2`` rejected.
    * ``period > n`` -> ``[]``.
    * Window contains a value <= 0 -> ``None`` (log undefined).
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def exponential_regression(
    values: Sequence[float], period: int = 30,
) -> list[float | None]:
    """Per-bar exponential-fit slope coefficient ``b``."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")
    n = len(values)
    if n == 0 or period > n:
        return []
    sx = (period - 1) / 2.0
    sxx = (period ** 3 - period) / 12.0
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        window = values[i - period + 1 : i + 1]
        if any(v <= 0 for v in window):
            continue
        log_window = [math.log(v) for v in window]
        mean_log_y = sum(log_window) / period
        sxy = sum(
            (k - sx) * (log_window[k] - mean_log_y) for k in range(period)
        )
        out[i] = sxy / sxx
    return out


__all__ = ["exponential_regression"]
