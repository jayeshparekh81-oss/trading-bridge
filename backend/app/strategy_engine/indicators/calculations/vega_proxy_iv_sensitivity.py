"""Vega proxy - sensitivity of price to volatility-regime change.

⚠️  PROXY, not Black-Scholes vega. Real vega is the rate at
which an option's price changes per 1 % change in IV. This
indicator approximates the *concept*: how much price moves per
unit change in the short/long ATR ratio.

Definition (custom proxy)::

    vol_ratio[i]   = volatility_ratio(short, long)[i]    # short/long ATR
    delta_price[i] = (close[i] - close[i - lag]) / close[i - lag] * 100
    delta_vol[i]   = vol_ratio[i] - vol_ratio[i - lag]
    vega[i]        = delta_price[i] / delta_vol[i]    (None if delta_vol == 0)

Where ``lag = max(short, long) // 2`` so the price change
captures the same window as the vol regime shift.

Defaults ``short = 5``, ``long = 20``.

Output length equals input length. ``None`` for the warm-up
plus any bar where vol regime didn't change (delta_vol == 0).

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``short >= long`` -> ``ValueError``.
    * Insufficient bars -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.volatility_ratio import (
    volatility_ratio,
)


def vega_proxy_iv_sensitivity(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    short: int = 5,
    long: int = 20,
) -> list[float | None]:
    """Per-bar vega proxy (price sensitivity to vol-regime change)."""
    if not isinstance(short, int) or isinstance(short, bool) or short <= 0:
        raise ValueError(f"short must be a positive int; got {short!r}.")
    if not isinstance(long, int) or isinstance(long, bool) or long <= 0:
        raise ValueError(f"long must be a positive int; got {long!r}.")
    if short >= long:
        raise ValueError(
            f"short must be strictly less than long; got short={short}, long={long}."
        )
    n = len(closes)
    if n != len(highs) or n != len(lows):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {len(highs)}, {len(lows)}, {n}."
        )
    if n == 0 or long >= n:
        return []

    vr = volatility_ratio(highs, lows, closes, short, long)
    if not vr:
        return [None] * n

    lag = max(short, long) // 2
    if lag < 1 or lag >= n:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(lag, n):
        cur_vr = vr[i]
        prev_vr = vr[i - lag]
        if cur_vr is None or prev_vr is None:
            continue
        delta_vol = cur_vr - prev_vr
        if delta_vol == 0:
            continue
        prev_price = closes[i - lag]
        if prev_price == 0:
            continue
        delta_price = (closes[i] - prev_price) / prev_price * 100.0
        out[i] = delta_price / delta_vol
    return out


__all__ = ["vega_proxy_iv_sensitivity"]
