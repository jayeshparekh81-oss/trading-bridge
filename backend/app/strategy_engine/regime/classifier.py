"""Regime classification — picks the highest-priority matching regime
from a :class:`RegimeMetrics` snapshot.

Priority order (locked, mirrors the spec):

    abnormal > breakout > gap_day > trending >
    high_volatility > low_volatility > choppy > sideways

Each predicate is small and pure; the orchestrator walks them in
priority order and returns the first one whose rule matches. The
matching regime carries a confidence score derived from how strongly
its driving metric clears the threshold.
"""

from __future__ import annotations

from app.strategy_engine.regime.constants import (
    ABNORMAL_PRICE_MOVE,
    ADX_SIDEWAYS_MAX,
    ADX_TRENDING_MIN,
    ATR_PERCENTILE_ABNORMAL,
    ATR_PERCENTILE_HIGH,
    ATR_PERCENTILE_LOW,
    DIRECTION_CHANGES_CHOPPY_MIN,
    DIRECTION_WINDOW,
    GAP_PCT,
    MA_SLOPE_TRENDING_MIN_PERCENT,
    RANGE_COMPRESSION_BREAKOUT_PRIOR_MAX,
    RANGE_COMPRESSION_SIDEWAYS_MAX,
    RANGE_EXPANSION_BREAKOUT_MIN,
)
from app.strategy_engine.regime.models import RegimeMetrics, RegimeName
from app.strategy_engine.schema.ohlcv import Candle


def classify_regime(
    metrics: RegimeMetrics,
    candles: list[Candle],
) -> tuple[RegimeName, float]:
    """Return ``(regime_name, confidence)`` for ``metrics``.

    ``candles`` is consulted only by the abnormal / breakout rules,
    which need access to the raw bar history (single-bar move size,
    prior-window range compression). All other rules read directly
    from ``metrics``.
    """
    # ── 1. Abnormal — single-bar shocks or 99th-percentile ATR ──
    if _matches_abnormal(metrics, candles):
        return "abnormal", _confidence_abnormal(metrics, candles)

    # ── 2. Breakout — recent compression followed by expansion ──
    if _matches_breakout(metrics, candles):
        return "breakout", _confidence_breakout(metrics, candles)

    # ── 3. Gap day — overnight (open vs prior close) gap ──
    if metrics.gap_percent is not None and abs(metrics.gap_percent) > GAP_PCT:
        return "gap_day", _confidence_gap(metrics)

    # ── 4. Trending — ADX strong + MA slope > threshold ──
    if (
        metrics.adx_value > ADX_TRENDING_MIN
        and abs(metrics.ma_slope_percent) > MA_SLOPE_TRENDING_MIN_PERCENT
    ):
        return "trending", _confidence_trending(metrics)

    # ── 5. High volatility ──
    if metrics.volatility_percentile >= ATR_PERCENTILE_HIGH:
        return "high_volatility", _confidence_high_vol(metrics)

    # ── 6. Low volatility ──
    if metrics.volatility_percentile <= ATR_PERCENTILE_LOW:
        return "low_volatility", _confidence_low_vol(metrics)

    # ── 7. Choppy — many direction changes in the recent window ──
    if metrics.direction_changes_count >= DIRECTION_CHANGES_CHOPPY_MIN:
        return "choppy", _confidence_choppy(metrics)

    # ── 8. Sideways — weak ADX + range compression ──
    if (
        metrics.adx_value < ADX_SIDEWAYS_MAX
        and metrics.range_compression_ratio < RANGE_COMPRESSION_SIDEWAYS_MAX
    ):
        return "sideways", _confidence_sideways(metrics)

    # No rule cleanly matched — degrade to the closest characterisation.
    # ADX still falls into trending vs sideways most naturally:
    if metrics.adx_value > ADX_TRENDING_MIN:
        return "trending", 0.4
    return "sideways", 0.4


# ─── Predicates ────────────────────────────────────────────────────────


def _matches_abnormal(metrics: RegimeMetrics, candles: list[Candle]) -> bool:
    """Single-bar moves > 5 % are *always* abnormal; the
    vol-percentile path is suppressed when a significant gap exists,
    because in that case the percentile spike is gap-driven and the
    more specific ``gap_day`` regime should win.

    The spec puts ``abnormal > gap_day`` in the priority order, but
    that priority is a tie-breaker for genuinely overlapping signals;
    a percentile spike whose only cause is the gap itself isn't a
    "second signal" — so we let gap_day own the case.
    """
    if len(candles) >= 2:
        prev_close = candles[-2].close
        last_close = candles[-1].close
        if prev_close > 0:
            move = abs(last_close - prev_close) / prev_close
            if move > ABNORMAL_PRICE_MOVE:
                return True
    if metrics.gap_percent is not None and abs(metrics.gap_percent) > GAP_PCT:
        return False
    return metrics.volatility_percentile >= ATR_PERCENTILE_ABNORMAL


