"""Per-anomaly check functions for the Data Quality validator.

Each public function takes the candle list and returns a list of
:class:`DataQualityIssue`. Functions are pure: no module-level state,
no clock reads, no logging. The orchestrator in ``validator.py`` runs
them in a fixed order and concatenates results.
"""

from __future__ import annotations

from datetime import datetime

from app.strategy_engine.data_quality import messages
from app.strategy_engine.data_quality.constants import (
    EXPECTED_TIMEFRAME_TOLERANCE,
    GAP_WARNING_MULTIPLIER,
    ZERO_VOLUME_THRESHOLD,
)
from app.strategy_engine.data_quality.models import DataQualityIssue
from app.strategy_engine.schema.ohlcv import Candle

# ─── 1. Out of order ───────────────────────────────────────────────────


def check_out_of_order(candles: list[Candle]) -> list[DataQualityIssue]:
    """Flag any candle whose timestamp is strictly less than the
    previous candle's. Equal timestamps are handled by the duplicate
    check so ``<`` (not ``<=``) keeps the responsibilities separate."""
    issues: list[DataQualityIssue] = []
    for i in range(1, len(candles)):
        prev_ts = candles[i - 1].timestamp
        curr_ts = candles[i].timestamp
        if not _comparable(prev_ts, curr_ts):
            # Mixed tz handled by the timezone check; skip here so we
            # don't raise on the subtraction.
            continue
        if curr_ts < prev_ts:
            msg, hin = messages.out_of_order_messages(i)
            issues.append(
                DataQualityIssue(
                    issue_type="out_of_order",
                    severity="critical",
                    candle_index=i,
                    message=msg,
                    hinglish_message=hin,
                )
            )
    return issues


# ─── 2. Duplicate timestamps ───────────────────────────────────────────


def check_duplicates(candles: list[Candle]) -> list[DataQualityIssue]:
    """Flag any timestamp that appears more than once. Reports the
    duplicate occurrence (i.e. every index after the first time the
    timestamp is seen) so the indices map 1:1 to bars to remove."""
    issues: list[DataQualityIssue] = []
    seen: set[datetime] = set()
    for i, candle in enumerate(candles):
        if candle.timestamp in seen:
            msg, hin = messages.duplicate_candle_messages(candle.timestamp)
            issues.append(
                DataQualityIssue(
                    issue_type="duplicate_candle",
                    severity="critical",
                    candle_index=i,
                    message=msg,
                    hinglish_message=hin,
                )
            )
        else:
            seen.add(candle.timestamp)
    return issues


# ─── 3. Invalid OHLC ───────────────────────────────────────────────────


def check_invalid_ohlc(candles: list[Candle]) -> list[DataQualityIssue]:
    """Flag candles where ``high < low`` or open/close are outside the
    [low, high] band. The :class:`Candle` constructor itself enforces
    this invariant — this check exists for candles built via
    ``model_construct`` (raw upstream sources) where Pydantic
    validation is bypassed."""
    issues: list[DataQualityIssue] = []
    for i, candle in enumerate(candles):
        if candle.high < candle.low:
            msg, hin = messages.invalid_ohlc_messages(
                i, high=candle.high, low=candle.low
            )
            issues.append(
                DataQualityIssue(
                    issue_type="invalid_ohlc",
                    severity="critical",
                    candle_index=i,
                    message=msg,
                    hinglish_message=hin,
                )
            )
            # If high < low the open/close band check is undefined;
            # one issue per candle is enough.
            continue
        for label, value in (("open", candle.open), ("close", candle.close)):
            if value < candle.low or value > candle.high:
                msg, hin = messages.invalid_ohlc_oc_messages(
                    i,
                    label=label,
                    value=value,
                    low=candle.low,
                    high=candle.high,
                )
                issues.append(
                    DataQualityIssue(
                        issue_type="invalid_ohlc",
                        severity="critical",
                        candle_index=i,
                        message=msg,
                        hinglish_message=hin,
                    )
                )
    return issues


# ─── 4. Time gaps + missing candles ────────────────────────────────────


