"""Commodity Channel Index (Donald Lambert, 1980).

Definition (matches Pine ``ta.cci``):

    TP[i]           = (high[i] + low[i] + close[i]) / 3
    SMA_TP[i]       = mean(TP[i - period + 1..i])
    MeanDev[i]      = mean(abs(TP[j] - SMA_TP[i]) for j in window)
    CCI[i]          = (TP[i] - SMA_TP[i]) / (0.015 * MeanDev[i])

CCI is a momentum oscillator that compares the current typical
price to its moving average; readings outside ±100 are commonly
treated as overbought / oversold.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period > len(values)`` -> ``[]``.
    * Mismatched lengths -> ``ValueError``.
    * Window with zero mean deviation (constant price) -> ``None``
      for that bar (division by zero).
"""

from __future__ import annotations

from collections.abc import Sequence


def cci(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 20,
) -> list[float | None]:
    """Commodity Channel Index over ``period`` bars."""
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0 or period > n:
        return []

    tp = [(highs[i] + lows[i] + closes[i]) / 3.0 for i in range(n)]
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        window = tp[i - period + 1 : i + 1]
        sma = sum(window) / period
        mean_dev = sum(abs(x - sma) for x in window) / period
        if mean_dev == 0.0:
            out[i] = None
            continue
        out[i] = (tp[i] - sma) / (0.015 * mean_dev)
    return out


__all__ = ["cci"]
