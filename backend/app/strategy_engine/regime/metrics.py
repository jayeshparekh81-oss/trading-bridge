"""Deterministic metric computation for the regime detector.

Each function takes the minimum slice of OHLCV data it needs and
returns a single numeric measurement the classifier can consult.
Calls into Phase 1's ADX/ATR calculations directly (the registry
itself doesn't need to be touched for execution-free metric reads).

All functions are pure — no I/O, no clock reads, no randomness. Inputs
are sequences of numbers; outputs are floats / ints.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.strategy_engine.indicators.calculations.adx import adx
from app.strategy_engine.indicators.calculations.atr import atr
from app.strategy_engine.regime.constants import (
    ADX_PERIOD,
    ATR_PERIOD,
    DIRECTION_WINDOW,
    MA_PERIOD,
    MA_SLOPE_WINDOW,
    RANGE_WINDOW,
)
from app.strategy_engine.regime.models import RegimeMetrics
from app.strategy_engine.schema.ohlcv import Candle


def compute_metrics(candles: Sequence[Candle]) -> RegimeMetrics:
    """Compute every metric the classifier consumes in one pass.

    Empty / very short candle lists are tolerated — undefined metrics
    fall back to defensive zero-ish values that signal "insufficient
    data" rather than crashing. The classifier converts those into the
    ``abnormal`` regime when the upstream candles are too sparse.
    """
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    closes = [c.close for c in candles]
    opens = [c.open for c in candles]

    return RegimeMetrics(
        adx_value=_latest_adx(highs, lows, closes),
        atr_normalized=_atr_normalized(highs, lows, closes),
        ma_slope_percent=_ma_slope_percent(closes),
        range_compression_ratio=_range_compression_ratio(highs, lows),
        gap_percent=_gap_percent(opens, closes),
        direction_changes_count=_direction_changes(closes),
        volatility_percentile=_atr_percentile(highs, lows, closes),
    )


# ─── Individual metric helpers ─────────────────────────────────────────


def _latest_adx(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> float:
    """Latest non-None ADX value, or 0 when the series is too short.

    Phase 1's :func:`adx` returns ``None`` for the first ``2*period - 1``
    bars; we walk back to find the most recent finite value so the
    metric is meaningful as soon as the window is satisfied.
    """
    if len(highs) <= ADX_PERIOD:
        return 0.0
    adx_line, _, _ = adx(highs, lows, closes, period=ADX_PERIOD)
    for value in reversed(adx_line):
        if value is not None:
            return float(value)
    return 0.0


def _atr_normalized(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> float:
    """Current ATR / current close. Returns 0 when undefined."""
    if not closes:
        return 0.0
    atr_line = atr(highs, lows, closes, period=ATR_PERIOD)
    if not atr_line:
        return 0.0
    last = atr_line[-1]
    if last is None:
        return 0.0
    final_close = closes[-1]
    if final_close <= 0:
        return 0.0
    return float(last) / final_close


def _ma_slope_percent(closes: Sequence[float]) -> float:
    """Percent change of the 20-period SMA over ``MA_SLOPE_WINDOW`` bars.

    Returns 0 when the series is too short to compute two SMA points
    spaced by the slope window, or when the older SMA value is zero
    (which would otherwise produce a division by zero).
    """
    needed = MA_PERIOD + MA_SLOPE_WINDOW
    if len(closes) < needed:
        return 0.0
    last_sma = sum(closes[-MA_PERIOD:]) / MA_PERIOD
    older_window_end = len(closes) - MA_SLOPE_WINDOW
    older_window_start = older_window_end - MA_PERIOD
    older_sma = sum(closes[older_window_start:older_window_end]) / MA_PERIOD
    if older_sma == 0:
        return 0.0
    return ((last_sma - older_sma) / older_sma) * 100.0


def _range_compression_ratio(highs: Sequence[float], lows: Sequence[float]) -> float:
    """``last_20_range / previous_20_range``.

    Returns 1.0 (neutral) when fewer than ``2 * RANGE_WINDOW`` bars
    are available, so the sideways/breakout rules don't fire on
    insufficient data. The previous-window range is floored at a
    tiny epsilon to avoid division by zero on flat synthetic series.
    """
    if len(highs) < 2 * RANGE_WINDOW:
        return 1.0
    last_high = max(highs[-RANGE_WINDOW:])
    last_low = min(lows[-RANGE_WINDOW:])
    prev_high = max(highs[-2 * RANGE_WINDOW : -RANGE_WINDOW])
    prev_low = min(lows[-2 * RANGE_WINDOW : -RANGE_WINDOW])
    last_range = last_high - last_low
    prev_range = prev_high - prev_low
    if prev_range <= 1e-9:
        return 1.0
    return last_range / prev_range


def _gap_percent(opens: Sequence[float], closes: Sequence[float]) -> float | None:
    """Last bar's gap (open vs prior close) as a fraction.

    Returns ``None`` when the series has fewer than two bars (no prior
    close to compare against) or when the prior close is zero.
    """
    if len(opens) < 2 or len(closes) < 2:
        return None
    prev_close = closes[-2]
    if prev_close <= 0:
        return None
    return (opens[-1] - prev_close) / prev_close


def _direction_changes(closes: Sequence[float]) -> int:
    """Close-to-close sign flips in the last ``DIRECTION_WINDOW`` bars.

    Walks the recent slice once: counts how many times the sign of the
    bar-over-bar return flips. Flat moves (0) carry the previous sign
    so single doji-style bars don't artificially inflate the count.
    """
    if len(closes) < 3:
        return 0
    window = closes[-DIRECTION_WINDOW:] if len(closes) >= DIRECTION_WINDOW else list(closes)
    changes = 0
    last_sign = 0
    for i in range(1, len(window)):
        diff = window[i] - window[i - 1]
        sign = 1 if diff > 0 else -1 if diff < 0 else last_sign
        if last_sign != 0 and sign != 0 and sign != last_sign:
            changes += 1
        if sign != 0:
            last_sign = sign
    return changes


def _atr_percentile(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> float:
    """Midrank percentile (0-1) of the latest ATR in the ATR series.

    Uses *midrank* semantics — ``(count_below + count_equal / 2) /
    total`` — so a value tied with all others doesn't trivially rank
    at the 100th percentile. That matters for synthetic data and quiet
    markets where many bars produce the same TR; on real data the
    midrank converges to the inclusive rank as ties become rare.

    Returns 0.5 (neutral) when:
      * the ATR series has fewer than 5 finite values (too small a
        sample to meaningfully rank), or
      * the ATR distribution is essentially constant
        (``max - min < 1e-9``), which would otherwise force every
        synthetic / quiet-market case into the abnormal bucket via
        the 99th-percentile predicate.
    """
    atr_line = atr(highs, lows, closes, period=ATR_PERIOD)
    finite = [v for v in atr_line if v is not None]
    if len(finite) < 5:
        return 0.5
    if max(finite) - min(finite) < 1e-9:
        return 0.5
    current = finite[-1]
    below = sum(1 for v in finite if v < current)
    equal = sum(1 for v in finite if v == current)
    return (below + equal / 2) / len(finite)


__all__ = ["compute_metrics"]
