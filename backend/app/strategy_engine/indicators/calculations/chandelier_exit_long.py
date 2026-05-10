"""Chandelier Exit — long-side trailing stop (Charles Le Beau).

Definition::

    long_stop[i] = max(high over period) - atr_mult * ATR(period)[i]

The stop trails *down* from the recent peak by an ATR-multiple
margin — gives the trade room to breathe while protecting the
profits earned at the peak. Distinct from
:mod:`atr_trailing_stop` (which trails from the current close)
and from ``supertrend`` (which switches direction).

Defaults ``period = 22``, ``atr_mult = 3.0``.

Output length equals input length. ``None`` for the warm-up.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``period > n`` -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.atr import atr


def chandelier_exit_long(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 22,
    atr_mult: float = 3.0,
) -> list[float | None]:
    """Long-side Chandelier Exit line."""
    return _chandelier(highs, lows, closes, period, atr_mult, side=+1)


def _chandelier(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int,
    atr_mult: float,
    *,
    side: int,
) -> list[float | None]:
    """Shared computation for long (+1) and short (-1) Chandeliers.

    Long side trails ``max(high) - mult * ATR``; short side
    mirrors with ``min(low) + mult * ATR``. The short variant
    lives in :mod:`chandelier_exit_short`."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    if not isinstance(atr_mult, (int, float)) or isinstance(atr_mult, bool):
        raise ValueError(f"atr_mult must be a number; got {atr_mult!r}.")
    if atr_mult <= 0:
        raise ValueError(f"atr_mult must be > 0; got {atr_mult}.")
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            f"highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0 or period > n:
        return []

    atr_series = atr(highs, lows, closes, period)
    if not atr_series:
        return [None] * n

    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        a = atr_series[i]
        if a is None:
            continue
        if side > 0:
            extreme = max(highs[i - period + 1 : i + 1])
            out[i] = extreme - atr_mult * a
        else:
            extreme = min(lows[i - period + 1 : i + 1])
            out[i] = extreme + atr_mult * a
    return out


__all__ = ["chandelier_exit_long"]
