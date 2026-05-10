"""Annualised rolling Sharpe Ratio.

Definition (textbook):

    returns[i] = close[i] / close[i - 1] - 1               for i >= 1

    Over a trailing ``period``-bar window of returns:
        mean_r = mean(returns)
        std_r  = stdev(returns)                # population (n)

        annual_excess = (mean_r - risk_free_rate / annualization)
                        * annualization
        annual_std    = std_r * sqrt(annualization)

        Sharpe = annual_excess / annual_std

The default ``annualization=252`` matches the trading-day count
for daily Indian / US equity data; intraday users override.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period >= len(closes)`` -> ``[]``.
    * Window with zero stdev (constant returns) -> ``None`` (Sharpe
      is undefined when volatility is zero).
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def sharpe_ratio(
    closes: Sequence[float],
    period: int = 252,
    annualization: int = 252,
    risk_free_rate: float = 0.0,
) -> list[float | None]:
    """Annualised Sharpe Ratio over a trailing window."""
    _check_period(period)
    if not isinstance(annualization, int) or annualization < 1:
        raise ValueError(
            f"annualization must be a positive int; got {annualization!r}."
        )
    n = len(closes)
    if n == 0 or period >= n:
        return []

    returns: list[float | None] = [None] * n
    for i in range(1, n):
        prev = closes[i - 1]
        if prev == 0:
            continue
        returns[i] = closes[i] / prev - 1.0

    rfr_per_bar = risk_free_rate / annualization
    sqrt_a = math.sqrt(annualization)
    out: list[float | None] = [None] * n
    for i in range(period, n):
        window = returns[i - period + 1 : i + 1]
        if any(v is None for v in window):
            continue
        floats = [v for v in window if v is not None]
        mean_r = sum(floats) / period
        var = sum((v - mean_r) ** 2 for v in floats) / period
        std_r = math.sqrt(var)
        if std_r == 0.0:
            continue
        out[i] = (mean_r - rfr_per_bar) * annualization / (std_r * sqrt_a)
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["sharpe_ratio"]
