"""Trend Consistency Score — fraction of trailing windows
agreeing with the current short-term trend direction.

Different from Pack 8's :mod:`mtf_ema_alignment` (which emits
ternary +1 / 0 / -1 based on strict ascending/descending EMA
order). This is a *continuous* score in ``[0, 1]``: how many of
the supplied SMA periods are sloping in the same direction as
the price's short-term trend.

Definition (with ``timeframes = (10, 20, 50)`` default)::

    short_dir = sign(close[i] - close[i - 1])         # +1 or -1
    sma_dirs  = [sign(SMA(close, p)[i] - SMA(close, p)[i - 1]) for p in timeframes]
    score[i]  = sum(sma_dir == short_dir) / len(timeframes)

Output range is ``[0, 1]``. 1.0 = every timeframe slope agrees
with the short-term direction (strong trend); 0.0 = every
timeframe disagrees (likely reversal in progress).

Output length equals input length. ``None`` for the warm-up
(slowest SMA period bars).

Edge cases:
    * Empty input -> ``[]``.
    * ``max(timeframes) >= n`` -> ``[]``.
    * Flat short-term move (close == close[i-1]) -> ``None`` for
      that bar (no direction to compare against).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.sma import sma


def trend_consistency_score(
    closes: Sequence[float],
    timeframes: tuple[int, ...] = (10, 20, 50),
) -> list[float | None]:
    """Per-bar trend-consistency score in ``[0, 1]``."""
    if len(timeframes) < 2:
        raise ValueError(
            f"timeframes must have at least 2 entries; got {timeframes!r}."
        )
    for tf in timeframes:
        if not isinstance(tf, int) or isinstance(tf, bool) or tf < 2:
            raise ValueError(
                f"every timeframe must be an int >= 2; got {timeframes!r}."
            )
    n = len(closes)
    if n == 0 or max(timeframes) >= n:
        return []

    sma_series = [sma(list(closes), tf) for tf in timeframes]
    if not all(sma_series):
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(1, n):
        delta_short = closes[i] - closes[i - 1]
        if delta_short == 0:
            continue
        short_dir = 1 if delta_short > 0 else -1
        agreements = 0
        valid = 0
        for s in sma_series:
            cur = s[i]
            prev = s[i - 1]
            if cur is None or prev is None:
                continue
            valid += 1
            sma_delta = cur - prev
            if sma_delta == 0:
                continue
            sma_dir = 1 if sma_delta > 0 else -1
            if sma_dir == short_dir:
                agreements += 1
        if valid < len(timeframes):
            continue
        out[i] = agreements / len(timeframes)
    return out


__all__ = ["trend_consistency_score"]
