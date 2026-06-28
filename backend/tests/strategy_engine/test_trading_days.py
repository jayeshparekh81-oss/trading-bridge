"""Tests for the standalone trading-day counter (options near-expiry-roll prep).

Convention under test: ``trading_days_between(start, end)`` counts trading days
in the half-open interval ``(start, end]`` — start EXCLUSIVE, end INCLUSIVE
("trading days remaining until expiry"). Weekends (and optional holidays) are
skipped. ``start >= end`` → 0.

Anchor dates use the first week of January 2024, which begins on a Monday
(asserted below so the fixtures can't silently drift).
"""

from __future__ import annotations

from datetime import date

from app.strategy_engine.trading_calendar import (
    is_trading_day,
    trading_days_between,
)

# Lock the anchor: 2024-01-01 is a Monday → the week is Mon..Sun = 01..07,
# next Monday = 08. (date.weekday(): Mon=0.)
_MON = date(2024, 1, 1)
_TUE = date(2024, 1, 2)
_WED = date(2024, 1, 3)
_THU = date(2024, 1, 4)
_FRI = date(2024, 1, 5)
_SAT = date(2024, 1, 6)
_SUN = date(2024, 1, 7)
_NEXT_MON = date(2024, 1, 8)


def test_anchor_dates_are_what_we_think() -> None:
    # Guard against fixture drift — if these ever fail, the dates were wrong.
    assert _MON.weekday() == 0  # Monday
    assert _FRI.weekday() == 4  # Friday
    assert _SAT.weekday() == 5 and _SUN.weekday() == 6  # weekend


def test_same_day_is_zero() -> None:
    # (d, d] is empty → 0 trading days remaining when expiry is today.
    assert trading_days_between(_MON, _MON) == 0


def test_adjacent_weekdays_mon_to_tue() -> None:
    # (Mon, Tue] = {Tue} → 1.
    assert trading_days_between(_MON, _TUE) == 1


def test_across_a_weekend_fri_to_mon() -> None:
    # (Fri, Mon] = {Sat, Sun, Mon} → only Mon is a trading day → 1.
    assert trading_days_between(_FRI, _NEXT_MON) == 1


def test_full_week_mon_to_next_mon() -> None:
    # (Mon, nextMon] = Tue,Wed,Thu,Fri,Sat,Sun,Mon → 5 trading days.
    assert trading_days_between(_MON, _NEXT_MON) == 5


def test_start_after_end_is_zero() -> None:
    # Past expiry → 0 (never negative).
    assert trading_days_between(_NEXT_MON, _MON) == 0


def test_holiday_inside_interval_is_skipped() -> None:
    # (Mon, Fri] = Tue,Wed,Thu,Fri → 4; with Wed a holiday → 3.
    assert trading_days_between(_MON, _FRI) == 4
    assert trading_days_between(_MON, _FRI, holidays={_WED}) == 3


def test_spans_month_boundary() -> None:
    # Jan 31 2024 = Wed; (Wed Jan31, Mon Feb05] = Thu(01) Fri(02) Sat(03)
    # Sun(04) Mon(05) → trading: Thu, Fri, Mon → 3.
    jan31 = date(2024, 1, 31)
    feb05 = date(2024, 2, 5)
    assert jan31.weekday() == 2  # Wednesday (anchor guard)
    assert trading_days_between(jan31, feb05) == 3


def test_same_day_with_holiday_on_that_day_is_zero() -> None:
    # (d, d] is empty regardless of d being a holiday → 0.
    assert trading_days_between(_WED, _WED, holidays={_WED}) == 0


def test_friday_to_saturday_is_zero() -> None:
    # (Fri, Sat] = {Sat} → non-trading → 0.
    assert trading_days_between(_FRI, _SAT) == 0


def test_is_trading_day_helper() -> None:
    assert is_trading_day(_MON) is True
    assert is_trading_day(_FRI) is True
    assert is_trading_day(_SAT) is False
    assert is_trading_day(_SUN) is False
    assert is_trading_day(_WED, holidays={_WED}) is False  # weekday but holiday
    assert is_trading_day(_WED, holidays={_THU}) is True   # holiday elsewhere
