"""CLI smoke: summary prints, exit codes, filter passthrough."""

from __future__ import annotations

from replayer import run as R
from tests.replayer import fixtures as F


def test_cli_replays_synthetic_day(tmp_path, capsys):
    data_dir = tmp_path / "data"
    day = data_dir / "2026-07-09"
    F.write_instrument(day, "NIFTY_FUT", 100, [F.tick(10), F.tick(20), F.tick(30)])
    F.write_instrument(day, "BANKNIFTY_FUT", 200, [F.tick(15), F.tick(25)])
    F.write_events(day, [{"ts_ns": 5, "kind": "SESSION", "detail": "start",
                          "value_num": None}])
    F.write_report(day, "PARTIAL", coverage_pct=0.3)

    rc = R.main(["prog", "--date", "2026-07-09", "--speed", "max",
                 "--data-dir", str(data_dir)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "events emitted : 6" in out       # 5 ticks + 1 event
    assert "PARTIAL" in out
    assert "throughput" in out


def test_cli_missing_day_returns_2(tmp_path):
    rc = R.main(["prog", "--date", "2099-01-01", "--data-dir", str(tmp_path / "data")])
    assert rc == 2


def test_cli_instrument_filter(tmp_path, capsys):
    data_dir = tmp_path / "data"
    day = data_dir / "2026-07-09"
    F.write_instrument(day, "NIFTY_FUT", 100, [F.tick(10)])
    F.write_instrument(day, "BANKNIFTY_FUT", 200, [F.tick(20), F.tick(30)])
    rc = R.main(["prog", "--date", "2026-07-09", "--data-dir", str(data_dir),
                 "--instruments", "BANKNIFTY"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "events emitted : 2" in out
