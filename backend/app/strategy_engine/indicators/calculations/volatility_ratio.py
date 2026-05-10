"""Volatility Ratio — short-term vs long-term ATR.

Definition::

    VR[i] = ATR(short)[i] / ATR(long)[i]

Output > 1 → short-term volatility is elevated relative to the
longer baseline (regime change brewing). Output < 1 → calm
relative to baseline.

Defaults ``short = 5``, ``long = 20``.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``short >= long`` -> ``ValueError``.
    * ``long >= n`` -> ``[]``.
    * Long-window ATR == 0 (degenerate) -> ``None`` for that bar.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.atr import atr


def volatility_ratio(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    short: int = 5,
    long: int = 20,
) -> list[float | None]:
    """Short / long ATR ratio."""
    if not isinstance(short, int) or isinstance(short, bool) or short <= 0:
        raise ValueError(f"short must be a positive int; got {short!r}.")
    if not isinstance(long, int) or isinstance(long, bool) or long <= 0:
        raise ValueError(f"long must be a positive int; got {long!r}.")
    if short >= long:
        raise ValueError(
            f"short must be strictly less than long; got short={short}, long={long}."
        )
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0 or long >= n:
        return []

    short_atr = atr(highs, lows, closes, short)
    long_atr = atr(highs, lows, closes, long)
    if not short_atr or not long_atr:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(n):
        s = short_atr[i]
        long_v = long_atr[i]
        if s is None or long_v is None or long_v == 0:
            continue
        out[i] = s / long_v
    return out


__all__ = ["volatility_ratio"]
