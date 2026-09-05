"""C9 — the lane refuses to ARM when it cannot answer 'is today a trading day?'.

The deployed image does not contain orderflow_engine/holidays.yaml (verified in
the running container). Without this gate the ladder would arm and then fail
every morning in a worker log. It must refuse at arm time, by name.
"""
from __future__ import annotations

from datetime import date

import pytest
from celery import Celery

from app.domains.customer_lane import calendar as cal
from app.domains.customer_lane import preflight as pf
from app.tasks import customer_lane_tasks as clt


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv(cal.ENV_OVERRIDE, raising=False)
    monkeypatch.delenv("CUSTOMER_LANE_BEAT_ENABLED", raising=False)
    cal._cached.cache_clear()


def test_preflight_passes_with_the_real_calendar():
    r = pf.check(date(2026, 9, 5))
    assert r.ready is True
    assert "holidays.yaml" in r.detail
    assert bool(r) is True


def test_preflight_refuses_when_the_calendar_is_absent(monkeypatch, tmp_path):
    """The production condition today: the file is not in the image."""
    monkeypatch.setenv(cal.ENV_OVERRIDE, str(tmp_path / "not-in-the-image.yaml"))
    cal._cached.cache_clear()
    r = pf.check(date(2026, 9, 5))
    assert r.ready is False
    assert r.reason == "calendar_unavailable"
    assert pf.SUBSYSTEM in r.detail, "the refusal must name the subsystem"


def test_preflight_refuses_once_coverage_has_expired(monkeypatch, tmp_path):
    p = tmp_path / "old.yaml"
    p.write_text("holidays:\n  - 2026-01-26\n")
    monkeypatch.setenv(cal.ENV_OVERRIDE, str(p))
    cal._cached.cache_clear()
    r = pf.check(date(2027, 2, 1))
    assert r.ready is False and r.reason == "calendar_expired"
    assert "2027" in r.detail


def test_assert_can_arm_raises_and_names_the_subsystem(monkeypatch, tmp_path):
    monkeypatch.setenv(cal.ENV_OVERRIDE, str(tmp_path / "absent.yaml"))
    cal._cached.cache_clear()
    with pytest.raises(pf.CustomerLaneNotReady) as exc:
        pf.assert_can_arm(date(2026, 9, 5))
    assert pf.SUBSYSTEM in str(exc.value)


def test_beat_REFUSES_TO_ARM_without_a_resolvable_calendar(monkeypatch, tmp_path):
    """THE POINT. Arming the schedule is what must be blocked."""
    monkeypatch.setenv("CUSTOMER_LANE_BEAT_ENABLED", "1")
    monkeypatch.setenv(cal.ENV_OVERRIDE, str(tmp_path / "absent.yaml"))
    cal._cached.cache_clear()
    app = Celery("probe")
    app.conf.beat_schedule = {}
    with pytest.raises(pf.CustomerLaneNotReady):
        clt.register_beat_entries(app)
    assert app.conf.beat_schedule == {}, "nothing may be scheduled after a refusal"


def test_beat_arms_normally_when_the_calendar_resolves(monkeypatch):
    monkeypatch.setenv("CUSTOMER_LANE_BEAT_ENABLED", "1")
    cal._cached.cache_clear()
    app = Celery("probe2")
    app.conf.beat_schedule = {}
    installed = clt.register_beat_entries(app)
    assert set(installed) == set(clt.LADDER_BEAT)


def test_disarmed_beat_does_not_even_run_preflight(monkeypatch, tmp_path):
    """With the flag off nothing is scheduled, so a missing calendar is not an
    error - the lane is simply not in use."""
    monkeypatch.setenv(cal.ENV_OVERRIDE, str(tmp_path / "absent.yaml"))
    cal._cached.cache_clear()
    app = Celery("probe3")
    app.conf.beat_schedule = {}
    assert clt.register_beat_entries(app) == {}
    assert app.conf.beat_schedule == {}
