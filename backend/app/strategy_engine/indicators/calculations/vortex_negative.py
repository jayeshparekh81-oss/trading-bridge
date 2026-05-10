"""Vortex Indicator — VI- line. Companion to :mod:`vortex_positive`.

Reuses the shared ``_vortex`` helper with ``plus=False``."""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.vortex_positive import _vortex


def vortex_negative(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:
    """Vortex VI- line."""
    return _vortex(highs, lows, closes, period, plus=False)


__all__ = ["vortex_negative"]
