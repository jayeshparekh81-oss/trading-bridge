"""OBV vs price divergence detector.

A textbook "smart money / dumb money" signal: price prints a
new high but OBV doesn't follow → distribution under the surface
(bearish divergence). Price prints a new low but OBV holds →
accumulation under the surface (bullish divergence).

Default ``lookback = 20``."""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations._divergence import (
    detect_divergence,
)
from app.strategy_engine.indicators.calculations.obv import obv


def obv_divergence(
    closes: Sequence[float],
    volumes: Sequence[float],
    lookback: int = 20,
) -> list[float | None]:
    """Per-bar OBV-vs-price divergence code."""
    n = len(closes)
    if n != len(volumes):
        raise ValueError(
            f"closes and volumes must have the same length; got {n}, {len(volumes)}."
        )
    obv_line = obv(list(closes), list(volumes))
    if not obv_line:
        return []
    return detect_divergence(closes, obv_line, lookback)


__all__ = ["obv_divergence"]
