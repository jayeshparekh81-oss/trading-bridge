"""Historical Volatility — annualised stddev of log returns.

Definition (matches the textbook formula and most charting
platforms):

    log_return[i] = log(close[i] / close[i - 1])     for i >= 1
    HV[i]         = stdev(log_returns[i - period + 1..i])
                    * sqrt(annualization)
                    * 100   (% expression)

The series of log returns is one shorter than ``closes`` (no return
defined for bar 0). The first ``period`` log returns are needed
before the first HV value can be emitted, so HV is defined from
index ``period`` onward.

Default ``annualization=252`` matches the trading-day count for
daily Indian / US equity data; intraday users override it.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period >= len(closes)`` -> ``[]``.
    * Any ``close <= 0`` (would invalidate ``log``) -> ``None`` at
      that bar and any subsequent bar still in the affected window.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def historical_volatility(
    closes: Sequence[float],
    period: int = 20,
    annualization: int = 252,
) -> list[float | None]:
    """Annualised historical volatility, expressed as a percent."""
    _check_period(period)
    if not isinstance(annualization, int) or annualization < 1:
        raise ValueError(
            f"annualization must be a positive int; got {annualization!r}."
        )
    n = len(closes)
    if n == 0 or period >= n:
        return []

    log_returns: list[float | None] = [None] * n
    for i in range(1, n):
        prev = closes[i - 1]
        curr = closes[i]
        if prev <= 0 or curr <= 0:
            continue
        log_returns[i] = math.log(curr / prev)

    out: list[float | None] = [None] * n
    sqrt_a = math.sqrt(annualization)
    for i in range(period, n):
        window = log_returns[i - period + 1 : i + 1]
        if any(v is None for v in window):
            continue
        # Refine type: window has only floats now.
        floats = [v for v in window if v is not None]
        mean = sum(floats) / period
        var = sum((v - mean) ** 2 for v in floats) / period
        out[i] = math.sqrt(var) * sqrt_a * 100.0
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["historical_volatility"]
