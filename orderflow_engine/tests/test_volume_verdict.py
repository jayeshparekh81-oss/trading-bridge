"""Futures volume-reset verdict recalibration (2026-07-15).

Cumulative volume dips transiently from out-of-order/stale feed packets (ltt steps
backward) + pre-open corrections — those are logged but must NOT flip the verdict.
Only a REAL reset does: a single decrease > VOLUME_RESET_PCT of max cumulative
volume, or summed decreases > VOLUME_BUDGET_PCT — and only on a liquid future.
"""

from __future__ import annotations

import json

import verify_session as V
from tests.replayer import fixtures as RF

NS = 1_000_000_000
FULL = V.EXPECTED_SESSION_S


def _day_vol(tmp_path, sym, sid, volumes, ltts=None):
    day = tmp_path / "2026-07-15"
    n = len(volumes)
    step = int(FULL * NS / max(1, n - 1))       # spread across the session -> coverage ok
    rows = [{"ts_recv_ns": 1 * NS + i * step, "ltt": (ltts[i] if ltts else 1 + i),
             "ltp": 100.0 + i * 0.01, "volume": v} for i, v in enumerate(volumes)]
    RF.write_instrument(day, sym, sid, rows)
    RF.write_events(day, [
        {"ts_ns": 0, "kind": "SESSION", "detail": "start", "value_num": None, "security_id": 0},
        {"ts_ns": FULL * NS, "kind": "SESSION", "detail": "end (record_end)",
         "value_num": None, "security_id": 0}])
    (day / "manifest.json").write_text(json.dumps({"date": day.name, "instruments": [
        {"symbol": sym, "security_id": sid, "exchange_segment": "NSE_FNO",
         "kind": "future", "gap_check": True, "expiry": ""}]}))
    return day


def _inst(r, sym):
    return next(i for i in r["instruments"] if i["file"].startswith(sym))


def test_todays_jitter_does_not_partial(tmp_path):
    """A 520-contract dip on a 2.9M book (0.018%, today's worst liquid case) -> PASS."""
    vols = [1_000_000, 2_000_000, 2_900_000, 2_899_480, 2_912_325]   # one -520 dip
    r = V.verify_session(_day_vol(tmp_path, "NIFTY_FUT", 61093, vols))
    assert r["status"] == "PASS", r["problems"]
    ni = _inst(r, "NIFTY_FUT")
    assert ni["volume_decrease_count"] == 1                 # still logged
    assert ni["volume_decrease_pct_single"] < 1.0


def test_real_reset_partials(tmp_path):
    """Volume collapses from ~2M to ~0 and STAYS low -> single decrease ~100% -> PARTIAL."""
    vols = [1_000_000, 2_000_000, 2_000_000, 100, 200, 300]
    r = V.verify_session(_day_vol(tmp_path, "NIFTY_FUT", 61093, vols))
    assert r["status"] == "PARTIAL"
    assert any("volume RESET" in p for p in r["problems"]), r["problems"]


def test_degraded_feed_summed_budget_partials(tmp_path):
    """Many small decreases, none > 1% but summed > 0.5% budget -> PARTIAL."""
    vols = [1000, 995, 1000, 995, 1000, 995, 1000]          # 3x -5 (0.5% each), summed 1.5%
    r = V.verify_session(_day_vol(tmp_path, "NIFTY_FUT", 61093, vols))
    assert r["status"] == "PARTIAL"
    assert any("volume feed degraded" in p for p in r["problems"]), r["problems"]


def test_thin_future_reset_not_verdict(tmp_path):
    """A hard reset on a THIN (non-liquid) future is logged but does NOT flip the day."""
    vols = [9000, 9000, 100, 200, 300]                      # collapse on FINNIFTY (thin)
    r = V.verify_session(_day_vol(tmp_path, "FINNIFTY_FUT", 61091, vols))
    assert r["status"] == "PASS", r["problems"]
    fin = _inst(r, "FINNIFTY_FUT")
    assert fin["volume_decrease_pct_single"] > 1.0          # metric still recorded


def test_ltt_sorted_isolates_out_of_order(tmp_path):
    """The secondary ltt-sorted count isolates a pure out-of-order packet (vanishes)
    from a receipt-order decrease that a real reset would keep."""
    vols = [1000, 1010, 1005, 1010]                         # 1005 arrives with an older ltt
    ltts = [1, 3, 2, 4]
    r = V.verify_session(_day_vol(tmp_path, "NIFTY_FUT", 61093, vols, ltts=ltts))
    ni = _inst(r, "NIFTY_FUT")
    assert ni["volume_decrease_count"] == 1                 # receipt order sees the dip
    assert ni["volume_decreases_ltt_sorted"] == 0           # ltt order is clean -> out-of-order
    assert r["status"] == "PASS", r["problems"]
