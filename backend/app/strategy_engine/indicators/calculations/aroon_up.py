"""Aroon Up — single-line projection of the existing aroon() calc.

The Phase-9 :func:`aroon` function returns ``(up, down, oscillator)``;
its dispatch surfaces ``oscillator`` as the primary line.
``aroon_up`` is the standalone single-output version: a strategy that
wants the up-line as its own named series doesn't have to pay the
multi-output dispatch dance (Phase-9 limitation).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.aroon import aroon


def aroon_up(
    highs: Sequence[float],
    lows: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Aroon Up line over ``period`` bars."""
    up, _down, _osc = aroon(highs, lows, period)
    return up


__all__ = ["aroon_up"]
