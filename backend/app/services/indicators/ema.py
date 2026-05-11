"""Exponential Moving Average — thin TA-Lib wrapper.

TradingView deviation flag
--------------------------
TA-Lib's EMA seeds the recursion with ``SMA(close[0..length-1])`` and
emits NaN for the first ``length - 1`` positions. Pine Script's
``ta.ema(close, length)`` seeds with the first close value and emits a
non-NaN value at position 0. After roughly ``3 * length`` bars the two
converge within float-32 epsilon.

For v1 we ship the TA-Lib seeding (locked architecture: TA-Lib defaults
are industry-standard). Operators comparing chart overlays to a Pine
indicator will see a small leading-edge discrepancy that decays into
the chart history; flag in user docs if needed.
"""

from __future__ import annotations

import numpy as np
import talib

from app.schemas.candle import Candle
from app.schemas.indicator import EmaParams, IndicatorName
from app.services.indicators.base import IndicatorParamsLike, closes_as_array


class EmaIndicator:
    """Exponential Moving Average with Wilder smoothing (alpha = 2/(N+1))."""

    name = IndicatorName.EMA
    output_names: tuple[str, ...] = ("value",)

    def compute(
        self, candles: list[Candle], params: IndicatorParamsLike
    ) -> dict[str, np.ndarray]:
        assert isinstance(params, EmaParams), (
            f"EmaIndicator dispatched with {type(params).__name__}"
        )
        closes = closes_as_array(candles)
        if closes.size == 0:
            return {"value": np.empty(0, dtype=np.float64)}
        return {"value": talib.EMA(closes, timeperiod=params.length)}


__all__ = ["EmaIndicator"]
