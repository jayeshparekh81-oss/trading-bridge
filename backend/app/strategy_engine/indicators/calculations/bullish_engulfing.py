"""Bullish Engulfing candlestick pattern (two-bar).

Bar i-1 closes bearish (close < open). Bar i closes bullish
(close > open) and its body fully covers bar i-1's body:

    open[i]  <= close[i - 1]   (current opens at or below prior close)
    close[i] >= open[i - 1]    (current closes at or above prior open)

The 2-bar lookback means index 0 is always ``None`` (no prior bar to
compare against); from index 1 onwards each bar is 1.0 / 0.0.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * Mismatched lengths -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence


def bullish_engulfing(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> list[float | None]:
    """Detect bullish-engulfing bars."""
    n = _check_lengths(opens, highs, lows, closes)
    if n == 0:
        return []

    out: list[float | None] = [None] + [0.0] * (n - 1)
    for i in range(1, n):
        prior_bearish = closes[i - 1] < opens[i - 1]
        current_bullish = closes[i] > opens[i]
        if not prior_bearish or not current_bullish:
            continue
        engulfs = (
            opens[i] <= closes[i - 1] and closes[i] >= opens[i - 1]
        )
        if engulfs:
            out[i] = 1.0
    return out


def _check_lengths(*series: Sequence[float]) -> int:
    n = len(series[0])
    for s in series[1:]:
        if len(s) != n:
            raise ValueError(
                f"OHLC series must have the same length; got "
                f"{[len(x) for x in series]}."
            )
    return n


__all__ = ["bullish_engulfing"]
