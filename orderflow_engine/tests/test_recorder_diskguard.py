"""Recorder-level disk-guard wiring: pre-session mode, drop-mode, skip marker."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq

from recorder import main as M
from recorder import scrip_master as SM
from recorder.diskguard import StartMode
from recorder.parser import parse_packet
from tests.fixtures import synthetic as S

FIX = Path(__file__).parent / "fixtures" / "mini_scrip.csv"


def _config():
    return {
        "feed": {"request_mode": "full", "ping_interval_s": 15, "ping_timeout_s": 10},
        "connections": {"max": 2},
        "storage": {"data_dir": "data", "flush_interval_s": 5, "max_buffer_rows": 20000,
                    "min_free_gb_warn": 0, "min_free_gb_start": 8,
                    "min_free_gb_core_only": 4, "min_free_gb_runtime": 2,
                    "disk_resume_gb": 3, "disk_check_interval_s": 60,
                    "error_log_interval_s": 300},
        "watchdog": {"gap_threshold_s": 3.0, "poll_interval_s": 1.0},
        "options": {"atm_window": 5, "anchor": "open_spot", "recenter": False},
        "schedule": {"connect": "09:05", "record_start": "09:07",
                     "record_end": "15:35", "verify": "15:40"},
        "scrip_master": {"url": "x", "cache_dir": "cache", "stale_hours": 20},
        "retention": {"enabled": True, "retention_days": 10, "run_time": "16:05"},
        "s3_backup": {"enabled": False},
        "indices": [{
            "name": "NIFTY",
            "spot": {"security_id": 13, "exchange_segment": "IDX_I", "gap_check": True},
            "future": {"underlying": "NIFTY", "exch": "NSE",
                       "exchange_segment": "NSE_FNO", "gap_check": True},
            "options": {"enabled": True, "underlying": "NIFTY", "exch": "NSE",
                        "exchange_segment": "NSE_FNO"},
        }],
        "standalone": [{"symbol": "INDIA_VIX", "security_id": 21,
                        "exchange_segment": "IDX_I", "gap_check": False}],
        "credentials": {"env_files": [], "broker_name": "dhan"},
    }


def _recorder(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "_now", lambda: datetime(2026, 7, 8, 11, 0, tzinfo=M.IST))
    monkeypatch.setattr(SM, "fetch_scrip_master", lambda *a, **k: FIX)
    rec = M.Recorder(_config(), root=tmp_path)
    rec.resolve_instruments()
    return rec


def test_apply_disk_plan_modes(tmp_path, monkeypatch):
    rec = _recorder(tmp_path, monkeypatch)
    monkeypatch.setattr(rec, "_free_gb", lambda: 20.0)
    assert rec._apply_disk_plan() is StartMode.FULL and rec._core_only is False
    monkeypatch.setattr(rec, "_free_gb", lambda: 5.0)
    assert rec._apply_disk_plan() is StartMode.CORE_ONLY and rec._core_only is True
    monkeypatch.setattr(rec, "_free_gb", lambda: 1.0)
    assert rec._apply_disk_plan() is StartMode.SKIP


def test_skip_session_writes_marker(tmp_path, monkeypatch):
    rec = _recorder(tmp_path, monkeypatch)
    day = tmp_path / "data" / "2026-07-08"
    rec._skip_session(day, free_gb=1.2)
    ev = pq.read_table(str(day / "events.parquet"))
    assert "DISK_SKIP" in ev.column("kind").to_pylist()


def test_paused_drops_ticks_without_writing(tmp_path, monkeypatch):
    rec = _recorder(tmp_path, monkeypatch)
    day = tmp_path / "data" / "2026-07-08"
    rec._open_session(day)
    fut_id = next(r.security_id for r in rec.core if r.symbol == "NIFTY_FUT")

    def feed(n, start_vol):
        for i in range(n):
            p = parse_packet(S.make_full(fut_id, volume=start_vol + i, ltp=100.0 + i))
            rec._on_packet(p, 1_751_950_020_000_000_000 + i)

    feed(10, 1000)                       # normal writes
    assert rec._writers[fut_id].rows_written + len(rec._writers[fut_id]._buffer) == 10

    rec._paused = True
    feed(7, 2000)                        # dropped, not written
    assert rec._dropped.get(fut_id) == 7
    # buffer/rows unchanged by the paused feed
    w = rec._writers[fut_id]
    assert w.rows_written + len(w._buffer) == 10

    rec._paused = False
    feed(3, 3000)                        # writing resumes
    assert w.rows_written + len(w._buffer) == 13
