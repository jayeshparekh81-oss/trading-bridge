"""IV proxy from ATR — annualised ATR-percent volatility.

⚠️  This is a PROXY, not actual implied volatility. Real IV
needs an options chain + Black-Scholes inversion + risk-free
rate. This indicator approximates the *units* IV is quoted in
(annualised %) by scaling ATR-percent by sqrt(bars_per_year).

Distinct from the existing volatility estimators:

    * historical_volatility (Pack 4) — annualised stddev of LOG
      RETURNS (close-to-close).
    * parkinson_volatility (Pack 12)  — annualised stddev from
      bar HIGH-LOW range.
    * atr_percent (Pack 12)           — un-annualised ATR / close.

This indicator is the third member of the family — annualised
ATR-percent. Useful as an apples-to-apples comparison against
quoted IV when no options chain is available.

Definition::

    atr_pct[i] = ATR(period)[i] / close[i] * 100
    iv_proxy[i] = atr_pct[i] * sqrt(bars_per_year)

Defaults ``atr_period = 20``, ``bars_per_year = 252``.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``atr_period >= n`` -> ``[]``.
    * ``close[i] == 0`` -> ``None`` for that bar.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.atr_percent import atr_percent


def iv_proxy_atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    atr_period: int = 20,
    bars_per_year: int = 252,
) -> list[float | None]:
    """ATR-based IV proxy in annualised % units."""
    if not isinstance(atr_period, int) or isinstance(atr_period, bool) or atr_period <= 0:
        raise ValueError(f"atr_period must be a positive int; got {atr_period!r}.")
    if not isinstance(bars_per_year, int) or isinstance(bars_per_year, bool) or bars_per_year <= 0:
        raise ValueError(
            f"bars_per_year must be a positive int; got {bars_per_year!r}."
        )
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0 or atr_period >= n:
        return []

    base = atr_percent(highs, lows, closes, atr_period)
    if not base:
        return [None] * n
    factor = math.sqrt(bars_per_year)
    return [None if v is None else v * factor for v in base]


__all__ = ["iv_proxy_atr"]
