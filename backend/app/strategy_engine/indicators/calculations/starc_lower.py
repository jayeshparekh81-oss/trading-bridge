"""STARC lower band — companion to :mod:`starc_upper`."""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.starc_upper import _starc


def starc_lower(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 5,
    atr_period: int = 15,
    atr_mult: float = 1.5,
) -> list[float | None]:
    """STARC lower band."""
    return _starc(highs, lows, closes, period, atr_period, atr_mult, side=-1)


__all__ = ["starc_lower"]
