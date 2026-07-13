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


def test_slicing_preserves_total_order(tmp_path, monkeypatch):
    """2026-07-13 fix: the time-sliced merge must emit the EXACT stream a
    whole-day merge emits — same events, same order — including at slice
    boundaries, with out-of-order files, null ts, and same-ts ties."""
    import replayer.engine as E
    from replayer.consumer import HashingConsumer
    from replayer.engine import ReplayEngine
    from replayer.source import ReplaySource

    day = tmp_path / "2026-07-13"
    # out-of-order ts within a file (salvage shape) + ties + a null-ts row
    F.write_instrument(day, "A_FUT", 1,
                       [F.tick(50, ltt=5), F.tick(10, ltt=1), F.tick(30, ltt=3),
                        F.tick(30, ltt=3), F.tick(None), F.tick(90, ltt=9)])
    F.write_instrument(day, "B_FUT", 2,
                       [F.tick(20, ltt=2), F.tick(30, ltt=3), F.tick(60, ltt=6)])
    F.write_events(day, [{"ts_ns": 30, "kind": "GAP", "detail": "g", "value_num": 1.0},
                         {"ts_ns": 70, "kind": "STATUS", "detail": "s", "value_num": None}])

    def _run():
        h = HashingConsumer()
        ReplayEngine(ReplaySource(day)).drive(h, speed="max")
        return h.count, h.hexdigest()

    monkeypatch.setattr(E, "SLICE_TARGET_ROWS", 1_000_000)   # one slice (= old whole-day)
    single = _run()
    monkeypatch.setattr(E, "SLICE_TARGET_ROWS", 2)           # many tiny slices
    sliced = _run()
    assert single == sliced
    assert single[0] == 11                                    # every row emitted once
