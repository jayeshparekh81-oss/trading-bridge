"""Functional adapter — backtest-engine entry point for the 5 MVP indicators.

Wraps the existing class-based API at
:mod:`app.services.indicators.{sma,ema,rsi,macd,bb}` in functional
free-function form for ergonomic consumption from the Phase F backtest
engine (Component 4)::

    from app.services.indicators.backtest_adapter import (
        sma, ema, rsi, macd, bollinger,
    )

    close = np.array([22000.0, 22010.5, ...])
    rsi_values = rsi(close, period=14)
    macd_line, signal, hist = macd(close)
    upper, middle, lower   = bollinger(close)

Pure composition — every function in this module:

    1. Validates the input ``close`` ndarray (1D, finite, sized for warmup).
    2. Synthesises a minimal :class:`Candle` list with placeholder OHLV.
    3. Calls the existing :class:`IndicatorImpl` ``.compute()`` method.
    4. Extracts the result ``ndarray`` from the returned dict.

Zero math reimplementation. If a deployed indicator class changes its
math, this adapter changes with it automatically — the math lives in
exactly one place (:mod:`app.services.indicators.{sma,ema,rsi,macd,bb}`).

NaN policy: identical to the underlying classes. Warmup positions and
any NaN-propagated bars return ``np.nan``. The backtest engine is
responsible for skipping signal evaluation on NaN bars.

Performance note
    The Candle synthesis pays a Decimal-construction + Pydantic-
    validation cost per bar (~1-3 µs on a modern Mac). For typical
    backtest patterns (precompute the full indicator once per run,
    then iterate bar-by-bar reading from the precomputed array) this
    one-shot cost is amortised across the run. For 10k bars: ~30 ms
    one-time overhead, negligible relative to the rest of the engine.

See :file:`BACKTEST_USAGE.md` (this directory) for end-to-end usage
examples in the backtest engine context.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import numpy as np

from app.schemas.candle import Candle, Timeframe
from app.schemas.indicator import (
    BbParams,
    EmaParams,
    MacdParams,
    RsiParams,
    SmaParams,
)
from app.services.indicators._types import BollingerResult, MACDResult
from app.services.indicators.bb import BollingerBandsIndicator
from app.services.indicators.ema import EmaIndicator
from app.services.indicators.macd import MacdIndicator
from app.services.indicators.rsi import RsiIndicator
from app.services.indicators.sma import SmaIndicator


# Fixed adapter epoch — the indicator math never reads timestamp values,
# only the close field. Any tz-aware datetime satisfies the Candle
# schema validators; pinning the epoch keeps the adapter deterministic.
_EPOCH = datetime(2025, 1, 1, tzinfo=timezone.utc)
_TIMEFRAME = Timeframe.FIVE_MIN


def _validate_close(close: np.ndarray, min_length: int) -> np.ndarray:
    """Coerce input to a float64 1-D contiguous ndarray and validate.

    Raises ``ValueError`` if the array is not 1-D, contains ``inf``,
    or is shorter than ``min_length`` bars (the minimum the indicator
    needs to produce any non-NaN output). ``np.nan`` in the input is
    allowed — TA-Lib propagates it correctly to the output.
    """
    arr = np.asarray(close, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"close must be 1-D, got shape {arr.shape}")
    if np.isinf(arr).any():
        raise ValueError("close contains inf — NaN is allowed but inf is not")
    if arr.size < min_length:
        raise ValueError(
            f"close has {arr.size} bars but indicator needs at least "
            f"{min_length} bars to produce any non-NaN output"
        )
    return np.ascontiguousarray(arr)


def _synth_candles(close: np.ndarray) -> list[Candle]:
    """Build a minimal :class:`Candle` list from an ndarray of closes.

    OHLV are placeholders: open=high=low=close, volume=0. Timestamps
    are 5-minute increments from a fixed UTC epoch. The indicator
    classes only read the ``close`` field, so the placeholders are
    inert with respect to indicator math.

    ``Decimal(str(c))`` round-trips through float64 exactly — Python's
    ``str(float)`` produces the shortest unique repr, so
    ``float(Decimal(str(x))) == x``.
    """
    return [
        Candle(
            symbol="ADAPTER",
            timeframe=_TIMEFRAME,
            timestamp=_EPOCH + timedelta(seconds=_TIMEFRAME.seconds * i),
            open=Decimal(str(float(c))),
            high=Decimal(str(float(c))),
            low=Decimal(str(float(c))),
            close=Decimal(str(float(c))),
            volume=0,
        )
        for i, c in enumerate(close)
    ]


def sma(close: np.ndarray, period: int = 20) -> np.ndarray:
    """Simple moving average — TA-Lib via :class:`SmaIndicator`.

    First ``period - 1`` positions are NaN; subsequent positions are
    the rolling arithmetic mean of the trailing window. Matches
    Pine ``ta.sma`` exactly (trivial — no smoothing convention to
    diverge on). Output length equals input length.
    """
    arr = _validate_close(close, period)
    candles = _synth_candles(arr)
    return SmaIndicator().compute(candles, SmaParams(length=period))["value"]


def ema(close: np.ndarray, period: int = 20) -> np.ndarray:
    """Exponential moving average — TA-Lib via :class:`EmaIndicator`.

    First ``period - 1`` positions are NaN; index ``period - 1`` is
    ``mean(close[0..period-1])`` (SMA seed); subsequent positions
    follow the recurrence ``alpha * close[t] + (1 - alpha) * ema[t-1]``
    with ``alpha = 2 / (period + 1)``. Matches Pine ``ta.ema`` to
    float64 epsilon. Output length equals input length.
    """
    arr = _validate_close(close, period)
    candles = _synth_candles(arr)
    return EmaIndicator().compute(candles, EmaParams(length=period))["value"]


def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder-smoothed RSI in the 0..100 range — TA-Lib via
    :class:`RsiIndicator`.

    First ``period`` positions are NaN; first valid value at index
    ``period``. Uses Wilder's smoothing (``alpha = 1 / period``,
    NOT the EMA alpha) — matches Pine ``ta.rsi`` to float64 epsilon.
    Output length equals input length.
    """
    arr = _validate_close(close, period + 1)
    candles = _synth_candles(arr)
    return RsiIndicator().compute(candles, RsiParams(length=period))["value"]


