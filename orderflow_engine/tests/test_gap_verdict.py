"""Gap-threshold recalibration verdict (2026-07-15).

Index instruments legitimately go quiet 3-10s (cadence); those must NOT flip the
day verdict. PARTIAL only on a real outage: a single liquid-instrument
(NIFTY_FUT/BANKNIFTY_FUT) gap > 60s, any reconnect/disconnect, or coverage < 95%.
Session-end open-ended gaps are excluded entirely.
"""

from __future__ import annotations

import json
from pathlib import Path

import verify_session as V
from tests.replayer import fixtures as RF

NS = 1_000_000_000
FULL = V.EXPECTED_SESSION_S   # 23280s


def _day(tmp_path, *, gaps=(), reconnects=0, disconnects=0, span_s=FULL, monotonic=True):
    day = tmp_path / "2026-07-15"
    v2 = 2000 if monotonic else 500              # monotonic future volume unless asked
    RF.write_instrument(day, "NIFTY_FUT", 61093, [
        {"ts_recv_ns": 1 * NS, "ltt": 1, "ltp": 100.0, "volume": 1000},
        {"ts_recv_ns": int(1 * NS + span_s * NS), "ltt": 1 + int(span_s),
         "ltp": 100.5, "volume": v2}])
    ev = [{"ts_ns": 0, "kind": "SESSION", "detail": "start", "value_num": None, "security_id": 0},
          {"ts_ns": int(span_s * NS), "kind": "SESSION", "detail": "end (record_end)",
           "value_num": None, "security_id": 0}]
    # Stamp gaps at a genuine MID-SESSION time (11:15 IST, post-market-open) so the
    # 2026-07-16 market-open clock credits them in full — these tests exercise real
    # in-session gaps. Pre-open / straddle cases live in test_preopen_gap_verdict.py.
    gap_end = V._market_open_ns(day) + 2 * 3600 * NS
    for sym, dur in gaps:
        ev.append({"ts_ns": gap_end, "kind": "GAP", "detail": f"{sym} gap",
                   "value_num": dur, "security_id": 0})
    for _ in range(reconnects):
        ev.append({"ts_ns": 1 * NS, "kind": "RECONNECT", "detail": "", "value_num": None,
                   "security_id": 0})
    for _ in range(disconnects):
        ev.append({"ts_ns": 1 * NS, "kind": "DISCONNECT", "detail": "", "value_num": None,
                   "security_id": 0})
    RF.write_events(day, ev)
    (day / "manifest.json").write_text(json.dumps({"date": day.name, "instruments": [
        {"symbol": "NIFTY_FUT", "security_id": 61093, "exchange_segment": "NSE_FNO",
         "kind": "future", "gap_check": True, "expiry": ""}]}))
    return day


def _v(day) -> dict:
    return V.verify_session(day)


def test_clean_day_with_cadence_gaps_passes(tmp_path):
    """60+ index 3-8s quiets + a thin-future/spot gap — none liquid>60s -> PASS.
    (Under the old 'any gap -> PARTIAL' rule this day was PARTIAL.)"""
    gaps = ([("NIFTY_FUT", 4.0)] * 30 + [("SENSEX_SPOT", 5.0)] * 20
            + [("FINNIFTY_FUT", 8.0)] * 10)
    r = _v(_day(tmp_path, gaps=gaps))
    assert r["status"] == "PASS", r["problems"]
    assert r["checks"]["events"]["gap_count_raw"] == 60      # all still logged


def test_liquid_outage_gap_partials(tmp_path):
    r = _v(_day(tmp_path, gaps=[("NIFTY_FUT", 4.0)] * 10 + [("BANKNIFTY_FUT", 445.0)]))
    assert r["status"] == "PARTIAL"
    assert any("liquid feed gap 445" in p for p in r["problems"])


def test_thin_future_or_spot_big_gap_not_verdict(tmp_path):
    """A 300s gap on a THIN future + a 120s spot gap are not verdict drivers -> PASS."""
    r = _v(_day(tmp_path, gaps=[("FINNIFTY_FUT", 300.0), ("SENSEX_SPOT", 120.0)]))
    assert r["status"] == "PASS", r["problems"]


def test_open_ended_gap_excluded(tmp_path):
    """A 600s OPEN-ENDED gap on a liquid instrument is an EOD artifact -> excluded."""
    r = _v(_day(tmp_path, gaps=[("NIFTY_FUT open-ended", 600.0)]))
    assert r["status"] == "PASS", r["problems"]
    assert r["checks"]["events"]["liquid_max_gap_s"] == 0.0


def test_reconnect_partials(tmp_path):
    r = _v(_day(tmp_path, reconnects=1))
    assert r["status"] == "PARTIAL"
    assert any("reconnect" in p for p in r["problems"])


def test_low_coverage_partials(tmp_path):
    r = _v(_day(tmp_path, span_s=10_000))       # ~43% coverage
    assert r["status"] == "PARTIAL"
    assert any("coverage" in p and "95" in p for p in r["problems"])
