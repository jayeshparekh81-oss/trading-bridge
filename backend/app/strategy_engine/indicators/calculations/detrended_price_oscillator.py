"""Detrended Price Oscillator (DPO).

Definition::

    shift = period / 2 + 1                              # integer floor
    DPO[i] = price[i - shift] - SMA(price, period)[i]

The shift removes the lag-induced trend component — DPO is *not*
real-time; it's a historical-cycle visualisation tool. Useful for
spotting cycle highs / lows in trending markets.

Default ``period = 20``.

Output length equals input length. The shift means the first
``period - 1`` indices AND the last ``shift`` indices are ``None``
(the latter because they'd reach into the future).

Edge cases:
    * Empty input -> ``[]``.
    * ``period >= n`` -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence


def detrended_price_oscillator(
    closes: Sequence[float],
    period: int = 20,
) -> list[float | None]:
    """Detrended Price Oscillator over a rolling SMA."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 1:
        raise ValueError(f"period must be an int > 1; got {period!r}.")
    n = len(closes)
    if n == 0 or period >= n:
        return []

    shift = period // 2 + 1
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        if i - shift < 0:
            continue
        sma = sum(closes[i - period + 1 : i + 1]) / period
        out[i] = closes[i - shift] - sma
    return out


__all__ = ["detrended_price_oscillator"]
