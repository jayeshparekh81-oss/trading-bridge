"""Pre-open gap exclusion — market-open clock for liquid futures (2026-07-16 fix).

Index FUTURES do not trade in the 09:07–09:15 pre-open window, so the watchdog
logs a ~433s "gap" from connect to the 09:15:00 opening tick every single day.
That is a no-trade artifact, NOT a feed hole — but the recalibrated verdict was
counting it as a >60s liquid outage and would PARTIAL every clean day on it
(masked 07-13/14/15 by real disk/teardown problems).

Fix: liquid-future gaps are clocked from MARKET OPEN (09:15:00 IST) — a gap is
credited only its POST-open portion, symmetric to the session-end open-ended
exclusion. Both directions are asserted here:
  (a) a pure pre-open 433s liquid gap        -> credited 0   -> must NOT PARTIAL
  (b) a real mid-session 120s liquid gap     -> credited 120 -> must STILL PARTIAL
  (c) a gap straddling 09:15 (09:10->09:20)  -> credited 300 (only the post-open 5 min)
"""

from __future__ import annotations

import json
from pathlib import Path

import verify_session as V
from tests.replayer import fixtures as RF

NS = V.NS_PER_S
DAY = "2026-07-16"


def _day(tmp_path, gap_events):
    """gap_events: list of (sym, dur_s, end_offset_s_from_market_open)."""
    day = tmp_path / DAY
    mo = V._market_open_ns(day)          # 09:15:00 IST epoch-ns for 2026-07-16
    span = V.EXPECTED_SESSION_S
    RF.write_instrument(day, "NIFTY_FUT", 61093, [
        {"ts_recv_ns": mo, "ltt": 1, "ltp": 100.0, "volume": 1000},
        {"ts_recv_ns": int(mo + span * NS), "ltt": 1 + span, "ltp": 100.5, "volume": 2000}])
    ev = [{"ts_ns": mo - 8 * 60 * NS, "kind": "SESSION", "detail": "start",
           "value_num": None, "security_id": 0},
          {"ts_ns": int(mo + span * NS), "kind": "SESSION", "detail": "end (record_end)",
           "value_num": None, "security_id": 0}]
    for sym, dur, end_off in gap_events:
        ev.append({"ts_ns": int(mo + end_off * NS), "kind": "GAP",
                   "detail": f"{sym} gap", "value_num": float(dur), "security_id": 0})
    RF.write_events(day, ev)
    (day / "manifest.json").write_text(json.dumps({"date": DAY, "instruments": [
        {"symbol": "NIFTY_FUT", "security_id": 61093, "exchange_segment": "NSE_FNO",
         "kind": "future", "gap_check": True, "expiry": ""}]}))
    return day


# ---- unit level: the clock arithmetic in _verify_events -------------------------

def test_preopen_gap_credited_zero(tmp_path):
    """(a) A 433s gap that ENDS at market open (starts 09:07:47 pre-open) -> 0 credited."""
    day = _day(tmp_path, [("NIFTY_FUT", 433.0, 0.0)])      # end exactly at 09:15:00
    ev = V._verify_events(day)
    assert ev["liquid_max_gap_s"] == 0.0                    # post-open portion
    assert ev["liquid_max_gap_raw_s"] == 433.0             # raw kept for observability


def test_midsession_gap_credited_full(tmp_path):
    """(b) A 120s gap wholly after open (ends 2h into the session) -> full 120s."""
    day = _day(tmp_path, [("NIFTY_FUT", 120.0, 2 * 3600.0)])
    ev = V._verify_events(day)
    assert ev["liquid_max_gap_s"] == 120.0


def test_straddling_gap_credits_only_post_open(tmp_path):
    """(c) A gap 09:10->09:20 (dur 600s, ends +300s) -> only the post-open 300s counts."""
    day = _day(tmp_path, [("NIFTY_FUT", 600.0, 300.0)])    # ends 5 min after open
    ev = V._verify_events(day)
    assert ev["liquid_max_gap_s"] == 300.0
    assert ev["liquid_max_gap_raw_s"] == 600.0


# ---- verdict level: end-to-end PASS / PARTIAL -----------------------------------

def test_preopen_only_day_passes(tmp_path):
    """(a, verdict) A clean day whose ONLY liquid >60s gaps are pre-open -> PASS.
    This is the 07-16 case that previously false-PARTIALed."""
    r = V.verify_session(_day(tmp_path, [
        ("NIFTY_FUT", 433.0, 0.0), ("BANKNIFTY_FUT", 433.0, 0.0)]))
    assert r["status"] == "PASS", r["problems"]
    assert r["checks"]["events"]["liquid_max_gap_s"] == 0.0
    assert r["checks"]["events"]["liquid_max_gap_raw_s"] == 433.0   # still recorded


def test_real_midsession_outage_still_partials(tmp_path):
    """(b, verdict) A genuine 120s mid-session liquid gap must STILL PARTIAL —
    the clock must not blunt real outages."""
    r = V.verify_session(_day(tmp_path, [
        ("NIFTY_FUT", 433.0, 0.0),          # pre-open (excluded)
        ("BANKNIFTY_FUT", 120.0, 3 * 3600.0)]))  # real mid-session hole
    assert r["status"] == "PARTIAL"
    assert any("liquid feed gap 120" in p for p in r["problems"]), r["problems"]


def test_straddling_gap_over_threshold_partials(tmp_path):
    """(c, verdict) A straddling gap whose POST-open portion exceeds 60s -> PARTIAL
    (only the real, in-session minutes drive it)."""
    r = V.verify_session(_day(tmp_path, [("NIFTY_FUT", 600.0, 300.0)]))  # 300s post-open
    assert r["status"] == "PARTIAL"
    assert any("liquid feed gap 300" in p for p in r["problems"]), r["problems"]
