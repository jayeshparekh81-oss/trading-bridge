"""Regression: session teardown must complete even if the feed task NEVER exits.

2026-07-13 production hang: after record_end, ``await asyncio.gather(*tasks)``
blocked forever because the feed's ``async for message in ws`` sat on an
idle-but-open websocket — the finally-block teardown (close/consolidate/verify)
never ran. The fix waits for the FIRST completed task (the session clock, right
after it sets session_stop) and cancels the rest.

Both daemons are tested with a fake ConnectionManager whose run() NEVER returns
(only responds to cancellation) — with the old gather() teardown these tests hang
and fail via wait_for timeout.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from recorder import depth_main as DM
from recorder import main as M
from recorder import scrip_master as SM
from recorder.depth_main import DepthRec
from tests.test_session_integration import FIX, _config

TIMEOUT_S = 15   # generous; the fixed teardown completes in well under a second


class NeverEndingMgr:
    """A feed manager whose run() never returns on its own (the 07-13 shape)."""

    def __init__(self, *a, **k):
        self.closed = False

    def assign(self, idx, insts):
        pass

    async def add(self, idx, insts):
        pass

    async def run(self, stop_event):
        await asyncio.Event().wait()      # never set -> blocks until cancelled

    async def close(self):
        self.closed = True


def test_r0_teardown_completes_with_neverending_feed(tmp_path, monkeypatch):
    # freeze "now" PAST record_end so the session clock trips immediately
    monkeypatch.setattr(M, "_now", lambda: datetime(2026, 7, 8, 16, 0, tzinfo=M.IST))
    monkeypatch.setattr(SM, "fetch_scrip_master", lambda *a, **k: FIX)
    monkeypatch.setattr(M, "ConnectionManager", NeverEndingMgr)

    rec = M.Recorder(_config(), root=tmp_path)
    rec.creds = SimpleNamespace(client_id="c", access_token="t")
    rec.resolve_instruments()

    async def run():
        global_stop = asyncio.Event()
        await asyncio.wait_for(rec.run_session(global_stop), timeout=TIMEOUT_S)

    asyncio.run(run())    # old teardown: hangs -> TimeoutError -> test FAILS

    day_dir = tmp_path / "data" / "2026-07-08"
    assert (day_dir / "report.json").exists()          # verify ran
    ev = day_dir / "events.parquet"
    assert ev.exists()                                  # session closed cleanly


def test_r1_depth_teardown_completes_with_neverending_feed(tmp_path, monkeypatch):
    monkeypatch.setattr(DM, "_now", lambda: datetime(2026, 7, 8, 16, 0, tzinfo=DM.IST))
    monkeypatch.setattr(DM, "DepthConnectionManager", NeverEndingMgr)

    cfg = {
        "storage": {"data_dir": "data", "min_free_gb_start": 0,
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
                  "retention": {"enabled": False},
                  "index_futures": [], "equities": []},
    }
    rec = DM.DepthRecorder(cfg, root=tmp_path)
    rec.creds = SimpleNamespace(client_id="c", access_token="t")
    rec.instruments = [DepthRec("NIFTY_FUT", "NSE_FNO", 100, "future")]

    async def run():
        global_stop = asyncio.Event()
        await asyncio.wait_for(rec.run_session(global_stop), timeout=TIMEOUT_S)

    asyncio.run(run())

    depth = tmp_path / "data" / "2026-07-08" / "depth"
    assert (depth / "report.json").exists()            # depth verify ran
    assert (depth / "NIFTY_FUT_100.parquet").exists()  # writer closed/consolidated


def test_r0_benign_run_once_task_must_not_end_session(tmp_path, monkeypatch):
    """2026-07-14 restart-loop regression (the exact miss in the teardown fix):
    a benign run-once task finishing (``_arm_options`` draining) must NOT trip
    run_session's FIRST_COMPLETED and tear the session down mid-market.

    With ``_now`` INSIDE the record window the session clock never fires, so a
    correct session stays up until cancelled and writes NO teardown report yet.
    Pre-fix: arm_options returns immediately -> FIRST_COMPLETED -> full teardown
    (report.json written) within a beat -> both asserts fail.
    """
    # 10:00 IST is well within record hours -> the clock does not trip.
    monkeypatch.setattr(M, "_now", lambda: datetime(2026, 7, 8, 10, 0, tzinfo=M.IST))
    monkeypatch.setattr(SM, "fetch_scrip_master", lambda *a, **k: FIX)
    monkeypatch.setattr(M, "ConnectionManager", NeverEndingMgr)

    rec = M.Recorder(_config(), root=tmp_path)
    rec.creds = SimpleNamespace(client_id="c", access_token="t")
    rec.resolve_instruments()
    rec.option_specs = []          # -> _arm_chains hits its run-once exit at once

    async def run():
        global_stop = asyncio.Event()
        task = asyncio.create_task(rec.run_session(global_stop))
        await asyncio.sleep(0.5)   # let arm_options complete + many loop turns
        still_running = not task.done()
        wrote_report = (tmp_path / "data" / "2026-07-08" / "report.json").exists()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return still_running, wrote_report

    still_running, wrote_report = asyncio.run(run())
    assert not wrote_report        # teardown/verify must NOT have run
    assert still_running           # session must still be recording


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
