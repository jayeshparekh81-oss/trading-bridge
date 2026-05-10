"""Aroon Down — single-line projection of the existing aroon() calc.

Companion to :mod:`aroon_up`. See the module docstring there for
the rationale (Phase-9 multi-output dispatch limitation)."""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.aroon import aroon


def aroon_down(
    highs: Sequence[float],
    lows: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Aroon Down line over ``period`` bars."""
    _up, down, _osc = aroon(highs, lows, period)
    return down


__all__ = ["aroon_down"]
