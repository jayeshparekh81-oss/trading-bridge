"""Simple Moving Average — thin TA-Lib wrapper."""

from __future__ import annotations

import numpy as np
import talib

from app.schemas.candle import Candle
from app.schemas.indicator import IndicatorName, SmaParams
from app.services.indicators.base import IndicatorParamsLike, closes_as_array


class SmaIndicator:
    """Simple Moving Average.

    ``SMA(t) = mean(close[t-length+1 : t+1])``. Trivially matches
    TradingView's ``ta.sma`` — no smoothing-convention divergence to
    flag.
    """

    name = IndicatorName.SMA
    output_names: tuple[str, ...] = ("value",)

    def compute(
        self, candles: list[Candle], params: IndicatorParamsLike
    ) -> dict[str, np.ndarray]:
        assert isinstance(params, SmaParams), (
            f"SmaIndicator dispatched with {type(params).__name__}"
        )
        closes = closes_as_array(candles)
        if closes.size == 0:
            return {"value": np.empty(0, dtype=np.float64)}
        # TA-Lib returns NaN for the first (length - 1) positions and
        # for any window that contains a NaN input — the exact
        # NaN-propagate behaviour we want.
        return {"value": talib.SMA(closes, timeperiod=params.length)}


__all__ = ["SmaIndicator"]
