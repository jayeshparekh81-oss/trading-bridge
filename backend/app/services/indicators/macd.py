"""Moving Average Convergence Divergence — thin TA-Lib wrapper.

Three EMAs in one shot:
    * ``fast_length`` EMA of close
    * ``slow_length`` EMA of close
    * MACD line  = fast EMA − slow EMA
    * Signal     = ``signal_length`` EMA of the MACD line
    * Histogram  = MACD line − Signal

Seeding convention (Queue UU, 2026-05-31)
    TRADETRI's MACD uses ``talib.MACD`` directly — which seeds the
    internal fast EMA at index ``slow-1`` (NOT ``fast-1``) with the
    immediately-preceding ``fast`` closes ``SMA(close[slow-fast..slow-1])``.
    This is the ALIGNED-seeding industry default; it matches
    pandas-ta-classic's ``ta.macd()`` default and every TA-Lib
    downstream consumer. Pine Script's documented composition
    ``ta.ema(close, fast) - ta.ema(close, slow)`` uses INDEPENDENT
    seeding (each EMA seeded at its own ``length-1``); the two
    conventions diverge by up to ~1 absolute on the first ~10 bars
    after slow-EMA warmup, then decay to machine-noise. Empirical
    impact on shipped templates: zero trade-direction flips, zero
    crossover-timing changes, identical entry/exit counts. Full
    quantification: ``docs/QUEUE_UU_MACD_INVESTIGATION.md``.
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
