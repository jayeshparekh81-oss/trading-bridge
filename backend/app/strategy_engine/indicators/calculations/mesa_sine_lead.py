"""MESA Sine Lead — companion to :mod:`mesa_sine_wave`.

45° (π/4) phase-leading projection of the dominant-cycle phase.
Crossings of MESA Sine Wave by MESA Lead flag cycle turning
points 1/8 of a cycle ahead of the actual reversal."""

from __future__ import annotations

import math
from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.mesa_sine_wave import (
    _mesa_phase_series,
)


def mesa_sine_lead(
    closes: Sequence[float],
    alpha: float = 0.07,
) -> list[float | None]:
    """Lead-wave projection (sine of phase + π/4)."""
    phase = _mesa_phase_series(closes, alpha)
    return [
        None if p is None else math.sin(p + math.pi / 4.0) for p in phase
    ]


__all__ = ["mesa_sine_lead"]
