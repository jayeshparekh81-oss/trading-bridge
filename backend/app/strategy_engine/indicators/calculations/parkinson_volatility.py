"""Parkinson Volatility Estimator (Michael Parkinson, 1980).

Substitute for the spec's ``realized_volatility``, which would
have computed the same numbers as the existing
``historical_volatility`` indicator (annualised stddev of log
returns). Parkinson's estimator uses the bar's high-low *range*
instead of close-to-close moves — about 5x more efficient when
intraday range information is available.

Definition::

    log_range[i] = log(high[i] / low[i])
    var          = sum(log_range^2) / (4 * ln(2) * period)
    Parkinson    = sqrt(var * bars_per_year) * 100

Default ``period = 20``, ``bars_per_year = 252`` (matches
``historical_volatility``).

Output length equals input length. Indices ``0 .. period - 1``
are ``None``.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period > n`` -> ``[]``.
    * ``low[i] <= 0`` (would invalidate log) -> ``None`` for any
      window touching that bar.
    * ``high == low`` (flat bar) contributes 0 to the sum.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

#: Parkinson's normalisation constant: 4 * ln(2). Pre-computed
#: so the inner loop doesn't reach for math.log every bar.
_FOUR_LN2 = 4.0 * math.log(2.0)


def parkinson_volatility(
    highs: Sequence[float],
    lows: Sequence[float],
    period: int = 20,
    bars_per_year: int = 252,
) -> list[float | None]:
    """Annualised Parkinson volatility (% form)."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    if not isinstance(bars_per_year, int) or isinstance(bars_per_year, bool) or bars_per_year <= 0:
        raise ValueError(
            f"bars_per_year must be a positive int; got {bars_per_year!r}."
        )
    n = len(highs)
    if n != len(lows):
        raise ValueError(
            f"highs and lows must have the same length; got {n}, {len(lows)}."
        )
    if n == 0 or period > n:
        return []

    log_range_sq: list[float | None] = [None] * n
    for i in range(n):
        if lows[i] <= 0 or highs[i] <= 0:
            continue
        ratio = highs[i] / lows[i]
        log_r = math.log(ratio)
        log_range_sq[i] = log_r * log_r

    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        window = log_range_sq[i - period + 1 : i + 1]
        if any(v is None for v in window):
            continue
        # All entries non-None inside this branch — narrow to
        # float for the sum.
        floats = [v for v in window if v is not None]
        var = sum(floats) / (_FOUR_LN2 * period)
        out[i] = math.sqrt(var * bars_per_year) * 100.0
    return out


__all__ = ["parkinson_volatility"]
