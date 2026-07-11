"""End-to-end DepthRecorder session (no network): feed synthetic depth packets
through the real _on_packet path, then close + verify. Asserts R1 writes ONLY
under depth/ and never creates R0's day-root files."""

from __future__ import annotations

from recorder import depth_parser as DP
from recorder.depth_main import DepthRec, DepthRecorder
from tests.fixtures import synthetic as S

NSE_FNO = 2  # segment code


def _cfg(data_dir):
    return {
        "storage": {"data_dir": str(data_dir), "min_free_gb_start": 0,
                    "min_free_gb_runtime": 0, "disk_resume_gb": 1,
                    "disk_check_interval_s": 60, "error_log_interval_s": 300},
        "watchdog": {"gap_threshold_s": 3.0, "poll_interval_s": 1.0},
        "feed": {"ping_interval_s": 15, "ping_timeout_s": 10},
        "schedule": {"connect": "09:05", "record_start": "09:07",
                     "record_end": "15:35", "verify": "15:40"},
        "s3_backup": {"enabled": False},
        "depth": {"enabled": True, "connections": 1, "data_subdir": "depth",
                  "flush_interval_s": 2, "max_buffer_rows": 100,
                  "mem_log_interval_s": 300,
                  "retention": {"enabled": True, "days": 5},
                  "index_futures": [], "equities": []},
    }


def test_full_depth_session_writes_only_under_depth(tmp_path):
    rec = DepthRecorder(_cfg(tmp_path))
    rec.instruments = [DepthRec("NIFTY_FUT", "NSE_FNO", 100, "future")]
    day_dir = rec.data_dir / "2026-07-13"

    rec._open_session(day_dir)
    for k in range(6):
        ts = 1_000_000 * (k + 1)
        bid = DP.parse_depth_packet(S.make_depth(100, side="bid", segment=NSE_FNO, msg_seq=k))
        ask = DP.parse_depth_packet(S.make_depth(100, side="ask", segment=NSE_FNO, msg_seq=k))
        rec._on_packet(bid, ts)
        rec._on_packet(ask, ts + 1)
    rec._close_session("record_end")
    rec._run_verify(day_dir)

    depth = day_dir / "depth"
    # depth artefacts exist, namespaced under depth/
    assert (depth / "NIFTY_FUT_100.parquet").exists()
    assert (depth / "report.json").exists()
    assert (depth / "manifest.json").exists()
    assert (depth / "events.parquet").exists()

    # R0's day-root files must NOT be created by the depth recorder
    assert not (day_dir / "report.json").exists()
    assert not (day_dir / "manifest.json").exists()
    assert not (day_dir / "events.parquet").exists()
    assert not (day_dir / "backup.json").exists()

    import json
    report = json.loads((depth / "report.json").read_text())
    assert report["status"] == "PASS"
    assert report["counts"]["instrument_files"] == 1

    import pyarrow.parquet as pq
    tbl = pq.read_table(str(depth / "NIFTY_FUT_100.parquet"))
    assert tbl.num_rows == 12                      # 6 bid + 6 ask, none lost
    assert set(tbl.column("side").to_pylist()) == {0, 1}


def test_disabled_flag_is_kill_switch(tmp_path):
    cfg = _cfg(tmp_path)
    cfg["depth"]["enabled"] = False
    rec = DepthRecorder(cfg)
    assert rec.enabled is False
