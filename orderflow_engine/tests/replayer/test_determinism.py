"""G1 gate: two replays of the same input produce a byte-identical stream."""

from __future__ import annotations

from replayer.consumer import HashingConsumer
from replayer.engine import ReplayEngine
from replayer.source import ReplaySource
from tests.replayer import fixtures as F


def _multi_instrument_day(root):
    day = root / "2026-07-09"
    F.write_instrument(day, "NIFTY_FUT", 100,
                       [F.tick(t, ltt=t // 10, ltp=100.0 + t) for t in range(1, 60, 3)])
    F.write_instrument(day, "BANKNIFTY_FUT", 200,
                       [F.tick(t, ltt=t // 10, ltp=200.0 + t) for t in range(2, 60, 3)])
    F.write_instrument(day, "NIFTY_CE_24000", 300,
                       [F.tick(t, ltt=t // 10, ltp=5.0 + t) for t in range(1, 60, 7)])
    F.write_events(day, [
        {"ts_ns": 4, "kind": "SESSION", "detail": "start", "value_num": None},
        {"ts_ns": 25, "kind": "GAP", "detail": "silent", "value_num": 3.5},
        {"ts_ns": 59, "kind": "SESSION", "detail": "end", "value_num": None},
    ])
    return day


def test_stream_hash_is_identical_across_two_replays(tmp_path):
    day = _multi_instrument_day(tmp_path)

    h1 = HashingConsumer()
    ReplayEngine(ReplaySource(day)).drive(h1, speed="max")
    h2 = HashingConsumer()
    ReplayEngine(ReplaySource(day)).drive(h2, speed="max")

    assert h1.count == h2.count > 0
    assert h1.hexdigest() == h2.hexdigest()


def test_iter_events_identical_across_runs(tmp_path):
    day = _multi_instrument_day(tmp_path)
    a = [(e.key, e.is_tick, e.ts_ns, e.security_id)
         for e in ReplayEngine(ReplaySource(day)).iter_events()]
    b = [(e.key, e.is_tick, e.ts_ns, e.security_id)
         for e in ReplayEngine(ReplaySource(day)).iter_events()]
    assert a == b


def test_speed_does_not_change_stream_hash(tmp_path):
    day = _multi_instrument_day(tmp_path)
    fast = HashingConsumer()
    ReplayEngine(ReplaySource(day)).drive(fast, speed="max")
    paced = HashingConsumer()
    # 1000x so the test doesn't actually wait, but the pacing path is exercised
    ReplayEngine(ReplaySource(day)).drive(paced, speed="1000x")
    assert fast.hexdigest() == paced.hexdigest()
