"""Elder Ray (composite Bull/Bear) — wrapper around the existing
elder_ray_bull + elder_ray_bear pair.

Returns ``(bull_power, bear_power)`` tuple — composite view that the
library exposes as a single educational page.

Formula (handled by underlying calcs):
    ema13 = EMA(close, 13)
    bull_power = high - ema13
    bear_power = low  - ema13
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.elder_ray_bull import elder_ray_bull
from app.strategy_engine.indicators.calculations.elder_ray_bear import elder_ray_bear


def elder_ray_bull_bear(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 13,
) -> tuple[list[float | None], list[float | None]]:
    """Composite Elder Ray Bull/Bear — returns (bull_power, bear_power)."""
    bull = elder_ray_bull(highs, closes, period=period)
    bear = elder_ray_bear(lows, closes, period=period)
    return (bull, bear)


__all__ = ["elder_ray_bull_bear"]
