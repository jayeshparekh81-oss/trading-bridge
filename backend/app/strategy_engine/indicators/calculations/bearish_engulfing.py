"""Bearish Engulfing candlestick pattern (two-bar).

Mirror of :mod:`bullish_engulfing`. Bar i-1 closes bullish; bar i
closes bearish; bar i body engulfs bar i-1 body:

    open[i]  >= close[i - 1]
    close[i] <= open[i - 1]

Edge cases per Phase 1 contract: same as :mod:`bullish_engulfing`.
"""

from __future__ import annotations

from collections.abc import Sequence


def bearish_engulfing(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> list[float | None]:
    """Detect bearish-engulfing bars."""
    n = _check_lengths(opens, highs, lows, closes)
    if n == 0:
        return []

    out: list[float | None] = [None] + [0.0] * (n - 1)
    for i in range(1, n):
        prior_bullish = closes[i - 1] > opens[i - 1]
        current_bearish = closes[i] < opens[i]
        if not prior_bullish or not current_bearish:
            continue
        engulfs = (
            opens[i] >= closes[i - 1] and closes[i] <= opens[i - 1]
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


__all__ = ["bearish_engulfing"]
