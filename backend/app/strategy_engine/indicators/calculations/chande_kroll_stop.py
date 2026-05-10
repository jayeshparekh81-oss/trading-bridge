"""Chande Kroll Stop (Tushar Chande & Stanley Kroll, 1995).

Volatility-aware trailing-stop curve. We expose the *long-side*
stop line as the primary output; short-side and switching are an
operator concern.

Definition (long-side stop)::

    raw_high[i] = max(high over atr_period) - atr_mult * ATR(atr_period)[i]
    stop[i]     = max(raw_high over period)

Defaults: ``atr_period = 10``, ``atr_mult = 1.0``, ``period = 9``.

Output length equals input length. ``None`` for the warm-up
(``atr_period + period`` bars).

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Insufficient bars -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.atr import atr


def chande_kroll_stop(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    atr_period: int = 10,
    atr_mult: float = 1.0,
    period: int = 9,
) -> list[float | None]:
    """Long-side Chande Kroll Stop curve."""
    _check_period(atr_period, "atr_period")
    _check_period(period, "period")
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
    minimum = atr_period + period
    if n == 0 or n < minimum:
        return []

    atr_series = atr(highs, lows, closes, atr_period)
    if not atr_series:
        return [None] * n

    raw_high: list[float | None] = [None] * n
    for i in range(atr_period - 1, n):
        a = atr_series[i]
        if a is None:
            continue
        window_high = max(highs[i - atr_period + 1 : i + 1])
        raw_high[i] = window_high - atr_mult * a

    out: list[float | None] = [None] * n
    for i in range(atr_period + period - 2, n):
        window = [v for v in raw_high[i - period + 1 : i + 1] if v is not None]
        if len(window) < period:
            continue
        out[i] = max(window)
    return out


def _check_period(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive int; got {value!r}.")


__all__ = ["chande_kroll_stop"]
