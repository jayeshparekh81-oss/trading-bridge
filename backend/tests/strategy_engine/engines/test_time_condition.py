"""Time-of-day condition evaluator tests."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.strategy_engine.engines.time_condition import evaluate_time_condition
from app.strategy_engine.schema.strategy import TimeCondition, TimeConditionOp


def _at(hh: int, mm: int, *, tz: ZoneInfo | None = None) -> datetime:
    """Build a tz-aware datetime at the given HH:MM (UTC by default)."""
    return datetime(2026, 5, 4, hh, mm, tzinfo=tz or UTC)


def test_exact_match_to_the_minute() -> None:
    cond = TimeCondition(type="time", op=TimeConditionOp.EXACT, value="09:15")
    assert evaluate_time_condition(cond, moment=_at(9, 15)) is True
    assert evaluate_time_condition(cond, moment=_at(9, 16)) is False
    assert evaluate_time_condition(cond, moment=_at(9, 14)) is False


def test_exact_ignores_seconds_and_microseconds() -> None:
    cond = TimeCondition(type="time", op=TimeConditionOp.EXACT, value="09:15")
    moment = datetime(2026, 5, 4, 9, 15, 30, 500_000, tzinfo=UTC)
    assert evaluate_time_condition(cond, moment=moment) is True


def test_after_strict_inequality() -> None:
    cond = TimeCondition(type="time", op=TimeConditionOp.AFTER, value="09:30")
    assert evaluate_time_condition(cond, moment=_at(9, 31)) is True
    assert evaluate_time_condition(cond, moment=_at(9, 30)) is False
    assert evaluate_time_condition(cond, moment=_at(9, 29)) is False


def test_before_strict_inequality() -> None:
    cond = TimeCondition(type="time", op=TimeConditionOp.BEFORE, value="15:25")
    assert evaluate_time_condition(cond, moment=_at(15, 24)) is True
    assert evaluate_time_condition(cond, moment=_at(15, 25)) is False
    assert evaluate_time_condition(cond, moment=_at(15, 26)) is False


def test_between_inclusive_at_both_endpoints() -> None:
    cond = TimeCondition(type="time", op=TimeConditionOp.BETWEEN, value="09:15", end="15:25")
    assert evaluate_time_condition(cond, moment=_at(9, 15)) is True
    assert evaluate_time_condition(cond, moment=_at(12, 0)) is True
    assert evaluate_time_condition(cond, moment=_at(15, 25)) is True
    assert evaluate_time_condition(cond, moment=_at(9, 14)) is False
    assert evaluate_time_condition(cond, moment=_at(15, 26)) is False


def test_between_same_start_and_end_is_one_minute_window() -> None:
    cond = TimeCondition(type="time", op=TimeConditionOp.BETWEEN, value="10:00", end="10:00")
    assert evaluate_time_condition(cond, moment=_at(10, 0)) is True
    assert evaluate_time_condition(cond, moment=_at(10, 1)) is False


def test_between_wrap_around_rejected() -> None:
    """22:00 -> 02:00 is not supported in Phase 2."""
    cond = TimeCondition(type="time", op=TimeConditionOp.BETWEEN, value="22:00", end="02:00")
    with pytest.raises(ValueError):
        evaluate_time_condition(cond, moment=_at(23, 0))


def test_evaluator_uses_local_time_of_day_for_ist() -> None:
    """A 09:15 IST condition vs a UTC moment that is 03:45 UTC = 09:15 IST."""
    ist = ZoneInfo("Asia/Kolkata")
    moment = datetime(2026, 5, 4, 9, 15, tzinfo=ist)
    cond = TimeCondition(type="time", op=TimeConditionOp.EXACT, value="09:15")
    assert evaluate_time_condition(cond, moment=moment) is True
