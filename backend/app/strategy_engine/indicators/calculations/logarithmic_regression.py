"""Logarithmic regression slope.

Fits ``y = a + b * log(x + 1)`` to the trailing window. Useful
for series that decelerate over time (square-root-ish growth).
The ``+1`` shift avoids ``log(0)`` for the first window x.

Definition::

    log_x[k] = log(k + 1)                    for k in 0..period-1
    OLS fit  y on log_x; emit slope b

Default ``period = 30``.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty input -> ``[]``.
    * ``period < 2`` rejected.
    * ``period > n`` -> ``[]``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def logarithmic_regression(
    values: Sequence[float], period: int = 30,
) -> list[float | None]:
    """Per-bar log-fit slope coefficient ``b``."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ValueError(f"period must be an int >= 2; got {period!r}.")
    n = len(values)
    if n == 0 or period > n:
        return []
    log_x = [math.log(k + 1) for k in range(period)]
    mean_log_x = sum(log_x) / period
    sxx = sum((lx - mean_log_x) ** 2 for lx in log_x)
    if sxx == 0:
        return [None] * n  # degenerate — single-point window
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        window = values[i - period + 1 : i + 1]
        mean_y = sum(window) / period
        sxy = sum(
            (log_x[k] - mean_log_x) * (window[k] - mean_y)
            for k in range(period)
        )
        out[i] = sxy / sxx
    return out


__all__ = ["logarithmic_regression"]