def check_time_gaps(
    candles: list[Candle],
    expected_timeframe_minutes: int,
) -> list[DataQualityIssue]:
    """Inter-candle gap analysis.

    Two mutually exclusive bands keyed off
    :data:`EXPECTED_TIMEFRAME_TOLERANCE` (``1.5x``) and
    :data:`GAP_WARNING_MULTIPLIER` (``2.0x``):

    * ``tolerance < ratio <= warning`` → ``time_gap`` warning.
    * ``ratio > warning``               → ``missing_candle`` critical.

    Out-of-order pairs are skipped — the dedicated
    :func:`check_out_of_order` covers them. Mixed-tz pairs are skipped
    since subtraction would raise; the dedicated
    :func:`check_timezone_mismatch` covers them.
    """
    issues: list[DataQualityIssue] = []
    if len(candles) < 2 or expected_timeframe_minutes <= 0:
        return issues
    timeframe_seconds = expected_timeframe_minutes * 60
    tolerance_seconds = timeframe_seconds * EXPECTED_TIMEFRAME_TOLERANCE
    warning_seconds = timeframe_seconds * GAP_WARNING_MULTIPLIER

    for i in range(1, len(candles)):
        prev_ts = candles[i - 1].timestamp
        curr_ts = candles[i].timestamp
        if not _comparable(prev_ts, curr_ts):
            continue
        delta_seconds = (curr_ts - prev_ts).total_seconds()
        if delta_seconds <= tolerance_seconds:
            continue
        if delta_seconds <= warning_seconds:
            msg, hin = messages.time_gap_messages(curr_ts)
            issues.append(
                DataQualityIssue(
                    issue_type="time_gap",
                    severity="warning",
                    candle_index=i,
                    message=msg,
                    hinglish_message=hin,
                )
            )
        else:
            msg, hin = messages.missing_candle_messages(curr_ts)
            issues.append(
                DataQualityIssue(
                    issue_type="missing_candle",
                    severity="critical",
                    candle_index=i,
                    message=msg,
                    hinglish_message=hin,
                )
            )
    return issues


# ─── 5. Zero volume ────────────────────────────────────────────────────


def check_zero_volume(candles: list[Candle]) -> list[DataQualityIssue]:
    """Single warning when the zero-volume fraction crosses
    :data:`ZERO_VOLUME_THRESHOLD`. One issue per stream — a per-bar
    flood would dominate the report on illiquid sessions."""
    if not candles:
        return []
    zero_count = sum(1 for c in candles if c.volume == 0)
    fraction = zero_count / len(candles)
    if fraction <= ZERO_VOLUME_THRESHOLD:
        return []
    msg, hin = messages.zero_volume_messages(fraction)
    return [
        DataQualityIssue(
            issue_type="zero_volume",
            severity="warning",
            candle_index=None,
            message=msg,
            hinglish_message=hin,
        )
    ]


# ─── 6. Timezone mismatch ──────────────────────────────────────────────


def check_timezone_mismatch(candles: list[Candle]) -> list[DataQualityIssue]:
    """One warning when the stream contains more than one distinct
    ``tzinfo`` value (including ``None`` for naive datetimes). We do
    not attempt to canonicalise different offsets to the same zone —
    distinct objects mean the upstream feed was inconsistent and the
    operator should resolve it."""
    if len(candles) < 2:
        return []
    distinct = {c.timestamp.tzinfo for c in candles}
    if len(distinct) <= 1:
        return []
    msg, hin = messages.timezone_mismatch_messages(len(distinct))
    return [
        DataQualityIssue(
            issue_type="timezone_mismatch",
            severity="warning",
            candle_index=None,
            message=msg,
            hinglish_message=hin,
        )
    ]


# ─── Helpers ───────────────────────────────────────────────────────────


def _comparable(a: datetime, b: datetime) -> bool:
    """``True`` when both timestamps share the same awareness so
    arithmetic / comparison won't raise. Mixed-aware/naive pairs are
    skipped by the gap and order checks; the timezone check reports
    them once."""
    return (a.tzinfo is None) == (b.tzinfo is None)


__all__ = [
    "check_duplicates",
    "check_invalid_ohlc",
    "check_out_of_order",
    "check_time_gaps",
    "check_timezone_mismatch",
    "check_zero_volume",
]
