"""Real-world tolerance: missing/empty/unreadable instruments, gaps, PARTIAL."""

from __future__ import annotations

from replayer.consumer import CountingConsumer
from replayer.engine import ReplayEngine
from replayer.source import ReplaySource
from tests.replayer import fixtures as F


def test_replays_what_exists_when_instruments_missing(tmp_path):
    day = tmp_path / "2026-07-09"
    F.write_instrument(day, "NIFTY_FUT", 100, [F.tick(10), F.tick(20)])
    # only one instrument present; must not crash / must emit its rows
    c = CountingConsumer()
    ReplayEngine(ReplaySource(day)).drive(c, speed="max")
    assert c.packets == 2 and c.events == 0


def test_empty_instrument_file_is_skipped(tmp_path):
    day = tmp_path / "2026-07-09"
    F.write_instrument(day, "NIFTY_FUT", 100, [F.tick(10)])
    F.write_instrument(day, "DEADOPT_999", 999, [])   # zero rows
    cov = ReplaySource(day).coverage()
    assert cov.tick_instruments == 1
    assert cov.empty_instruments == 1
    c = CountingConsumer()
    ReplayEngine(ReplaySource(day)).drive(c, speed="max")
    assert c.packets == 1


def test_unreadable_file_is_skipped_not_fatal(tmp_path):
    day = tmp_path / "2026-07-09"
    F.write_instrument(day, "NIFTY_FUT", 100, [F.tick(10), F.tick(20)])
    (day / "CORRUPT_555.parquet").write_bytes(b"not parquet")
    cov = ReplaySource(day).coverage()
    assert "CORRUPT_555.parquet" in cov.unreadable_files
    c = CountingConsumer()
    ReplayEngine(ReplaySource(day)).drive(c, speed="max")   # no crash
    assert c.packets == 2


def test_gap_events_are_emitted(tmp_path):
    day = tmp_path / "2026-07-09"
    F.write_instrument(day, "NIFTY_FUT", 100, [F.tick(10), F.tick(9999)])
    F.write_events(day, [
        {"ts_ns": 100, "kind": "GAP_OPEN", "detail": "silent>3s", "value_num": None},
        {"ts_ns": 5000, "kind": "GAP", "detail": "resolved", "value_num": 4.9},
    ])
    c = CountingConsumer()
    ReplayEngine(ReplaySource(day)).drive(c, speed="max")
    assert c.packets == 2 and c.events == 2


def test_partial_status_surfaced_in_coverage(tmp_path):
    day = tmp_path / "2026-07-09"
    F.write_instrument(day, "NIFTY_FUT", 100, [F.tick(10)])
    F.write_report(day, "PARTIAL", coverage_pct=0.3)
    cov = ReplaySource(day).coverage()
    assert cov.status == "PARTIAL"
    assert cov.coverage_pct == 0.3


def test_missing_day_dir_yields_no_events(tmp_path):
    src = ReplaySource(tmp_path / "2099-01-01")
    assert not src.exists()
    assert list(ReplayEngine(src).iter_events()) == []


def test_instrument_filter(tmp_path):
    day = tmp_path / "2026-07-09"
    F.write_instrument(day, "NIFTY_FUT", 100, [F.tick(10)])
    F.write_instrument(day, "BANKNIFTY_FUT", 200, [F.tick(20), F.tick(30)])
    src = ReplaySource(day, instruments=["BANKNIFTY"])
    c = CountingConsumer()
    ReplayEngine(src).drive(c, speed="max")
    assert c.packets == 2   # only BANKNIFTY_FUT
