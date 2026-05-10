"""Supertrend (Olivier Seban / popularised on TradingView).

Trend-following band tracker. Two outputs:

    * ``line`` — the active band level (lower band when the trend is
      up, upper band when the trend is down).
    * ``direction`` — ``+1.0`` when price is above the line (bullish),
      ``-1.0`` when below (bearish), ``None`` during warm-up.

Definition (matches the canonical Pine implementation):

    HL2          = (high + low) / 2
    upper_basic  = HL2 + multiplier * ATR
    lower_basic  = HL2 - multiplier * ATR

    The "final" bands ratchet:
        upper_final[i] = min(upper_basic[i], upper_final[i - 1])
                          if upper_basic[i] < upper_final[i - 1] or close[i - 1] > upper_final[i - 1]
                          else upper_final[i - 1]
        lower_final[i] = max(lower_basic[i], lower_final[i - 1])
                          if lower_basic[i] > lower_final[i - 1] or close[i - 1] < lower_final[i - 1]
                          else lower_final[i - 1]

    Trend flips when close crosses the active band; the line follows
    whichever band is active.

Edge cases per Phase 1 contract:
    * Empty input -> ``([], [])``.
    * Insufficient bars for ATR -> ``([None]*n, [None]*n)``.
    * Mismatched input lengths -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence


def supertrend(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 10,
    multiplier: float = 3.0,
) -> tuple[list[float | None], list[float | None]]:
    """Return ``(supertrend_line, direction)``."""
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
    if n == 0:
        return ([], [])

    atr = _atr(highs, lows, closes, period)
    line: list[float | None] = [None] * n
    direction: list[float | None] = [None] * n

    upper_final = [0.0] * n
    lower_final = [0.0] * n
    long_trend = True

    for i in range(n):
        a = atr[i]
        if a is None:
            continue
        hl2 = (highs[i] + lows[i]) / 2.0
        upper_basic = hl2 + multiplier * a
        lower_basic = hl2 - multiplier * a

        if i == 0 or atr[i - 1] is None:
            upper_final[i] = upper_basic
            lower_final[i] = lower_basic
            long_trend = closes[i] >= upper_basic
        else:
            upper_final[i] = (
                upper_basic
                if (
                    upper_basic < upper_final[i - 1]
                    or closes[i - 1] > upper_final[i - 1]
                )
                else upper_final[i - 1]
            )
            lower_final[i] = (
                lower_basic
                if (
                    lower_basic > lower_final[i - 1]
                    or closes[i - 1] < lower_final[i - 1]
                )
                else lower_final[i - 1]
            )

        if long_trend:
            if closes[i] < lower_final[i]:
                long_trend = False
                line[i] = upper_final[i]
                direction[i] = -1.0
            else:
                line[i] = lower_final[i]
                direction[i] = 1.0
        else:
            if closes[i] > upper_final[i]:
                long_trend = True
                line[i] = lower_final[i]
                direction[i] = 1.0
            else:
                line[i] = upper_final[i]
                direction[i] = -1.0
    return (line, direction)


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


__all__ = ["supertrend"]
