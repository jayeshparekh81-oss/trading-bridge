"""Replayer depth-stream support + determinism (Module R1 over R2)."""

from __future__ import annotations

from recorder.depth_schema import SIDE_ASK, SIDE_BID

from replayer.consumer import CountingConsumer, HashingConsumer
from replayer.engine import ReplayEngine
from replayer.source import ReplaySource
from tests.replayer import fixtures as F


def _day(tmp_path):
    day = tmp_path / "2026-07-13"
    F.write_instrument(day, "NIFTY_FUT", 100, [F.tick(10, ltt=1), F.tick(90, ltt=2)])
    F.write_depth(day, "NIFTY_FUT", 100, [
        F.depth_row(20, side=SIDE_BID), F.depth_row(20, side=SIDE_ASK),
        F.depth_row(80, side=SIDE_BID),
    ])
    F.write_events(day, [
        {"ts_ns": 5, "kind": "SESSION", "detail": "start", "value_num": None},
        {"ts_ns": 95, "kind": "GAP", "detail": "gap", "value_num": 3.0},
    ])
    return day


def test_counts_depth_ticks_events(tmp_path):
    src = ReplaySource(_day(tmp_path))
    c = CountingConsumer()
    ReplayEngine(src).drive(c, speed="max")
    assert c.packets == 2
    assert c.depth == 3
    assert c.events == 2
    assert c.total == 7


def test_depth_merged_in_ts_order(tmp_path):
    src = ReplaySource(_day(tmp_path))
    streams = [(e.ts_ns, e.stream) for e in ReplayEngine(src).iter_events()]
    assert streams == [
        (5, "event"), (10, "tick"), (20, "depth"), (20, "depth"),
        (80, "depth"), (90, "tick"), (95, "event")]


def test_tick_then_depth_then_event_at_same_instant(tmp_path):
    day = tmp_path / "2026-07-13"
    F.write_instrument(day, "X", 1, [F.tick(50, ltt=7)])
    F.write_depth(day, "X", 1, [F.depth_row(50, side=SIDE_BID)])
    F.write_events(day, [{"ts_ns": 50, "kind": "STATUS", "detail": "s", "value_num": None}])
    streams = [e.stream for e in ReplayEngine(ReplaySource(day)).iter_events()]
    assert streams == ["tick", "depth", "event"]


def test_determinism_with_depth(tmp_path):
    src = ReplaySource(_day(tmp_path))
    h1, h2 = HashingConsumer(), HashingConsumer()
    ReplayEngine(src).drive(h1, speed="max")
    ReplayEngine(src).drive(h2, speed="max")
    assert h1.hexdigest() == h2.hexdigest()
    assert h1.count == 7
