"""Trend-Momentum Combo - momentum signed by trend alignment.

Combines a long-EMA trend filter with a short ATR-normalised
momentum reading::

    trend_dir   = +1 if close > ema(close, trend_period) else -1
    momentum    = (close - close[momentum_period]) / atr(momentum_period)
    output      = trend_dir * momentum

Positive output = momentum is *aligned* with the trend (continuation
context). Negative = momentum is *against* the trend (counter-
trend context). Magnitude is in ATR units (unbounded but typically
``[-3, +3]``).

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Either period non-positive int -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.atr import atr
from app.strategy_engine.indicators.calculations.ema import ema


def trend_momentum_combo(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    trend_period: int = 50,
    momentum_period: int = 14,
) -> list[float | None]:
    """Trend-signed ATR-normalised momentum."""
    if not isinstance(trend_period, int) or isinstance(trend_period, bool) or trend_period < 2:
        raise ValueError(f"trend_period must be int >= 2; got {trend_period!r}.")
    if not isinstance(momentum_period, int) or isinstance(momentum_period, bool) or momentum_period < 1:
        raise ValueError(
            f"momentum_period must be a positive int; got {momentum_period!r}."
        )
    n = len(closes)
    if n != len(highs) or n != len(lows):
        raise ValueError(
            f"highs/lows/closes must match in length; "
            f"got {len(highs)}, {len(lows)}, {n}."
        )
    if n == 0:
        return []

    ema_line = ema(closes, trend_period)
    atr_line = atr(highs, lows, closes, momentum_period)
    if not ema_line or not atr_line:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(momentum_period, n):
        e = ema_line[i]
        t = atr_line[i]
        if e is None or t is None or t == 0:
            continue
        trend_dir = 1 if closes[i] >= e else -1
        momentum = (closes[i] - closes[i - momentum_period]) / t
        out[i] = trend_dir * momentum
    return out


__all__ = ["trend_momentum_combo"]
