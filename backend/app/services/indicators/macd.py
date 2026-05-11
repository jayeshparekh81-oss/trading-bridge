"""Moving Average Convergence Divergence — thin TA-Lib wrapper.

Three EMAs in one shot:
    * ``fast_length`` EMA of close
    * ``slow_length`` EMA of close
    * MACD line  = fast EMA − slow EMA
    * Signal     = ``signal_length`` EMA of the MACD line
    * Histogram  = MACD line − Signal

TA-Lib's :func:`talib.MACD` uses the standard ``MA_Type.EMA`` for all
three averages and returns the trio as parallel arrays. Pine Script's
``ta.macd(close, fast, slow, signal)`` produces the same field set
modulo the same EMA-seeding nuance flagged in
:mod:`app.services.indicators.ema` — practical chart values are
within float-32 epsilon after the first few bars.
"""

from __future__ import annotations

import numpy as np
import talib

from app.schemas.candle import Candle
from app.schemas.indicator import IndicatorName, MacdParams
from app.services.indicators.base import IndicatorParamsLike, closes_as_array


class MacdIndicator:
    """MACD producing macd / signal / histogram series."""

    name = IndicatorName.MACD
    output_names: tuple[str, ...] = ("macd", "signal", "histogram")

    def compute(
        self, candles: list[Candle], params: IndicatorParamsLike
    ) -> dict[str, np.ndarray]:
        assert isinstance(params, MacdParams), (
            f"MacdIndicator dispatched with {type(params).__name__}"
        )
        closes = closes_as_array(candles)
        if closes.size == 0:
            empty = np.empty(0, dtype=np.float64)
            return {"macd": empty, "signal": empty.copy(), "histogram": empty.copy()}
        macd, signal, hist = talib.MACD(
            closes,
            fastperiod=params.fast_length,
            slowperiod=params.slow_length,
            signalperiod=params.signal_length,
        )
        return {"macd": macd, "signal": signal, "histogram": hist}


__all__ = ["MacdIndicator"]
