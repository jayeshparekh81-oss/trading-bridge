"""Data Quality validator — orchestrator.

Pure deterministic pipeline:

    candles ─► checks ─► scorer ─► report

No LLM calls, no network, no clock reads. Inputs are immutable
sequences of :class:`Candle`; outputs are frozen Pydantic models.
"""

from __future__ import annotations

from app.strategy_engine.data_quality.checks import (
    check_duplicates,
    check_invalid_ohlc,
    check_out_of_order,
    check_time_gaps,
    check_timezone_mismatch,
    check_zero_volume,
)
from app.strategy_engine.data_quality.messages import summary_for
from app.strategy_engine.data_quality.models import (
    DataQualityIssue,
    DataQualityReport,
)
from app.strategy_engine.data_quality.scorer import (
    can_backtest,
    compute_quality_score,
    estimate_missing_percent,
)
from app.strategy_engine.schema.ohlcv import Candle


def validate_candles(
    candles: list[Candle],
    expected_timeframe_minutes: int = 5,
) -> DataQualityReport:
    """Run all quality checks against ``candles`` and return a report.

    Args:
        candles: OHLCV bars in nominal chronological order. The order
            is *not* required by the validator (out-of-order is one of
            the things we flag) — but consumers should index ``issues``
            against the same list they passed in.
        expected_timeframe_minutes: Bar interval in minutes. Used by
            the gap / missing-candle checks and the missing-percent
            estimate. Non-positive values disable those checks.

    Returns:
        :class:`DataQualityReport` with the deterministic verdict.
    """
    # The checks are independent and run in a fixed order so the
    # ``issues`` tuple is stable for the same input — callers can
    # compare reports byte-for-byte.
    issues: list[DataQualityIssue] = []
    issues.extend(check_out_of_order(candles))
    issues.extend(check_duplicates(candles))
    issues.extend(check_invalid_ohlc(candles))
    issues.extend(check_time_gaps(candles, expected_timeframe_minutes))
    issues.extend(check_zero_volume(candles))
    issues.extend(check_timezone_mismatch(candles))

    quality_score = compute_quality_score(issues)
    missing_percent = estimate_missing_percent(candles, expected_timeframe_minutes)
    backtestable = can_backtest(
        issues,
        quality_score=quality_score,
        missing_percent=missing_percent,
    )
    is_valid = not any(issue.severity == "critical" for issue in issues)

    return DataQualityReport(
        is_valid=is_valid,
        total_candles=len(candles),
        issues=tuple(issues),
        quality_score=quality_score,
        summary_hinglish=summary_for(backtestable, quality_score),
        can_backtest=backtestable,
    )


__all__ = ["validate_candles"]
