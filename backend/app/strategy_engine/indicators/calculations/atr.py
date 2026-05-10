"""Average True Range — Wilder smoothing.

Definition (Wilder, 1978; matches Pine ``ta.atr``):

    True range at bar ``i``::

        TR[0] = high[0] - low[0]                           # no prior close
        TR[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )                                                  # for i >= 1

    Then::

        ATR[period - 1] = mean(TR[0..period - 1])          # simple-mean seed
        ATR[i]          = (ATR[i - 1] * (period - 1) + TR[i]) / period   # for i >= period

Output length equals input length. Positions ``0 .. period - 2`` are
``None``.

Edge cases per Phase 1 contract:
    * Empty input -> ``[]``.
    * ``period > len(highs)`` -> ``[]``.
    * Mismatched input lengths -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """ATR (Wilder) over ``period`` bars."""
    _check_period(period)
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0 or period > n:
        return []

    tr: list[float] = [0.0] * n
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        prev_close = closes[i - 1]
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - prev_close),
            abs(lows[i] - prev_close),
        )

    out: list[float | None] = [None] * (period - 1)
    seed = sum(tr[:period]) / period
    out.append(seed)
    prev = seed
    for i in range(period, n):
        current = (prev * (period - 1) + tr[i]) / period
        out.append(current)
        prev = current
    return out


def _check_period(period: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")


__all__ = ["atr"]
