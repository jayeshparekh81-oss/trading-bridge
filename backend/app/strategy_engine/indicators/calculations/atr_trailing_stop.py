"""Generic ATR trailing stop — long-side, ratcheted.

Distinct from the Pack-12 ``chandelier_exit_long`` (which trails
from the recent *peak high*) and from ``supertrend`` (which
flips direction). This generic stop trails from the *current
close* and only ever moves in the favourable direction:

    raw_stop[i] = close[i] - atr_mult * ATR(atr_period)[i]
    stop[i]     = max(raw_stop[i], stop[i - 1])             # ratchet up

The result is a stop line that climbs as price climbs but never
loosens — close < stop[i] is the exit signal.

Defaults ``atr_period = 14``, ``atr_mult = 2.0``.

Output length equals input length. ``None`` for the warm-up
(first ``atr_period`` bars).

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``atr_period >= n`` -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.atr import atr


def atr_trailing_stop(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    atr_period: int = 14,
    atr_mult: float = 2.0,
) -> list[float | None]:
    """Long-side ratcheting ATR trailing stop."""
    if not isinstance(atr_period, int) or isinstance(atr_period, bool) or atr_period <= 0:
        raise ValueError(f"atr_period must be a positive int; got {atr_period!r}.")
    if not isinstance(atr_mult, (int, float)) or isinstance(atr_mult, bool):
        raise ValueError(f"atr_mult must be a number; got {atr_mult!r}.")
    if atr_mult <= 0:
        raise ValueError(f"atr_mult must be > 0; got {atr_mult}.")
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0 or atr_period >= n:
        return []

    atr_series = atr(highs, lows, closes, atr_period)
    if not atr_series:
        return [None] * n

    out: list[float | None] = [None] * n
    running_stop: float | None = None
    for i in range(n):
        a = atr_series[i]
        if a is None:
            continue
        raw = closes[i] - atr_mult * a
        running_stop = raw if running_stop is None else max(running_stop, raw)
        out[i] = running_stop
    return out


__all__ = ["atr_trailing_stop"]
