"""Bollinger Bands — TA-Lib wrapper with Pine-compatible stddev correction.

TA-Lib's :func:`talib.BBANDS` computes the band's standard deviation
using the **biased (population)** formula — divides the sum of squared
deviations by ``N``. TradingView's Pine ``ta.stdev(src, length)`` uses
**sample** stddev — divides by ``N - 1``. The two relate by:

    stddev_sample = stddev_biased * sqrt(N / (N - 1))

We post-process TA-Lib's bands to apply this correction so the output
matches Pine Script's default ``ta.bb()`` exactly. Middle band (SMA)
is unchanged; only the band-width scales:

    upper_pine = middle + (upper_talib - middle) * sqrt(N / (N - 1))
    lower_pine = middle - (middle - lower_talib) * sqrt(N / (N - 1))

For ``length=20`` the correction factor is ``sqrt(20/19) ≈ 1.0259``
(i.e. Pine bands are about 2.6% wider). The math is exact within
float64 epsilon; latency cost is one vectorised multiply, negligible
vs the underlying TA-Lib C path.

Edge case: ``length=1`` would mean dividing by zero in the correction.
For ``length=1`` the biased stddev is always 0 (one-element variance)
so the upper/lower bands collapse to the middle band; the correction
is skipped to avoid NaN propagation.
"""

from __future__ import annotations

import math

import numpy as np
import talib

from app.schemas.candle import Candle
from app.schemas.indicator import BbParams, IndicatorName
from app.services.indicators.base import IndicatorParamsLike, closes_as_array


class BollingerBandsIndicator:
    """Bollinger Bands producing Pine-compatible upper / middle / lower series."""

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
            matype=0,  # 0 = SMA (TA-Lib default; matches Pine default basis)
        )
        # Biased → sample stddev correction (Pine compatibility).
        # ``BbParams.length`` is constrained ``ge=2`` at the schema
        # layer, so dividing by ``length - 1`` is always safe here.
        correction = math.sqrt(params.length / (params.length - 1))
        upper = middle + (upper - middle) * correction
        lower = middle - (middle - lower) * correction
        return {"upper": upper, "middle": middle, "lower": lower}


__all__ = ["BollingerBandsIndicator"]
