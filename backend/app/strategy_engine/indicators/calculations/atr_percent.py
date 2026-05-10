"""ATR as a percentage of price — normalised volatility.

Definition::

    ATR_pct[i] = ATR(high, low, close, period)[i] / close[i] * 100

Comparable across symbols and price levels (raw ATR isn't —
ATR(NIFTY) is in points; ATR(RELIANCE) is in rupees). Useful as
a position-sizing input or a regime filter.

Default ``period = 14``.

Output length equals input length. ``None`` for the ATR warm-up.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period >= n`` -> ``[]``.
    * ``close[i] == 0`` -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.atr import atr


def atr_percent(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """ATR expressed as % of close."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0 or period >= n:
        return []

    atr_series = atr(highs, lows, closes, period)
    if not atr_series:
        return [None] * n
    out: list[float | None] = [None] * n
    for i in range(n):
        a = atr_series[i]
        if a is None or closes[i] == 0:
            continue
        out[i] = a / closes[i] * 100.0
    return out


__all__ = ["atr_percent"]
