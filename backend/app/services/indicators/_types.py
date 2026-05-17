"""NamedTuple result types for the Phase F backtest adapter.

Multi-output indicators (MACD, Bollinger Bands) return structured
NamedTuples instead of ``dict[str, np.ndarray]`` so callers can
destructure positionally on the backtest hot path::

    macd_line, signal, hist = macd(closes)
    upper, middle, lower    = bollinger(closes)

The existing class-based API at :mod:`app.services.indicators.{macd,bb}`
keeps its ``dict[str, np.ndarray]`` return shape for HTTP-response
compatibility — these NamedTuples exist only as a thin convenience
wrapper used by :mod:`app.services.indicators.backtest_adapter`.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np


class MACDResult(NamedTuple):
    """Three parallel arrays from :func:`backtest_adapter.macd`.

    Field order matches TA-Lib's ``talib.MACD`` return order. All
    arrays have the same length as the input ``close`` array; warmup
    positions are ``np.nan``.
    """

    macd: np.ndarray
    signal: np.ndarray
    histogram: np.ndarray


class BollingerResult(NamedTuple):
    """Three parallel arrays from :func:`backtest_adapter.bollinger`.

    Field order matches TA-Lib's ``talib.BBANDS`` return order
    (upper, middle, lower). All arrays have the same length as the
    input ``close`` array; warmup positions are ``np.nan``.
    """

    upper: np.ndarray
    middle: np.ndarray
    lower: np.ndarray


__all__ = ["BollingerResult", "MACDResult"]
