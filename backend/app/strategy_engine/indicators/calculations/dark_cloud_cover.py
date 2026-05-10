"""Dark Cloud Cover candlestick (two-bar bearish reversal).

Mirror of :mod:`piercing_pattern`. Bar i-1 is bullish; bar i opens
above bar i-1's high (gap up), then closes below the midpoint of
bar i-1's body but not all the way through (otherwise it would be a
bearish engulfing).

Definition:

    bar i-1: close > open                          (bullish)
    bar i:   close < open                          (bearish)
    bar i:   open > high[i - 1]                    (gap-up open)
    bar i:   close < (open[i-1] + close[i-1]) / 2  (below mid-body)
    bar i:   close > open[i - 1]                   (not a full engulfing)

Edge cases per Phase 1 contract: same as :mod:`bullish_engulfing`.
"""

from __future__ import annotations

from collections.abc import Sequence


def dark_cloud_cover(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> list[float | None]:
    """Detect dark-cloud-cover bars."""
    n = _check_lengths(opens, highs, lows, closes)
    if n == 0:
        return []

    out: list[float | None] = [None] + [0.0] * (n - 1)
    for i in range(1, n):
        if closes[i - 1] <= opens[i - 1]:
            continue
        if closes[i] >= opens[i]:
            continue
        if opens[i] <= highs[i - 1]:
            continue
        midpoint = (opens[i - 1] + closes[i - 1]) / 2.0
        if closes[i] >= midpoint:
            continue
        if closes[i] <= opens[i - 1]:
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


__all__ = ["dark_cloud_cover"]
