"""Ordering: ts primary, ltt tiebreak, stable final tiebreak; ticks lead events."""

from __future__ import annotations

from replayer.engine import ReplayEngine
from replayer.source import ReplaySource
from tests.replayer import fixtures as F


def _emit(day):
    return list(ReplayEngine(ReplaySource(day)).iter_events())


def test_merges_instruments_in_ts_order(tmp_path):
    day = tmp_path / "2026-07-09"
    F.write_instrument(day, "NIFTY_FUT", 100, [F.tick(10), F.tick(30), F.tick(50)])
    F.write_instrument(day, "BANKNIFTY_FUT", 200, [F.tick(20), F.tick(40)])
    evs = _emit(day)
    assert [e.ts_ns for e in evs] == [10, 20, 30, 40, 50]
    assert all(e.is_tick for e in evs)


def test_ltt_breaks_ties_at_same_recv_ts(tmp_path):
    day = tmp_path / "2026-07-09"
    # same ts_recv_ns=100, different ltt -> lower ltt first
    F.write_instrument(day, "A", 100, [F.tick(100, ltt=555)])
    F.write_instrument(day, "B", 200, [F.tick(100, ltt=111)])
    evs = _emit(day)
    assert [e.security_id for e in evs] == [200, 100]  # ltt 111 (sid200) before 555


def test_final_tiebreak_by_security_id(tmp_path):
    day = tmp_path / "2026-07-09"
    # identical ts AND ltt -> deterministic by security_id
    F.write_instrument(day, "HI", 900, [F.tick(100, ltt=100)])
    F.write_instrument(day, "LO", 100, [F.tick(100, ltt=100)])
    evs = _emit(day)
    assert [e.security_id for e in evs] == [100, 900]


def test_ticks_lead_events_at_same_instant(tmp_path):
    day = tmp_path / "2026-07-09"
    F.write_instrument(day, "NIFTY_FUT", 100, [F.tick(100, ltt=50)])
    F.write_events(day, [{"ts_ns": 100, "kind": "GAP", "detail": "x", "value_num": 4.0}])
    evs = _emit(day)
    assert evs[0].is_tick is True and evs[1].is_tick is False


def test_events_merge_by_ts_into_stream(tmp_path):
    day = tmp_path / "2026-07-09"
    F.write_instrument(day, "NIFTY_FUT", 100, [F.tick(10), F.tick(90)])
    F.write_events(day, [
        {"ts_ns": 5, "kind": "SESSION", "detail": "start", "value_num": None},
        {"ts_ns": 50, "kind": "GAP", "detail": "gap", "value_num": 3.0},
    ])
    evs = _emit(day)
    assert [(e.ts_ns, e.is_tick) for e in evs] == [
        (5, False), (10, True), (50, False), (90, True)]
