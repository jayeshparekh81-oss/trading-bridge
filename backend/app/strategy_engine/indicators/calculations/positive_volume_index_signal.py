"""PVI signal line - EMA smoothing of Pack 10's positive_volume_index.

Default ``signal_period = 255`` (Fosback's 1-year smoothing window
from "Stock Market Logic", 1976). Output is on the same scale as
PVI (typically near 1000, the PVI seed).

Operators compare ``PVI vs PVI_signal``: PVI > signal = bullish
retail flow; PVI < signal = bearish retail flow (Fosback's "Smart
Money / Dumb Money" framework).

Output length matches input. ``None`` until the EMA seeds.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``signal_period < 2`` -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.ema import ema
from app.strategy_engine.indicators.calculations.positive_volume_index import (
    positive_volume_index,
)


def positive_volume_index_signal(
    closes: Sequence[float],
    volumes: Sequence[float],
    signal_period: int = 255,
) -> list[float | None]:
    """EMA(PVI, signal_period)."""
    if not isinstance(signal_period, int) or isinstance(signal_period, bool) or signal_period < 2:
        raise ValueError(f"signal_period must be int >= 2; got {signal_period!r}.")
    n = len(closes)
    if n != len(volumes):
        raise ValueError(
            f"closes and volumes must match in length; got {n}, {len(volumes)}."
        )
    if n == 0:
        return []
    pvi = positive_volume_index(list(closes), list(volumes))
    if not pvi:
        return [None] * n
    pvi_floats = [v if v is not None else 0.0 for v in pvi]
    smoothed = ema(pvi_floats, signal_period)
    if not smoothed:
        return [None] * n
    out: list[float | None] = list(smoothed)
    return out


__all__ = ["positive_volume_index_signal"]