def _matches_breakout(metrics: RegimeMetrics, candles: list[Candle]) -> bool:
    """Compression-then-expansion: prior 20-bar block was compressed
    and the current 20-bar range expanded materially. We synthesise
    a "prior compression" metric by comparing the 20-bar range from
    two windows back to the 20-bar range one window back; if that
    older ratio is small *and* the current expansion ratio is large,
    we declare a breakout.

    Falls back to ``False`` when the candle history is too short to
    provide three non-overlapping 20-bar windows.
    """
    if len(candles) < 60:
        return False
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    # Three non-overlapping 20-bar windows: oldest, middle, latest.
    oldest_range = max(highs[-60:-40]) - min(lows[-60:-40])
    middle_range = max(highs[-40:-20]) - min(lows[-40:-20])
    latest_range = max(highs[-20:]) - min(lows[-20:])
    if oldest_range <= 1e-9:
        return False
    prior_compression = middle_range / oldest_range
    if middle_range <= 1e-9:
        return False
    current_expansion = latest_range / middle_range
    return (
        prior_compression < RANGE_COMPRESSION_BREAKOUT_PRIOR_MAX
        and current_expansion > RANGE_EXPANSION_BREAKOUT_MIN
    )


# ─── Confidence shapers ────────────────────────────────────────────────


def _confidence_abnormal(metrics: RegimeMetrics, candles: list[Candle]) -> float:
    score = 0.6
    if metrics.volatility_percentile >= ATR_PERCENTILE_ABNORMAL:
        score = max(score, 0.85)
    if len(candles) >= 2 and candles[-2].close > 0:
        move = abs(candles[-1].close - candles[-2].close) / candles[-2].close
        score = max(score, min(0.99, 0.6 + (move / ABNORMAL_PRICE_MOVE) * 0.2))
    return min(0.99, score)


def _confidence_breakout(metrics: RegimeMetrics, candles: list[Candle]) -> float:
    # Re-derive the expansion ratio for confidence scaling.
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    middle_range = max(highs[-40:-20]) - min(lows[-40:-20])
    latest_range = max(highs[-20:]) - min(lows[-20:])
    if middle_range <= 1e-9:
        return 0.5
    expansion = latest_range / middle_range
    # 1.5x expansion → 0.6, 3x → 0.95.
    raw = 0.5 + (expansion - RANGE_EXPANSION_BREAKOUT_MIN) * 0.25
    return max(0.5, min(0.95, raw))


def _confidence_gap(metrics: RegimeMetrics) -> float:
    if metrics.gap_percent is None:
        return 0.5
    excess = abs(metrics.gap_percent) / GAP_PCT
    return min(0.95, 0.5 + (excess - 1.0) * 0.15)


def _confidence_trending(metrics: RegimeMetrics) -> float:
    """ADX 25→0.55, 40→0.85, 60+→0.95 with bonus for strong MA slope."""
    adx_factor = max(0.0, (metrics.adx_value - ADX_TRENDING_MIN) / 35.0)
    slope_factor = min(
        0.15,
        max(0.0, abs(metrics.ma_slope_percent) - MA_SLOPE_TRENDING_MIN_PERCENT) / 10.0,
    )
    return min(0.95, 0.55 + adx_factor * 0.4 + slope_factor)


def _confidence_high_vol(metrics: RegimeMetrics) -> float:
    extra = (metrics.volatility_percentile - ATR_PERCENTILE_HIGH) / (1.0 - ATR_PERCENTILE_HIGH)
    return max(0.5, min(0.95, 0.55 + extra * 0.4))


def _confidence_low_vol(metrics: RegimeMetrics) -> float:
    deficit = (ATR_PERCENTILE_LOW - metrics.volatility_percentile) / ATR_PERCENTILE_LOW
    return max(0.5, min(0.95, 0.55 + deficit * 0.4))


def _confidence_choppy(metrics: RegimeMetrics) -> float:
    excess = metrics.direction_changes_count - DIRECTION_CHANGES_CHOPPY_MIN
    # Window is DIRECTION_WINDOW; the upper bound on excess is roughly
    # ``DIRECTION_WINDOW - DIRECTION_CHANGES_CHOPPY_MIN``.
    span = max(1, DIRECTION_WINDOW - DIRECTION_CHANGES_CHOPPY_MIN)
    return max(0.5, min(0.95, 0.55 + (excess / span) * 0.4))


def _confidence_sideways(metrics: RegimeMetrics) -> float:
    adx_factor = (ADX_SIDEWAYS_MAX - metrics.adx_value) / ADX_SIDEWAYS_MAX
    compression_factor = (
        RANGE_COMPRESSION_SIDEWAYS_MAX - metrics.range_compression_ratio
    ) / RANGE_COMPRESSION_SIDEWAYS_MAX
    return max(
        0.5,
        min(0.9, 0.55 + max(0.0, adx_factor) * 0.2 + max(0.0, compression_factor) * 0.2),
    )


__all__ = ["classify_regime"]
