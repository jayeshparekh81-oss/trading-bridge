"""Keltner Channel — Chester Keltner / popularised by Linda Raschke.

Three outputs (matches Pine ``ta.kc``):

    * ``upper``  — middle EMA + ``multiplier`` * ATR.
    * ``middle`` — EMA of close over ``period`` bars.
    * ``lower``  — middle EMA - ``multiplier`` * ATR.

Volatility-aware envelope around an EMA. Wider than a Bollinger
band when ATR is high, narrower when calm.

Edge cases per Phase 1 contract:
    * Empty input -> ``([], [], [])``.
    * Insufficient bars for either EMA or ATR -> warm-up positions
      are ``None``.
    * Mismatched lengths -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence


def keltner_channel(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 20,
    multiplier: float = 2.0,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Return ``(upper, middle, lower)`` Keltner channel."""
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    if multiplier <= 0:
        raise ValueError(f"multiplier must be > 0; got {multiplier!r}.")
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0 or period > n:
        return ([], [], [])

    middle = _ema(closes, period)
    atr = _atr(highs, lows, closes, period)
    upper: list[float | None] = [None] * n
    lower: list[float | None] = [None] * n
    for i in range(n):
        m = middle[i]
        a = atr[i]
        if m is None or a is None:
            continue
        upper[i] = m + multiplier * a
        lower[i] = m - multiplier * a
    return (upper, middle, lower)


def _ema(values: Sequence[float], period: int) -> list[float | None]:
    n = len(values)
    if n == 0 or period > n:
        return [None] * n
    out: list[float | None] = [None] * n
    seed = sum(values[i] for i in range(period)) / period
    out[period - 1] = seed
    alpha = 2.0 / (period + 1)
    prev = seed
    for i in range(period, n):
        prev = alpha * values[i] + (1.0 - alpha) * prev
        out[i] = prev
    return out


def _atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int,
) -> list[float | None]:
    n = len(highs)
    if n == 0 or period > n:
        return [None] * n
    tr: list[float] = [highs[0] - lows[0]]
    for i in range(1, n):
        tr.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )
    out: list[float | None] = [None] * n
    seed = sum(tr[i] for i in range(period)) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, n):
        prev = (prev * (period - 1) + tr[i]) / period
        out[i] = prev
    return out


__all__ = ["keltner_channel"]
