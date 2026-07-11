"""Event-calendar guard (Module R6)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from signals.events import Event, active_event, load_events

IST = timezone(timedelta(hours=5, minutes=30))


def test_seed_events_load():
    evs = load_events()                       # the committed orderflow_engine/events.yaml
    assert len(evs) >= 3
    assert any("RBI" in e.label for e in evs)


def test_active_event_inside_window():
    ev = Event(date(2026, 2, 6), time(9, 15), time(12, 30), "RBI MPC", "high_vol")
    ts = int(datetime(2026, 2, 6, 10, 0, tzinfo=IST).timestamp() * 1e9)
    assert active_event([ev], ts) is ev


def test_no_event_outside_window():
    ev = Event(date(2026, 2, 6), time(9, 15), time(12, 30), "RBI MPC", "high_vol")
    ts = int(datetime(2026, 2, 6, 13, 0, tzinfo=IST).timestamp() * 1e9)   # after window
    assert active_event([ev], ts) is None
    ts2 = int(datetime(2026, 2, 5, 10, 0, tzinfo=IST).timestamp() * 1e9)  # wrong day
    assert active_event([ev], ts2) is None


def test_flow_bias_field_parsed():
    evs = load_events()
    assert any(e.flow_bias in ("mild_long", "high_vol", "mild_short", "none") for e in evs)
