"""Delta proxy - directional bias from price action.

⚠️  This is a PRICE-DERIVED PROXY, NOT an actual Black-Scholes
delta. Real delta needs an options chain + strike + expiry +
IV + risk-free rate. This indicator approximates the *concept*
of directional bias (-1 = strong short bias; +1 = strong long
bias) using price action alone.

Definition (custom proxy)::

    sma[i]   = SMA(close, period)[i]
    atr[i]   = ATR(period)[i]
    raw[i]   = (close[i] - sma[i]) / (atr[i] * 2)        # ~95th-percentile distance
    delta[i] = clamp(raw[i], -1, +1)

Output range is ``[-1, +1]``. Distinct from existing momentum
indicators in that the value is BOUNDED + interpretable as a
"directional positioning" signal (the conceptual analogue to
delta, not a substitute).

Default ``period = 14``.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period >= n`` -> ``[]``.
    * ATR == 0 (flat market) -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.atr import atr
from app.strategy_engine.indicators.calculations.sma import sma


def delta_proxy_directional(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """-1..+1 directional-bias proxy."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(closes)
    if n != len(highs) or n != len(lows):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {len(highs)}, {len(lows)}, {n}."
        )
    if n == 0 or period >= n:
        return []

    sma_series = sma(list(closes), period)
    atr_series = atr(highs, lows, closes, period)
    if not sma_series or not atr_series:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(n):
        s = sma_series[i]
        a = atr_series[i]
        if s is None or a is None or a == 0:
            continue
        raw = (closes[i] - s) / (a * 2.0)
        out[i] = max(-1.0, min(1.0, raw))
    return out


__all__ = ["delta_proxy_directional"]
