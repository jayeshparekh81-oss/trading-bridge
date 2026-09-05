"""C13 — the IP lock is enforced in code, not left to procedure.

Two clocks, deliberately not collapsed:
  * Dhan holds a whitelisted IP for 7 DAYS       -> ip_whitelisted_at
  * the exchange allows one change per CALENDAR WEEK -> last_ip_change_at
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models.customer_lane import CustomerBrokerLink, CustomerLinkStatus
from app.domains.customer_lane.ip_lock import (BROKER_LOCK_DAYS, IST, IpChangeRefused,
                                               change_static_ip, may_change_ip,
                                               same_calendar_week, week_start)

pytestmark = [pytest.mark.postgres, pytest.mark.asyncio]

DB_URL = os.environ.get(
    "CL_SCRATCH_URL",
    "postgresql+asyncpg://trading_bridge_test:test_password_do_not_use_in_prod"
    "@localhost:5433/cl_scratch",
)
UTC = timezone.utc
MON = datetime(2026, 9, 7, 10, 0, tzinfo=IST)      # Monday
SUN = datetime(2026, 9, 6, 10, 0, tzinfo=IST)      # the Sunday before it


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine(DB_URL, future=True)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
        await s.rollback()
    await engine.dispose()


# ── the five required cases ───────────────────────────────────────────────

async def test_inside_the_7_day_lock_is_refused_with_the_unlock_date():
    d = may_change_ip(current_ip="1.1.1.1", ip_whitelisted_at=MON - timedelta(days=2),
                      last_ip_change_at=MON - timedelta(days=2), now=MON)
    assert d.permitted is False
    assert d.reason == "broker_lock_active"
    assert d.allowed_from == MON - timedelta(days=2) + timedelta(days=BROKER_LOCK_DAYS)
    assert "can be changed on or after" in d.detail


async def test_lock_clear_but_already_changed_this_week_is_refused_with_next_monday():
    d = may_change_ip(current_ip="1.1.1.1", ip_whitelisted_at=MON - timedelta(days=30),
                      last_ip_change_at=MON - timedelta(hours=3), now=MON)
    assert d.permitted is False
    assert d.reason == "already_changed_this_week"
    assert d.allowed_from == datetime(2026, 9, 14, 0, 0, tzinfo=IST)
    assert d.allowed_from.weekday() == 0, "next eligible moment is a Monday"


async def test_both_clocks_clear_is_permitted():
    d = may_change_ip(current_ip="1.1.1.1", ip_whitelisted_at=MON - timedelta(days=30),
                      last_ip_change_at=MON - timedelta(days=30), now=MON)
    assert d.permitted is True and d.reason == "permitted"
    assert bool(d) is True


async def test_missing_whitelist_data_FAILS_CLOSED():
    d = may_change_ip(current_ip="1.1.1.1", ip_whitelisted_at=None,
                      last_ip_change_at=None, now=MON)
    assert d.permitted is False and d.reason == "lock_state_unknown"
    assert "locks the customer out" in d.detail


async def test_missing_change_history_FAILS_CLOSED():
    d = may_change_ip(current_ip="1.1.1.1", ip_whitelisted_at=MON - timedelta(days=30),
                      last_ip_change_at=None, now=MON)
    assert d.permitted is False and d.reason == "change_history_unknown"


# ── the calendar-week boundary: NOT "once per 7 days" ─────────────────────

async def test_sunday_then_monday_is_a_NEW_calendar_week_one_day_later():
    """The case that proves the two clocks are not the same rule. One day apart,
    two calendar weeks. With the broker lock clear, this is PERMITTED."""
    assert not same_calendar_week(SUN, MON)
    d = may_change_ip(current_ip="1.1.1.1",
                      ip_whitelisted_at=SUN - timedelta(days=30),
                      last_ip_change_at=SUN, now=MON)
    assert d.permitted is True, d.detail


async def test_monday_then_friday_is_the_SAME_week_four_days_later():
    fri = datetime(2026, 9, 11, 10, 0, tzinfo=IST)
    assert same_calendar_week(MON, fri)
    d = may_change_ip(current_ip="1.1.1.1", ip_whitelisted_at=MON - timedelta(days=30),
                      last_ip_change_at=MON, now=fri)
    assert d.permitted is False and d.reason == "already_changed_this_week"


async def test_weeks_start_on_monday_in_IST():
    assert week_start(MON) == datetime(2026, 9, 7, 0, 0, tzinfo=IST)
    assert week_start(SUN) == datetime(2026, 8, 31, 0, 0, tzinfo=IST)


async def test_the_IST_choice_actually_changes_the_answer():
    """23:00 UTC Sunday is 04:30 IST Monday — a different calendar week. Computing
    this in UTC would give the wrong answer for ~5.5 hours of every week."""
    late_sunday_utc = datetime(2026, 9, 6, 23, 0, tzinfo=UTC)
    assert late_sunday_utc.astimezone(IST).weekday() == 0, "it is Monday in IST"
    assert not same_calendar_week(datetime(2026, 9, 6, 10, 0, tzinfo=IST),
                                  late_sunday_utc)


async def test_naive_datetimes_are_treated_as_UTC_not_local():
    naive = datetime(2026, 9, 7, 4, 30)
    d = may_change_ip(current_ip="1.1.1.1", ip_whitelisted_at=MON - timedelta(days=30),
                      last_ip_change_at=MON - timedelta(days=30), now=naive)
    assert d.permitted is True


# ── refuses AT THE POINT OF CHANGE ────────────────────────────────────────

async def _link(s, **kw) -> uuid.UUID:
    cid = uuid.uuid4()
    await s.execute(text("INSERT INTO users (id,email,password_hash) VALUES (:i,:e,'x')"),
                    {"i": cid, "e": f"c13-{cid}@test.local"})
    s.add(CustomerBrokerLink(customer_id=cid,
                             status=CustomerLinkStatus.NEVER_CONNECTED, **kw))
    await s.flush()
    return cid


async def test_change_is_REFUSED_at_the_point_of_change_and_mutates_nothing(session):
    cid = await _link(session, assigned_static_ip="1.1.1.1",
                      ip_whitelisted_at=MON - timedelta(days=2),
                      last_ip_change_at=MON - timedelta(days=2))
    with pytest.raises(IpChangeRefused) as exc:
        await change_static_ip(session, cid, "2.2.2.2", now=MON)
    assert exc.value.decision.reason == "broker_lock_active"
    assert exc.value.decision.allowed_from is not None, "tells the customer WHEN"

    from sqlalchemy import select
    link = (await session.execute(select(CustomerBrokerLink).where(
        CustomerBrokerLink.customer_id == cid))).scalar_one()
    assert link.assigned_static_ip == "1.1.1.1", "the IP must not have changed"


async def test_permitted_change_records_the_new_clock(session):
    cid = await _link(session, assigned_static_ip="1.1.1.1",
                      ip_whitelisted_at=MON - timedelta(days=30),
                      last_ip_change_at=MON - timedelta(days=30))
    await change_static_ip(session, cid, "2.2.2.2", now=MON)

    from sqlalchemy import select
    link = (await session.execute(select(CustomerBrokerLink).where(
        CustomerBrokerLink.customer_id == cid))).scalar_one()
    assert link.assigned_static_ip == "2.2.2.2"
    assert link.last_ip_change_at is not None
    assert link.ip_whitelisted_at is None, "the NEW ip is not whitelisted yet"


async def test_first_assignment_is_not_a_change(session):
    cid = await _link(session)
    d = await change_static_ip(session, cid, "3.3.3.3", now=MON)
    assert d.reason == "initial_assignment"


async def test_a_second_change_immediately_after_is_refused(session):
    cid = await _link(session, assigned_static_ip="1.1.1.1",
                      ip_whitelisted_at=MON - timedelta(days=30),
                      last_ip_change_at=MON - timedelta(days=30))
    await change_static_ip(session, cid, "2.2.2.2", now=MON)
    with pytest.raises(IpChangeRefused) as exc:
        await change_static_ip(session, cid, "4.4.4.4", now=MON + timedelta(hours=1))
    assert exc.value.decision.reason == "lock_state_unknown"
