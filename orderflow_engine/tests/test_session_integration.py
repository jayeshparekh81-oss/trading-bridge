"""Integration test: two-phase session (core stream -> arm options -> verify).

Uses the mini scrip fixture and a fake ConnectionManager (no network/DB). Drives
packets through Recorder._on_packet, arms option strikes from a simulated open
spot, closes the session, and runs verify_session end-to-end.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from recorder import main as M
from recorder import scrip_master as SM
from recorder.parser import parse_packet
from tests.fixtures import synthetic as S
import verify_session as V

FIX = Path(__file__).parent / "fixtures" / "mini_scrip.csv"


class FakeMgr:
    def __init__(self):
        self.added = []

    async def add(self, idx, insts):
        self.added.append((idx, list(insts)))


def _config():
    return {
        "feed": {"request_mode": "full", "ping_interval_s": 15, "ping_timeout_s": 10},
        "connections": {"max": 2},
        "storage": {"data_dir": "data", "flush_interval_s": 5,
                    "max_buffer_rows": 20000, "min_free_gb_warn": 0},
        "watchdog": {"gap_threshold_s": 3.0, "poll_interval_s": 1.0},
        "options": {"atm_window": 5, "anchor": "open_spot", "recenter": False},
        "schedule": {"connect": "09:05", "record_start": "09:07",
                     "record_end": "15:35", "verify": "15:40"},
        "scrip_master": {"url": "x", "cache_dir": "cache", "stale_hours": 20},
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


def test_two_phase_session_end_to_end(tmp_path, monkeypatch):
    # Freeze "now" to a trading day within the fixture's expiry range.
    monkeypatch.setattr(M, "_now", lambda: datetime(2026, 7, 8, 11, 0, tzinfo=M.IST))
    monkeypatch.setattr(SM, "fetch_scrip_master", lambda *a, **k: FIX)

    rec = M.Recorder(_config(), root=tmp_path)
    rec.resolve_instruments()

    # core = NIFTY spot + NIFTY future + VIX
    core_syms = {r.symbol for r in rec.core}
    assert core_syms == {"NIFTY_SPOT", "NIFTY_FUT", "INDIA_VIX"}
    assert len(rec.option_specs) == 1 and rec.option_specs[0].chain.expiry.isoformat() == "2026-07-14"

    day_dir = tmp_path / "data" / "2026-07-08"
    rec._open_session(day_dir)

    base = 1_751_950_020_000_000_000
    fut_id = next(r.security_id for r in rec.core if r.symbol == "NIFTY_FUT")

    # Phase 1: core ticks (future with monotonic volume, spot sets live price).
    # Spread across the full ~23,280s session so wall-clock coverage is realistic
    # (the 2026-07-15 verify recalibration makes coverage < 95% a PARTIAL driver).
    step = 233_000_000_000   # ~233s * 100 ticks ~= the expected session span
    for i in range(100):
        t = parse_packet(S.make_full(fut_id, volume=1_000_000 + i * 7, ltp=24500 + i * 0.1))
        rec._on_packet(t, base + i * step)
    for i in range(30):
        t = parse_packet(S.make_ticker(13, ltp=24510 + i * 0.05))  # spot -> _latest_price[13]
        rec._on_packet(t, base + i * 200_000_000)
    for i in range(5):
        rec._on_packet(parse_packet(S.make_ticker(21, ltp=12.5 + i * 0.01)), base + i * 10**9)

    assert rec._latest_price[13] > 24500  # spot captured for ATM anchoring

    # Phase 2: arm options from the live spot
    mgr = FakeMgr()
    spec = rec.option_specs[0]
    asyncio.run(rec._arm_one(spec, rec._latest_price[13], mgr))
    assert spec.armed and mgr.added, "options should be subscribed on a connection"
    # ATM±5 over the 5 fixture strikes -> all 10 CE/PE writers created
    opt_ids = [sid for sid, w in rec._writers.items() if "_CE_" in w.symbol or "_PE_" in w.symbol]
    assert len(opt_ids) == 10

    # a couple of option ticks land; most strikes stay empty (illiquid) -> still PASS
    for i in range(8):
        rec._on_packet(parse_packet(S.make_full(40005, volume=100 + i, ltp=120 + i)),
                       base + i * 10**8)

    rec._close_session("record_end")

    # manifest written with gap_check flags
    manifest = json.loads((day_dir / "manifest.json").read_text())
    by_sym = {e["symbol"]: e for e in manifest["instruments"]}
    assert by_sym["NIFTY_FUT"]["gap_check"] is True
    assert by_sym["INDIA_VIX"]["gap_check"] is False
    assert any(e["kind"] == "option" for e in manifest["instruments"])

    # verify: options/VIX lenient (0 rows ok); future volume monotonic; no gaps
    report = V.verify_session(day_dir)
    V._print_report(report)
    assert report["overall"] == "PASS", report["problems"]
    # core = gap-checked spot + future; VIX (gap_check False) + 10 options are lenient
    assert report["counts"]["core"] == 2
    assert report["counts"]["options_lenient"] == 11

    # an empty deep-OTM option file exists and did NOT cause a failure
    empty = [i for i in report["instruments"] if i.get("lenient") and i.get("rows") == 0]
    assert empty, "expected some empty (illiquid) option files"

    # --- S3 backup wiring (fake client, no network) ---
    from recorder.s3_backup import S3Backup
    from tests.test_s3_backup import FakeS3
    rec._run_verify(day_dir)  # write report.json so it is part of the backup set
    fake = FakeS3()
    rec.s3 = S3Backup({"enabled": True, "bucket": "b", "prefix": "orderflow/r0",
                       "retries": 3, "verify": True}, client=fake, sleep=lambda *_: None)
    asyncio.run(rec._backup(day_dir))

    assert (day_dir / "backup.json").exists()          # audit written locally
    assert (day_dir / "NIFTY_FUT_61093.parquet").exists()  # local copy KEPT
    keys = set(fake.objects)
    for suffix in ("/report.json", "/manifest.json", "/events.parquet",
                   "/backup.json", "/NIFTY_FUT_61093.parquet"):
        assert any(k.endswith(suffix) for k in keys), f"missing {suffix} in S3"
    assert all(k.startswith("orderflow/r0/2026-07-08/") for k in keys)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "-s"]))
