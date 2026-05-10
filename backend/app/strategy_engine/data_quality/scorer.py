"""Quality-score and ``can_backtest`` decision logic.

Pure functions — given a list of issues and the candle stream, derive
the numeric score and the gating decision. No I/O, no side effects.
"""

from __future__ import annotations

from datetime import datetime

from app.strategy_engine.data_quality.constants import (
    CRITICAL_PENALTY,
    INFO_PENALTY,
    MAX_MISSING_PERCENT,
    QUALITY_FLOOR_FOR_BACKTEST,
    WARNING_PENALTY,
)
from app.strategy_engine.data_quality.models import DataQualityIssue
from app.strategy_engine.schema.ohlcv import Candle


def compute_quality_score(issues: list[DataQualityIssue]) -> float:
    """Start at 100, deduct per issue by severity, floor at 0.

    The penalty schedule lives in :mod:`constants` so it can be
    tightened without touching the scorer."""
    score = 100.0
    for issue in issues:
        if issue.severity == "critical":
            score -= CRITICAL_PENALTY
        elif issue.severity == "warning":
            score -= WARNING_PENALTY
        else:
            score -= INFO_PENALTY
    return max(0.0, score)


def estimate_missing_percent(
    candles: list[Candle],
    expected_timeframe_minutes: int,
) -> float:
    """Estimate the fraction of expected candles that are absent.

    Built from inter-candle gaps that are large enough to imply at
    least one full bar's worth of data is missing — uses the same
    series the gap check consults so a divergent answer can't surface
    here. Returns ``0.0`` when fewer than two candles are present or
    the timeframe is non-positive."""
    if len(candles) < 2 or expected_timeframe_minutes <= 0:
        return 0.0
    timeframe_seconds = expected_timeframe_minutes * 60
    missing_estimated = 0
    for i in range(1, len(candles)):
        prev_ts = candles[i - 1].timestamp
        curr_ts = candles[i].timestamp
        if not _comparable(prev_ts, curr_ts):
            continue
        delta_seconds = (curr_ts - prev_ts).total_seconds()
        if delta_seconds <= 0:
            continue
        # Each whole timeframe step beyond the first one covers a
        # missing bar — round to the nearest whole step.
        steps = round(delta_seconds / timeframe_seconds)
        if steps > 1:
            missing_estimated += steps - 1
    expected_total = len(candles) + missing_estimated
    if expected_total == 0:
        return 0.0
    return missing_estimated / expected_total


def can_backtest(
    issues: list[DataQualityIssue],
    *,
    quality_score: float,
    missing_percent: float,
) -> bool:
    """Stricter gate the backtest engine consults.

    ``False`` if ANY of:
      * an ``out_of_order`` issue is present (chronology broken)
      * an ``invalid_ohlc`` issue is present (prices untrustworthy)
      * estimated missing fraction exceeds
        :data:`MAX_MISSING_PERCENT`
      * ``quality_score`` is below
        :data:`QUALITY_FLOOR_FOR_BACKTEST`
    """
    blocking_types = {"out_of_order", "invalid_ohlc"}
    if any(issue.issue_type in blocking_types for issue in issues):
        return False
    if missing_percent > MAX_MISSING_PERCENT:
        return False
    return quality_score >= QUALITY_FLOOR_FOR_BACKTEST


def _comparable(a: datetime, b: datetime) -> bool:
    return (a.tzinfo is None) == (b.tzinfo is None)


__all__ = [
    "can_backtest",
    "compute_quality_score",
    "estimate_missing_percent",
]