def macd(
    close: np.ndarray,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> MACDResult:
    """MACD — TA-Lib via :class:`MacdIndicator`.

    Returns ``(macd_line, signal_line, histogram)``. All three arrays
    have length equal to ``close``; warmup region is NaN. First valid
    macd_line at index ``slow - 1``; first valid signal_line at index
    ``slow + signal - 2``.
    """
    arr = _validate_close(close, slow + signal - 1)
    candles = _synth_candles(arr)
    out = MacdIndicator().compute(
        candles,
        MacdParams(
            fast_length=fast,
            slow_length=slow,
            signal_length=signal,
        ),
    )
    return MACDResult(
        macd=out["macd"],
        signal=out["signal"],
        histogram=out["histogram"],
    )


def bollinger(
    close: np.ndarray,
    period: int = 20,
    stddev: float = 2.0,
) -> BollingerResult:
    """Bollinger Bands — TA-Lib via :class:`BollingerBandsIndicator`.

    Returns ``(upper, middle, lower)``. All three arrays have length
    equal to ``close``; first ``period - 1`` positions are NaN.
    Middle band is ``SMA(close, period)``; outer bands are
    ``middle ± stddev * biased_stddev(close, period)`` — Pine ``ta.bb``
    default convention (matches TradingView).
    """
    arr = _validate_close(close, period)
    candles = _synth_candles(arr)
    out = BollingerBandsIndicator().compute(
        candles,
        BbParams(length=period, stddev_multiplier=stddev),
    )
    return BollingerResult(
        upper=out["upper"],
        middle=out["middle"],
        lower=out["lower"],
    )


__all__ = [
    "BollingerResult",
    "MACDResult",
    "bollinger",
    "ema",
    "macd",
    "rsi",
    "sma",
]
