"""Scheduler phase/gating tests (IST, holiday-aware)."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from recorder.scheduler import IST, Phase, Scheduler


def _ist(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=IST)


@pytest.fixture()
def sched():
    # 2026-07-08 is a Wednesday; 2026-07-09 Thursday; add a fake holiday.
    return Scheduler(holidays=frozenset({date(2026, 7, 10)}))


def test_phases_across_a_trading_day(sched):
    assert sched.phase(_ist(2026, 7, 8, 8, 0)) is Phase.WAIT
    assert sched.phase(_ist(2026, 7, 8, 9, 6)) is Phase.CONNECT
    assert sched.phase(_ist(2026, 7, 8, 11, 0)) is Phase.RECORD
    assert sched.phase(_ist(2026, 7, 8, 15, 37)) is Phase.WIND_DOWN
    assert sched.phase(_ist(2026, 7, 8, 15, 45)) is Phase.VERIFY


def test_weekend_is_wait(sched):
    assert sched.phase(_ist(2026, 7, 11, 11, 0)) is Phase.WAIT  # Saturday


def test_holiday_is_wait(sched):
    assert sched.phase(_ist(2026, 7, 10, 11, 0)) is Phase.WAIT  # Friday holiday


def test_next_connect_skips_holiday_and_weekend(sched):
    # After Thursday's session, next connect skips Fri(holiday)+Sat+Sun -> Monday.
    nc = sched.next_connect(_ist(2026, 7, 9, 16, 0))
    assert nc.date() == date(2026, 7, 13)  # Monday
    assert (nc.hour, nc.minute) == (9, 5)


def test_naive_datetime_rejected(sched):
    with pytest.raises(ValueError):
        sched.phase(datetime(2026, 7, 8, 11, 0))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
