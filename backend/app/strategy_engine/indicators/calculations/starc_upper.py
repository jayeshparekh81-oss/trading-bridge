"""STARC (Stoller Average Range Channel) — upper band (Manning Stoller).

Definition::

    base[i]  = SMA(close, period)[i]
    atr[i]   = ATR(high, low, close, atr_period)[i]
    upper[i] = base[i] + atr_mult * atr[i]

Default ``period = 5`` (Stoller's short-period SMA),
``atr_period = 15``, ``atr_mult = 1.5``.

Output length equals input length. ``None`` until both base + ATR
are warm.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * Insufficient bars -> ``[]``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.atr import atr
from app.strategy_engine.indicators.calculations.sma import sma


def starc_upper(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 5,
    atr_period: int = 15,
    atr_mult: float = 1.5,
) -> list[float | None]:
    """STARC upper band."""
    return _starc(highs, lows, closes, period, atr_period, atr_mult, side=+1)


def _starc(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int,
    atr_period: int,
    atr_mult: float,
    *,
    side: int,
) -> list[float | None]:
    """Shared computation. ``side = +1`` for the upper line,
    ``-1`` for the lower (used by :mod:`starc_lower`)."""
    _validate(period, atr_period, atr_mult)
    n = len(highs)
    if n != len(lows) or n != len(closes):
        raise ValueError(
            "highs, lows, closes must have the same length; "
            f"got {n}, {len(lows)}, {len(closes)}."
        )
    if n == 0:
        return []
    base = sma(list(closes), period)
    band = atr(highs, lows, closes, atr_period)
    if not base or not band:
        return [None] * n
    out: list[float | None] = [None] * n
    for i in range(n):
        b = base[i]
        a = band[i]
        if b is None or a is None:
            continue
        out[i] = b + side * atr_mult * a
    return out


def _validate(period: int, atr_period: int, atr_mult: float) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive int; got {period!r}.")
    if not isinstance(atr_period, int) or isinstance(atr_period, bool) or atr_period <= 0:
        raise ValueError(f"atr_period must be a positive int; got {atr_period!r}.")
    if not isinstance(atr_mult, (int, float)) or isinstance(atr_mult, bool):
        raise ValueError(f"atr_mult must be a number; got {atr_mult!r}.")
    if atr_mult <= 0:
        raise ValueError(f"atr_mult must be > 0; got {atr_mult}.")


__all__ = ["starc_upper"]
