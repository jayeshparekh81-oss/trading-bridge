"""Bollinger Bands — thin TA-Lib wrapper.

TA-Lib's :func:`talib.BBANDS` computes the band's standard deviation
using the **biased (population)** formula — divides the sum of squared
deviations by ``N``. This matches Pine Script's default
``ta.stdev(src, length)``, which uses ``biased=true`` (also divisor
``N``) by convention. Both libraries — and pandas-ta-classic's
``ta.bbands`` default — produce identical band widths for the same
``(length, mult)`` inputs.

Phase F note: an earlier revision of this module applied a
``sqrt(N / (N - 1))`` post-processing correction under the mistaken
belief that Pine used sample stddev (divisor ``N - 1``). The
correction inflated bands by ~2.6% at length=20 — see
``PHASE_F_DEVIATION_ANALYSIS.md`` for the empirical verdict and the
authorized fix (commit ``680479b``-vs-``c845b3a`` deltas).
"""

from __future__ import annotations

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
        return {"upper": upper, "middle": middle, "lower": lower}


__all__ = ["BollingerBandsIndicator"]
