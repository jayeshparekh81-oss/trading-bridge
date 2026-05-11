"""Bollinger Bands — thin TA-Lib wrapper.

TradingView deviation flag
--------------------------
TA-Lib's :func:`talib.BBANDS` computes the band's standard deviation
using the **biased (population)** formula — divides the sum of squared
deviations by ``N``. TradingView's Pine ``ta.stdev(src, length)`` uses
**sample** stddev — divides by ``N - 1``. For length=20 the bands are
narrower by a factor of ``sqrt(20/19) ≈ 1.026`` in TA-Lib output.

This is a *flag, not a fix* per the locked architecture (TA-Lib defaults
are industry-standard). Documented for ops awareness and surfaced in
``PATCH_INSTRUCTIONS_INDICATORS.md`` as a Phase-2 candidate (could be
fixed by computing rolling sample stddev with pandas, but the latency
tradeoff vs TA-Lib's C path needs measurement).
"""

from __future__ import annotations

import numpy as np
import talib

from app.schemas.candle import Candle
from app.schemas.indicator import BbParams, IndicatorName
from app.services.indicators.base import IndicatorParamsLike, closes_as_array


class BollingerBandsIndicator:
    """Bollinger Bands producing upper / middle / lower series."""

    name = IndicatorName.BB
    output_names: tuple[str, ...] = ("upper", "middle", "lower")

    def compute(
        self, candles: list[Candle], params: IndicatorParamsLike
    ) -> dict[str, np.ndarray]:
        assert isinstance(params, BbParams), (
            f"BollingerBandsIndicator dispatched with {type(params).__name__}"
        )
        closes = closes_as_array(candles)
        if closes.size == 0:
            empty = np.empty(0, dtype=np.float64)
            return {
                "upper": empty,
                "middle": empty.copy(),
                "lower": empty.copy(),
            }
        upper, middle, lower = talib.BBANDS(
            closes,
            timeperiod=params.length,
            nbdevup=params.stddev_multiplier,
            nbdevdn=params.stddev_multiplier,
            matype=0,  # 0 = SMA (TA-Lib default; matches TradingView default basis)
        )
        return {"upper": upper, "middle": middle, "lower": lower}


__all__ = ["BollingerBandsIndicator"]
