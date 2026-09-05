"""C8 — the exchange trading-day calendar.

The ladder must be silent on an exchange holiday, normal on a trading weekday,
silent at the weekend, and must FAIL LOUD for a date the list does not cover.
"""
from __future__ import annotations

import os
import pathlib
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models.customer_lane import (CustomerBrokerLink, CustomerLinkStatus,
                                         CustomerNotificationLog, LadderStep)
from app.domains.customer_lane import calendar as cal
from app.domains.customer_lane.ladder import is_ladder_trading_day, run_step

pytestmark = [pytest.mark.postgres, pytest.mark.asyncio]

DB_URL = os.environ.get(
    "CL_SCRATCH_URL",
    "postgresql+asyncpg://trading_bridge_test:test_password_do_not_use_in_prod"
    "@localhost:5433/cl_scratch",
)

HOLIDAY = date(2026, 9, 14)      # Mon — Ganesh Chaturthi, listed in holidays.yaml
WEEKDAY = date(2026, 9, 3)       # Thu — a normal trading day
WEEKEND = date(2026, 9, 5)       # Sat
UNCOVERED = date(2027, 3, 1)     # Mon — beyond the list's coverage
ALL_RUNGS = (LadderStep.R1, LadderStep.R2, LadderStep.CALL, LadderStep.RED)


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine(DB_URL, future=True)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
        await s.rollback()
    await engine.dispose()


@pytest.fixture(autouse=True)
def _armed(monkeypatch):
    monkeypatch.setenv("CUSTOMER_LANE_LADDER_ENABLED", "1")
    monkeypatch.delenv(cal.ENV_OVERRIDE, raising=False)
    cal._cached.cache_clear()


async def _disconnected(s) -> uuid.UUID:
    cid = uuid.uuid4()
    await s.execute(text("INSERT INTO users (id,email,password_hash) VALUES (:i,:e,'x')"),
                    {"i": cid, "e": f"c8-{cid}@test.local"})
    s.add(CustomerBrokerLink(customer_id=cid,
                             status=CustomerLinkStatus.NEVER_CONNECTED))
    await s.flush()
    return cid


async def _rows(s, cid) -> list[str]:
    r = await s.execute(select(CustomerNotificationLog.step)
                        .where(CustomerNotificationLog.customer_id == cid))
    return [x.value if hasattr(x, "value") else str(x) for x in r.scalars().all()]


# ── it reuses the estate's ONE list ───────────────────────────────────────

async def test_it_reads_the_existing_shared_list_not_a_copy():
    p = cal.holidays_path()
    assert p.name == "holidays.yaml"
    assert p.parent.name == "orderflow_engine", \
        "the lane must read the estate's shared list, not a vendored copy"
    assert p.exists()
    assert len(cal.load_holidays()) >= 16


async def test_known_holiday_is_not_a_trading_day():
    assert cal.is_trading_day(HOLIDAY) is False
    assert is_ladder_trading_day(HOLIDAY) is False


async def test_normal_weekday_is_a_trading_day():
    assert cal.is_trading_day(WEEKDAY) is True
    assert is_ladder_trading_day(WEEKDAY) is True


async def test_weekend_is_not_a_trading_day():
    assert cal.is_trading_day(WEEKEND) is False


# ── the ladder, end to end ────────────────────────────────────────────────

async def test_no_notification_at_ANY_rung_on_an_exchange_holiday(session):
    cid = await _disconnected(session)
    for step in ALL_RUNGS:
        out = await run_step(session, step, trading_date=HOLIDAY,
                             now=datetime(2026, 9, 14, 3, 0, tzinfo=UTC))
        assert out == [], f"{step.value} fired on an exchange holiday"
    assert await _rows(session, cid) == []


async def test_normal_weekday_runs_the_ladder(session):
    cid = await _disconnected(session)
    for step in ALL_RUNGS:
        await run_step(session, step, trading_date=WEEKDAY,
                       now=datetime(2026, 9, 3, 3, 0, tzinfo=UTC))
    assert sorted(await _rows(session, cid)) == ["CALL", "R1", "R2", "RED"]


async def test_weekend_sends_nothing(session):
    cid = await _disconnected(session)
    for step in ALL_RUNGS:
        assert await run_step(session, step, trading_date=WEEKEND,
                              now=datetime(2026, 9, 5, 3, 0, tzinfo=UTC)) == []
    assert await _rows(session, cid) == []


# ── the loud failures ─────────────────────────────────────────────────────

async def test_a_year_with_no_data_FAILS_LOUD(session):
    """The whole point. Never 'assume it is a trading day'."""
    with pytest.raises(cal.CalendarCoverageError) as exc:
        cal.is_trading_day(UNCOVERED)
    msg = str(exc.value)
    assert "2027" in msg and "holidays.yaml" in msg

    cid = await _disconnected(session)
    with pytest.raises(cal.CalendarCoverageError):
        await run_step(session, LadderStep.R1, trading_date=UNCOVERED,
                       now=datetime(2027, 3, 1, 3, 0, tzinfo=UTC))
    assert await _rows(session, cid) == [], "nothing may be sent on an unjudgeable day"


