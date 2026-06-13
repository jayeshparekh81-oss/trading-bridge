"""Tests for ``app.services.historical_candles.rate_limit_guard``.

Pure-Python, no DB. The frozen-clock pattern (passing ``now_utc`` as a
parameter) means we don't need freezegun — every test can synthesise
an instant directly.

Test matrix tries each leaf of the decision tree:
    * Weekday market hours (09:00-15:59 IST) → live_market 20%
    * Weekday off-market (16:00 onwards / before 09:00) → off_market 80%
    * Weekend (Sat/Sun, any clock time) → off_market 80%
    * Kill-switch paused_live overrides clock → paused 80%
    * Naive datetime → ValueError
    * Custom total_budget_rps scales correctly
    * total_budget_rps <= 0 → ValueError
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.services.historical_candles.rate_limit_guard import (
    DHAN_HISTORICAL_BUDGET_RPS,
    BackfillQuota,
    compute_backfill_quota,
    is_off_market_window_ist,
)

_IST = ZoneInfo("Asia/Kolkata")


def _ist_instant(year: int, month: int, day: int, hh: int, mm: int = 0) -> datetime:
    """Helper: build a TZ-aware UTC datetime that corresponds to the
    given IST wall-clock instant. Tests read more naturally in IST."""
    return datetime(year, month, day, hh, mm, tzinfo=_IST).astimezone(UTC)


# ═══════════════════════════════════════════════════════════════════════
# is_off_market_window_ist
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "hh,mm",
    [(9, 0), (9, 1), (10, 30), (12, 0), (15, 59)],
)
def test_off_market__false_during_weekday_market_hours(hh: int, mm: int) -> None:
    # 2026-06-15 is a Monday.
    ts = _ist_instant(2026, 6, 15, hh, mm)
    assert is_off_market_window_ist(ts) is False


@pytest.mark.parametrize(
    "hh,mm",
    [(16, 0), (16, 1), (18, 0), (23, 59), (0, 0), (7, 0), (8, 59)],
)
def test_off_market__true_outside_weekday_market_hours(hh: int, mm: int) -> None:
    ts = _ist_instant(2026, 6, 15, hh, mm)  # Monday
    assert is_off_market_window_ist(ts) is True


@pytest.mark.parametrize(
    "weekday_offset",
    [5, 6],  # Sat=5, Sun=6 — both should be off
)
def test_off_market__weekends_always_off_regardless_of_clock(
    weekday_offset: int,
) -> None:
    # 2026-06-13 is a Saturday; +1 day → Sunday.
    base = _ist_instant(2026, 6, 13, 12, 0)
    ts = base + timedelta(days=(weekday_offset - 5))
    assert is_off_market_window_ist(ts) is True


def test_off_market__market_open_boundary_is_inclusive() -> None:
    """09:00 IST on a weekday is ON market — boundary inclusive."""
    ts = _ist_instant(2026, 6, 15, 9, 0)
    assert is_off_market_window_ist(ts) is False


def test_off_market__market_close_boundary_is_off() -> None:
    """16:00 IST on a weekday is OFF market — close boundary exclusive
    on the open side, so the second the bell rings the worker can
    accelerate."""
    ts = _ist_instant(2026, 6, 15, 16, 0)
    assert is_off_market_window_ist(ts) is True


def test_off_market__naive_datetime_raises_value_error() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        is_off_market_window_ist(datetime(2026, 6, 15, 12, 0))


# ═══════════════════════════════════════════════════════════════════════
# compute_backfill_quota
# ═══════════════════════════════════════════════════════════════════════


def test_quota__live_market_hours_returns_20_percent() -> None:
    ts = _ist_instant(2026, 6, 15, 10, 30)  # Monday 10:30
    q = compute_backfill_quota(now_utc=ts)
    assert isinstance(q, BackfillQuota)
    assert q.share == pytest.approx(0.20)
    assert q.backfill_rps == pytest.approx(DHAN_HISTORICAL_BUDGET_RPS * 0.20)
    assert q.rationale == "market_hours_live"


def test_quota__off_market_returns_80_percent() -> None:
    ts = _ist_instant(2026, 6, 15, 22, 0)  # Monday 22:00
    q = compute_backfill_quota(now_utc=ts)
    assert q.share == pytest.approx(0.80)
    assert q.backfill_rps == pytest.approx(DHAN_HISTORICAL_BUDGET_RPS * 0.80)
    assert q.rationale == "off_market"


def test_quota__weekend_returns_off_market_rationale() -> None:
    ts = _ist_instant(2026, 6, 13, 12, 0)  # Saturday 12:00
    q = compute_backfill_quota(now_utc=ts)
    assert q.share == pytest.approx(0.80)
    assert q.rationale == "off_market"


def test_quota__paused_live_strategy_overrides_market_hours() -> None:
    """Even at 10:30 IST on a Monday, paused_live_strategy → 80%."""
    ts = _ist_instant(2026, 6, 15, 10, 30)
    q = compute_backfill_quota(now_utc=ts, kill_switch_paused_live=True)
    assert q.share == pytest.approx(0.80)
    assert q.rationale == "kill_switch_paused_live_strategy"


def test_quota__paused_live_distinct_from_off_market_rationale() -> None:
    """At an off-market instant, paused-live's rationale token still
    wins so the audit trail records the exceptional cause."""
    ts = _ist_instant(2026, 6, 15, 22, 0)
    q = compute_backfill_quota(now_utc=ts, kill_switch_paused_live=True)
    assert q.rationale == "kill_switch_paused_live_strategy"


def test_quota__custom_total_budget_scales_proportionally() -> None:
    ts = _ist_instant(2026, 6, 15, 22, 0)
    q = compute_backfill_quota(now_utc=ts, total_budget_rps=10.0)
    assert q.backfill_rps == pytest.approx(8.0)
    assert q.share == pytest.approx(0.80)


def test_quota__zero_budget_rejected() -> None:
    ts = _ist_instant(2026, 6, 15, 22, 0)
    with pytest.raises(ValueError, match="must be > 0"):
        compute_backfill_quota(now_utc=ts, total_budget_rps=0.0)


def test_quota__negative_budget_rejected() -> None:
    ts = _ist_instant(2026, 6, 15, 22, 0)
    with pytest.raises(ValueError, match="must be > 0"):
        compute_backfill_quota(now_utc=ts, total_budget_rps=-1.0)


def test_quota__naive_datetime_propagates_value_error() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        compute_backfill_quota(now_utc=datetime(2026, 6, 15, 12, 0))
