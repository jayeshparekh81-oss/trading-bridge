"""Relative Strength Index — thin TA-Lib wrapper.

TA-Lib's RSI uses **Wilder's smoothing** internally (alpha = 1/length,
not the EMA alpha 2/(length+1)). This is precisely what TradingView's
default ``ta.rsi(close, length)`` Pine Script implementation produces,
so no divergence flag is required for RSI.
"""

from __future__ import annotations

import numpy as np
import talib

from app.schemas.candle import Candle
from app.schemas.indicator import IndicatorName, RsiParams
from app.services.indicators.base import IndicatorParamsLike, closes_as_array


class RsiIndicator:
    """Wilder-smoothed RSI in the conventional 0..100 range."""

    name = IndicatorName.RSI
    output_names: tuple[str, ...] = ("value",)

    def compute(
        self, candles: list[Candle], params: IndicatorParamsLike
    ) -> dict[str, np.ndarray]:
        assert isinstance(params, RsiParams), (
            f"RsiIndicator dispatched with {type(params).__name__}"
        )
        closes = closes_as_array(candles)
        if closes.size == 0:
            return {"value": np.empty(0, dtype=np.float64)}
        return {"value": talib.RSI(closes, timeperiod=params.length)}


__all__ = ["RsiIndicator"]