async def test_missing_file_is_unreadable_not_no_holidays(monkeypatch, tmp_path):
    monkeypatch.setenv(cal.ENV_OVERRIDE, str(tmp_path / "absent.yaml"))
    cal._cached.cache_clear()
    with pytest.raises(cal.CalendarUnavailable) as exc:
        cal.is_trading_day(WEEKDAY)
    assert "not found" in str(exc.value)


async def test_empty_list_is_unreadable_not_no_holidays(monkeypatch, tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text("holidays: []\n")
    monkeypatch.setenv(cal.ENV_OVERRIDE, str(p))
    cal._cached.cache_clear()
    with pytest.raises(cal.CalendarUnavailable) as exc:
        cal.is_trading_day(WEEKDAY)
    assert "ZERO dates" in str(exc.value)


# ── the yearly-refresh alarm ──────────────────────────────────────────────

async def test_alarm_is_silent_well_before_the_end_of_coverage():
    assert cal.coverage_alarm(date(2026, 9, 5)) is None


async def test_alarm_fires_from_1_november_when_next_year_is_absent():
    for day in (date(2026, 11, 1), date(2026, 11, 5), date(2026, 12, 20)):
        msg = cal.coverage_alarm(day)
        assert msg is not None, f"no alarm on {day}"
        assert "RUNNING OUT" in msg and "2027" in msg


async def test_alarm_escalates_once_coverage_has_actually_expired():
    msg = cal.coverage_alarm(date(2027, 1, 4))
    assert msg is not None and "EXPIRED" in msg


async def test_alarm_goes_quiet_once_next_year_is_loaded(monkeypatch, tmp_path):
    p = tmp_path / "next.yaml"
    p.write_text("holidays:\n  - 2026-12-25\n  - 2027-01-26\n")
    monkeypatch.setenv(cal.ENV_OVERRIDE, str(p))
    cal._cached.cache_clear()
    assert cal.coverage_end() == date(2027, 12, 31)
    assert cal.coverage_alarm(date(2026, 11, 5)) is None


# ── H4: resolution ORDER. The env var is primary; the arithmetic is fallback only ──


async def test_env_var_unset_falls_back_to_the_arithmetic_path(monkeypatch):
    monkeypatch.delenv(cal.ENV_OVERRIDE, raising=False)
    cal._cached.cache_clear()
    p = cal.holidays_path()
    assert p.name == "holidays.yaml" and p.parent.name == "orderflow_engine"
    assert cal.is_trading_day(WEEKDAY) is True


async def test_env_var_pointing_at_a_valid_file_WINS(monkeypatch, tmp_path):
    alt = tmp_path / "alt.yaml"
    alt.write_text("holidays:\n  - 2026-12-25\n  - 2027-01-26\n")
    monkeypatch.setenv(cal.ENV_OVERRIDE, str(alt))
    cal._cached.cache_clear()
    assert cal.holidays_path() == alt
    assert cal.coverage_end() == date(2027, 12, 31), "it really read the override"


async def test_env_var_pointing_at_a_MISSING_file_refuses_and_never_falls_back(
    monkeypatch, tmp_path
):
    """THE POINT OF H4. A silent fallback would answer trading-day questions from a
    file the operator did not choose and does not know about."""
    monkeypatch.setenv(cal.ENV_OVERRIDE, str(tmp_path / "not-there.yaml"))
    cal._cached.cache_clear()
    with pytest.raises(cal.CalendarUnavailable) as exc:
        cal.is_trading_day(WEEKDAY)
    msg = str(exc.value)
    assert "not-there.yaml" in msg
    assert cal.ENV_OVERRIDE in msg, "the refusal must name the env var that set it"
    assert "orderflow_engine" not in msg, "must NOT have fallen back to the shared file"


async def test_the_prepared_mount_destination_matches_the_documented_env_value():
    """The compose mount and the documented env var must agree, or the mount is
    pointless. Both are prepared-not-applied; this keeps them in step."""
    compose = pathlib.Path("../docker-compose.yml").read_text()
    dest = "/opt/tradetri/holidays.yaml"
    assert compose.count(f":{dest}:ro") == 3, (
        "expected a read-only mount on backend, celery_worker and celery_beat")
    assert ":rw" not in compose.split("holidays.yaml")[1][:40]
    doc = pathlib.Path("../docs/CUSTOMER_LANE_CALENDAR_IN_CONTAINER.md").read_text()
    assert f"CUSTOMER_LANE_HOLIDAYS_FILE={dest}" in doc
