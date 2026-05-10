"""NVI signal line - EMA smoothing of Pack 10's negative_volume_index.

Default ``signal_period = 255`` (Fosback's 1-year smoothing window).
Operators compare ``NVI vs NVI_signal``: NVI > signal = bullish
institutional flow ("Smart Money").

Output length matches input. ``None`` until the EMA seeds.

Edge cases:
    * Empty / mismatched lengths -> ``[]`` / ``ValueError``.
    * ``signal_period < 2`` -> ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.ema import ema
from app.strategy_engine.indicators.calculations.negative_volume_index import (
    negative_volume_index,
)


def negative_volume_index_signal(
    closes: Sequence[float],
    volumes: Sequence[float],
    signal_period: int = 255,
) -> list[float | None]:
    """EMA(NVI, signal_period)."""
    if not isinstance(signal_period, int) or isinstance(signal_period, bool) or signal_period < 2:
        raise ValueError(f"signal_period must be int >= 2; got {signal_period!r}.")
    n = len(closes)
    if n != len(volumes):
        raise ValueError(
            f"closes and volumes must match in length; got {n}, {len(volumes)}."
        )
    if n == 0:
        return []
    nvi = negative_volume_index(list(closes), list(volumes))
    if not nvi:
        return [None] * n
    nvi_floats = [v if v is not None else 0.0 for v in nvi]
    smoothed = ema(nvi_floats, signal_period)
    if not smoothed:
        return [None] * n
    out: list[float | None] = list(smoothed)
    return out


__all__ = ["negative_volume_index_signal"]
