"""Breadth Thrust — Marty Zweig's classic, single-symbol proxy.

Substitute for the spec's ``bull_bear_power`` (which would have
overloaded Elder's "Bull Power" / "Bear Power" naming from
Pack 6's ``elder_ray_bull`` / ``elder_ray_bear``).

Zweig's original Breadth Thrust is market-wide: 10-day EMA of
(advancing issues / total issues). A reading rising from below
0.40 to above 0.615 within ~10 days flags a major buy signal.

Single-symbol proxy substitutes "advancing issues" with
"bullish bars" (close >= open) and "total issues" with bar count:

    bullish_share[i] = sum(close[k] >= open[k] for k in window) / period
    BT[i]            = EMA(bullish_share, ema_period)[i]

Output range is ``[0, 1]``. Default ``period = 10``,
``ema_period = 10``.

Output length equals input length. ``None`` for the warm-up
(``period + ema_period - 1`` bars).

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Insufficient bars -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.ema import ema


def breadth_thrust(
    opens: Sequence[float],
    closes: Sequence[float],
    period: int = 10,
    ema_period: int = 10,
) -> list[float | None]:
    """Single-symbol breadth-thrust proxy."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    if not isinstance(ema_period, int) or isinstance(ema_period, bool) or ema_period <= 0:
        raise ValueError(
            f"ema_period must be a positive int; got {ema_period!r}."
        )
    n = len(opens)
    if n != len(closes):
        raise ValueError(
            f"opens and closes must have the same length; got {n}, {len(closes)}."
        )
    if n == 0 or period + ema_period > n:
        return []

    bull_share: list[float] = [0.0] * n
    for i in range(period - 1, n):
        bullish_count = sum(
            1 for k in range(i - period + 1, i + 1)
            if closes[k] >= opens[k]
        )
        bull_share[i] = bullish_count / period

    smoothed = ema(bull_share, ema_period)
    if not smoothed:
        return [None] * n
    out: list[float | None] = list(smoothed)
    # Mask the bullish-share warm-up bars (the bull_share values
    # there are zero placeholders, not real measurements).
    for i in range(min(period - 1, n)):
        out[i] = None
    return out


__all__ = ["breadth_thrust"]
