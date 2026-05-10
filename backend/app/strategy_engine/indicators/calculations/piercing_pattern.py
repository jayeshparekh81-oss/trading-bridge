"""Piercing Pattern candlestick (two-bar bullish reversal).

Bar i-1 is bearish. Bar i opens below bar i-1's low (gap down) and
closes above the midpoint of bar i-1's body, but does NOT close
above bar i-1's open (otherwise it would be a bullish engulfing).

Definition:

    bar i-1: close < open                       (bearish)
    bar i:   open < low[i - 1]                  (gap-down open)
    bar i:   close > (open[i-1] + close[i-1]) / 2   (above mid-body)
    bar i:   close < open[i - 1]                (not a full engulfing)

Edge cases per Phase 1 contract: same as :mod:`bullish_engulfing`.
"""

from __future__ import annotations

from collections.abc import Sequence


def piercing_pattern(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> list[float | None]:
    """Detect piercing-pattern bars."""
    n = _check_lengths(opens, highs, lows, closes)
    if n == 0:
        return []

    out: list[float | None] = [None] + [0.0] * (n - 1)
    for i in range(1, n):
        if closes[i - 1] >= opens[i - 1]:
            continue
        if closes[i] <= opens[i]:
            continue
        if opens[i] >= lows[i - 1]:
            continue
        midpoint = (opens[i - 1] + closes[i - 1]) / 2.0
        if closes[i] <= midpoint:
            continue
        if closes[i] >= opens[i - 1]:
            continue
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


__all__ = ["piercing_pattern"]
