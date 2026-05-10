"""Chandelier Exit — short-side trailing stop. See
:mod:`chandelier_exit_long` for the long-side companion + the
shared computation."""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.chandelier_exit_long import (
    _chandelier,
)


def chandelier_exit_short(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 22,
    atr_mult: float = 3.0,
) -> list[float | None]:
    """Short-side Chandelier Exit: ``min(low, period) + mult * ATR``."""
    return _chandelier(highs, lows, closes, period, atr_mult, side=-1)


__all__ = ["chandelier_exit_short"]
