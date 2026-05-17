"""Pivot Swing — signed swing-pivot indicator combining swing_high + swing_low.

Detects classic Dow-style swing pivots and emits a single signed series
per bar so strategy DSLs can treat "we're at a swing pivot" as one
condition. Wraps the existing :func:`swing_high` + :func:`swing_low`
implementations.

Output contract:
    * ``+price`` at the confirmation bar of a swing high (positive
      number = the pivot's high level)
    * ``-price`` at the confirmation bar of a swing low (negative
      number; magnitude = the pivot's low level)
    * ``None`` everywhere else (including bars that are pivots but
      not yet confirmed)
    * If a bar is both a confirmed swing high AND a confirmed swing
      low at the same index (rare; can happen with degenerate input
      like a long flat-line followed by a single spike), the
      higher-magnitude one wins.

This signed output lets a condition_evaluator query "pivot_swing > 0"
for swing highs, "pivot_swing < 0" for swing lows, "pivot_swing is
not None" for any pivot.

Reference: maps to Pine Script's classic Pivot Reversal strategy port
where the trader takes the opposite-side trade on a confirmed pivot.

Edge cases:
    * Empty input -> ``[]``
    * Length mismatch between highs and lows -> ``ValueError``
    * Insufficient bars (``left + right + 1 > n``) -> ``[None] * n``
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.swing_high import swing_high
from app.strategy_engine.indicators.calculations.swing_low import swing_low


def pivot_swing(
    highs: Sequence[float],
    lows: Sequence[float],
    left_bars: int = 5,
    right_bars: int = 5,
) -> list[float | None]:
    """Signed swing-pivot series. ``+x`` = swing high at level ``x``,
    ``-x`` = swing low at level ``x``, ``None`` otherwise.
    """
    n = len(highs)
    if len(lows) != n:
        raise ValueError(
            f"highs/lows length mismatch: highs={n}, lows={len(lows)}."
        )
    if n == 0:
        return []

    high_series = swing_high(highs, left_bars=left_bars, right_bars=right_bars)
    low_series = swing_low(lows, left_bars=left_bars, right_bars=right_bars)

    out: list[float | None] = [None] * n
    for i in range(n):
        h = high_series[i] if i < len(high_series) else None
        l = low_series[i] if i < len(low_series) else None
        if h is not None and l is not None:
            # Rare both-confirmed case — pick the larger magnitude.
            if abs(h) >= abs(l):
                out[i] = float(h)
            else:
                out[i] = -float(l)
        elif h is not None:
            out[i] = float(h)
        elif l is not None:
            out[i] = -float(l)
    return out


__all__ = ["pivot_swing"]
