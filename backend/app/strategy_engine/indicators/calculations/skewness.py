"""Skewness of returns over a trailing window.

Third standardised moment. Tells you whether the return
distribution leans left (negative skew, "left-tail risk") or
right (positive skew, "lottery-like upside").

Definition::

    return[i] = (close[i] - close[i - 1]) / close[i - 1]
    mu        = mean(returns over period)
    sigma^2   = sum((r - mu)^2) / period               (population var)
    skew      = sum((r - mu)^3) / (period * sigma^3)

Default ``period = 30``.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty input -> ``[]``.
    * ``period >= n`` -> ``[]`` (need ``period`` returns).
    * sigma == 0 (constant window) -> ``None`` for that bar.
    * close[i - 1] == 0 -> contribution is 0 that bar.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def skewness(
    closes: Sequence[float], period: int = 30,
) -> list[float | None]:
    """Population skewness of trailing-window returns."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 3:
        raise ValueError(f"period must be an int >= 3; got {period!r}.")
    n = len(closes)
    if n == 0 or period >= n:
        return []

    returns: list[float] = [0.0] * n
    for i in range(1, n):
        prev = closes[i - 1]
        if prev != 0:
            returns[i] = (closes[i] - prev) / prev

    out: list[float | None] = [None] * n
    for i in range(period, n):
        window = returns[i - period + 1 : i + 1]
        mu = sum(window) / period
        var = sum((r - mu) ** 2 for r in window) / period
        if var == 0:
            continue
        sigma = math.sqrt(var)
        third = sum((r - mu) ** 3 for r in window) / period
        out[i] = third / (sigma ** 3)
    return out


__all__ = ["skewness"]
