"""Intraday time-to-expiry + 0-DTE IV-sanity flag (2026-07-15).

T now measures to the expiry-day 15:30 IST close so 0-DTE greeks decay through the
session instead of the old flat integer-day T; a floor keeps the final minutes finite;
past expiry -> None. Rows with an implausibly-low backed-out IV are flagged iv_suspect.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from chain.config import ChainConfig
from chain.engine import ChainEngine, _time_to_expiry_years
from tests.chain import fixtures as F

NS = 1_000_000_000
IST = timezone(timedelta(hours=5, minutes=30))
FLOOR, DC = 300.0, 365


def _ts(y, mo, d, h, mi):
    return int(datetime(y, mo, d, h, mi, tzinfo=IST).timestamp() * NS)


def test_T_decays_intraday_on_expiry_day():
    open_T = _time_to_expiry_years("2026-07-14", _ts(2026, 7, 14, 9, 15), FLOOR, DC)
    noon_T = _time_to_expiry_years("2026-07-14", _ts(2026, 7, 14, 12, 0), FLOOR, DC)
    late_T = _time_to_expiry_years("2026-07-14", _ts(2026, 7, 14, 15, 0), FLOOR, DC)
    assert open_T > noon_T > late_T > 0                  # continuous intraday decay


def test_T_floor_bounds_final_minutes():
    # 1 min before close (< 300s) is floored, not driven to ~0
    t = _time_to_expiry_years("2026-07-14", _ts(2026, 7, 14, 15, 29), FLOOR, DC)
    assert t == FLOOR / (DC * 86400.0)


def test_T_none_at_and_after_expiry():
    assert _time_to_expiry_years("2026-07-14", _ts(2026, 7, 14, 15, 30), FLOOR, DC) is None
    assert _time_to_expiry_years("2026-07-14", _ts(2026, 7, 14, 15, 31), FLOOR, DC) is None
    assert _time_to_expiry_years("2026-07-13", _ts(2026, 7, 14, 9, 15), FLOOR, DC) is None


def test_multiday_T_barely_changes_intraday():
    """6-DTE: open vs close T differ only by the intraday fraction (no regression)."""
    o = _time_to_expiry_years("2026-07-21", _ts(2026, 7, 15, 9, 15), FLOOR, DC)
    c = _time_to_expiry_years("2026-07-21", _ts(2026, 7, 15, 15, 0), FLOOR, DC)
    assert 0.015 < c < o < 0.020 and (o - c) < 0.001


META = {13: {"kind": "spot", "index": "NIFTY", "right": None, "strike": None, "expiry": ""},
        51355: {"kind": "option", "index": "NIFTY", "right": "CE", "strike": 100,
                "expiry": "2026-07-14"}}


def _eng(iv_min=0.03):
    cfg = ChainConfig({"chain": {"snapshot_interval_s": 0, "iv_sanity_min": iv_min}})
    return ChainEngine(cfg, META, date(2026, 7, 14))


def test_iv_suspect_fires_below_the_configured_threshold():
    """Flag logic: iv < iv_sanity_min -> iv_suspect. Same option, two thresholds."""
    ts = _ts(2026, 7, 14, 10, 0)

    def _iv_row(iv_min):
        eng = _eng(iv_min=iv_min)
        eng.on_packet(F.spot_tick(ts, 13, 100.0), ts)
        eng.on_packet(F.opt_tick(ts, 51355, oi=1000, volume=10, ltp=0.5), ts)
        return [r for r in eng.rows if r["right"] == "CE"][-1]

    hi = _iv_row(0.03)                      # a real IV (~0.1-0.3) is ABOVE 3%
    assert hi["iv"] is not None and hi["iv"] >= 0.03 and hi["iv_suspect"] is False
    lo = _iv_row(0.90)                      # same option, threshold above its IV -> flagged
    assert lo["iv"] < 0.90 and lo["iv_suspect"] is True
