"""Kurtosis (excess) of returns over a trailing window.

Fourth standardised moment minus 3 — the *excess* form. Tells
you how fat-tailed the return distribution is relative to
Gaussian (which has kurtosis = 3 -> excess = 0).

    > 0 -> fat-tailed (more extreme moves than Normal predicts)
    = 0 -> Gaussian-like
    < 0 -> thin-tailed / platykurtic

Definition::

    mu          = mean(returns)
    sigma^2     = sum((r - mu)^2) / period
    fourth_mom  = sum((r - mu)^4) / period
    kurt_excess = fourth_mom / sigma^4 - 3

Default ``period = 30``.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty input -> ``[]``.
    * ``period >= n`` -> ``[]``.
    * sigma == 0 (constant window) -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence


def kurtosis(
    closes: Sequence[float], period: int = 30,
) -> list[float | None]:
    """Excess kurtosis of trailing-window returns."""
    if not isinstance(period, int) or isinstance(period, bool) or period < 4:
        raise ValueError(f"period must be an int >= 4; got {period!r}.")
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
        fourth = sum((r - mu) ** 4 for r in window) / period
        out[i] = fourth / (var * var) - 3.0
    return out


__all__ = ["kurtosis"]
