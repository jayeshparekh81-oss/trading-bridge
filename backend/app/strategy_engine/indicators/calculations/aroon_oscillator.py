"""Aroon Oscillator — Aroon Up minus Aroon Down.

Output range is ``[-100, +100]``. Sustained positive readings
indicate a strong uptrend; sustained negative readings indicate a
strong downtrend; oscillation around zero indicates a range-bound
regime."""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.aroon import aroon


def aroon_oscillator(
    highs: Sequence[float],
    lows: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Aroon Oscillator (up - down) over ``period`` bars."""
    _up, _down, osc = aroon(highs, lows, period)
    return osc


__all__ = ["aroon_oscillator"]
