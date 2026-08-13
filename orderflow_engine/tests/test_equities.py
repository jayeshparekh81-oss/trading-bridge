"""Equity resolution + dedup through Recorder.resolve_instruments (mini fixture)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from recorder import main as M
from recorder import scrip_master as SM

FIX = Path(__file__).parent / "fixtures" / "mini_scrip.csv"


def _config(equities):
    return {
        "feed": {"request_mode": "full", "ping_interval_s": 15, "ping_timeout_s": 10},
        "connections": {"max": 3},
        "storage": {"data_dir": "data", "flush_interval_s": 5,
                    "max_buffer_rows": 20000, "min_free_gb_warn": 0},
        "watchdog": {"gap_threshold_s": 3.0, "poll_interval_s": 1.0},
        "options": {"atm_window": 5},
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
        "equities": equities,
        "credentials": {"env_files": [], "broker_name": "dhan"},
    }


def test_equities_resolved_and_deduped(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "_now", lambda: datetime(2026, 7, 8, 11, 0, tzinfo=M.IST))
    monkeypatch.setattr(SM, "fetch_scrip_master", lambda *a, **k: FIX)

    # HDFCBANK listed twice (simulating NIFTY + BANKNIFTY overlap) -> deduped
    rec = M.Recorder(_config([{"symbol": "HDFCBANK"}, {"symbol": "BSE"},
                              {"symbol": "HDFCBANK"}]), root=tmp_path)
    rec.resolve_instruments()

    syms = [r.symbol for r in rec.core]
    assert syms.count("HDFCBANK") == 1, "duplicate equity should be deduped"
    equities = {r.symbol: r for r in rec.core if r.kind == "equity"}
    assert set(equities) == {"HDFCBANK", "BSE"}
    assert equities["HDFCBANK"].security_id == 1333
    assert equities["HDFCBANK"].exchange_segment == "NSE_EQ"
    # record-only: equities are gap-exempt (do not gate PASS/FAIL)
    assert all(not r.gap_check for r in equities.values())


def test_unknown_equity_is_skipped_not_fatal(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "_now", lambda: datetime(2026, 7, 8, 11, 0, tzinfo=M.IST))
    monkeypatch.setattr(SM, "fetch_scrip_master", lambda *a, **k: FIX)
    rec = M.Recorder(_config([{"symbol": "HDFCBANK"}, {"symbol": "BOGUSSYM"}]), root=tmp_path)
    rec.resolve_instruments()  # must not raise
    syms = {r.symbol for r in rec.core if r.kind == "equity"}
    assert syms == {"HDFCBANK"}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
