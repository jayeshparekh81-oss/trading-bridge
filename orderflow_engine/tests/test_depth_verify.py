"""Depth session verification (Module R1) — gap-verdict recalibration (2026-07-16).

The old "any GAP -> PARTIAL" made every clean depth day PARTIAL. The verdict is now
liquid-scoped + outage-based + market-hours-clipped, mirroring R0's verify_session.
Both directions are locked here: cadence -> PASS, a REAL in-hours liquid outage -> PARTIAL,
pre-open + post-close excluded, a straddle counts only its in-hours portion.
"""

from __future__ import annotations

import pyarrow as pa
import pyarrow.parquet as pq

import recorder.depth_verify as DV
from recorder.depth_schema import DEPTH_SCHEMA, SIDE_ASK, SIDE_BID, normalize_depth_row
from recorder.depth_verify import EXPECTED_SESSION_S, verify_depth
from recorder.schema import EVENT_SCHEMA, normalize_event_row

DAY = "2026-07-15"
NS = DV.NS_PER_S
MO, MC = DV._market_window_ns(DAY)          # market open/close epoch-ns for 2026-07-15


def _write_depth(depth_dir, sym, sid, rows):
    depth_dir.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist([normalize_depth_row(r) for r in rows], schema=DEPTH_SCHEMA),
                   str(depth_dir / f"{sym}_{sid}.parquet"))


def _both_sides(sid, first_ns, last_ns):
    return [{"ts_recv_ns": first_ns, "side": SIDE_BID, "security_id": sid},
            {"ts_recv_ns": last_ns, "side": SIDE_ASK, "security_id": sid}]


def _day(tmp_path, *, gaps=(), reconnects=0, disconnects=0, liquid_span=True, extra=()):
    """gaps: (sym, dur_s, end_ns). Liquid futures span ~full market hours unless asked not to."""
    day = tmp_path / DAY
    dd = day / "depth"
    first, last = (MO - 8 * 60 * NS, MC + 5 * 60 * NS) if liquid_span else (MO, MO + 60 * NS)
    _write_depth(dd, "NIFTY_FUT", 61093, _both_sides(61093, first, last))
    _write_depth(dd, "BANKNIFTY_FUT", 61088, _both_sides(61088, first, last))
    for sym, sid, f, l in extra:
        _write_depth(dd, sym, sid, _both_sides(sid, f, l))
    ev = [normalize_event_row({"ts_ns": MO - 8 * 60 * NS, "kind": "SESSION",
                               "detail": "start", "value_num": None}),
          normalize_event_row({"ts_ns": MC + 5 * 60 * NS, "kind": "SESSION",
                               "detail": "end", "value_num": None})]
    for sym, dur, end in gaps:
        ev.append(normalize_event_row({"ts_ns": int(end), "kind": "GAP",
                                       "detail": f"{sym} gap", "value_num": float(dur)}))
    for _ in range(reconnects):
        ev.append(normalize_event_row({"ts_ns": MO, "kind": "RECONNECT", "detail": "", "value_num": None}))
    for _ in range(disconnects):
        ev.append(normalize_event_row({"ts_ns": MO, "kind": "DISCONNECT", "detail": "", "value_num": None}))
    pq.write_table(pa.Table.from_pylist(ev, schema=EVENT_SCHEMA), str(dd / "events.parquet"))
    return day


# ---- structural / basic --------------------------------------------------------

def test_fail_when_no_depth_dir(tmp_path):
    assert verify_depth(tmp_path / DAY)["status"] == "FAIL"


def test_clean_day_passes(tmp_path):
    r = verify_depth(_day(tmp_path))
    assert r["status"] == "PASS", r["problems"]
    assert r["coverage"]["coverage_pct"] >= 99.0
    assert r["coverage"]["basis"] == "liquid"


# ---- gap verdict: cadence PASS, real outage PARTIAL ----------------------------

def test_cadence_gaps_pass(tmp_path):
    """Many small mid-session liquid gaps (5s) + a big NON-liquid gap -> PASS.
    Under the OLD 'any gap -> PARTIAL' this was PARTIAL."""
    mid = MO + 2 * 3600 * NS
    gaps = ([("NIFTY_FUT", 5.0, mid + i * NS) for i in range(30)]
            + [("HDFCBANK", 400.0, mid)])          # non-liquid: logged, not verdict-driving
    r = verify_depth(_day(tmp_path, gaps=gaps))
    assert r["status"] == "PASS", r["problems"]
    assert r["checks"]["events"]["liquid_max_gap_s"] <= 5.0


def test_real_liquid_outage_partials(tmp_path):
    """A genuine in-hours 300s NIFTY_FUT gap MUST still PARTIAL (the outage proof)."""
    r = verify_depth(_day(tmp_path, gaps=[("NIFTY_FUT", 300.0, MO + 2 * 3600 * NS)]))
    assert r["status"] == "PARTIAL"
    assert any("liquid depth outage 300" in p for p in r["problems"]), r["problems"]
    assert r["checks"]["events"]["liquid_max_gap_s"] == 300.0


def test_pre_open_gap_excluded(tmp_path):
    """A 200s NIFTY_FUT gap ending at 09:15 (connect -> first snapshot) -> 0 -> PASS."""
    r = verify_depth(_day(tmp_path, gaps=[("NIFTY_FUT", 200.0, MO)]))
    assert r["status"] == "PASS", r["problems"]
    assert r["checks"]["events"]["liquid_max_gap_s"] == 0.0
    assert r["checks"]["events"]["liquid_max_gap_raw_s"] == 200.0   # raw kept for observability


def test_post_close_gap_excluded(tmp_path):
    """A 200s NIFTY_FUT gap starting at 15:30 (feed wind-down) -> 0 -> PASS.
    This is the real 07-15/07-16 case (gap resolved ~15:33)."""
    r = verify_depth(_day(tmp_path, gaps=[("NIFTY_FUT", 200.0, MC + 200 * NS)]))  # start=MC
    assert r["status"] == "PASS", r["problems"]
    assert r["checks"]["events"]["liquid_max_gap_s"] == 0.0


def test_straddle_open_counts_post_open_only(tmp_path):
    """Gap 09:13:20 -> 09:18:20 (dur 300, ends MO+200): only the 200s after open counts."""
    r = verify_depth(_day(tmp_path, gaps=[("NIFTY_FUT", 300.0, MO + 200 * NS)]))
    assert r["checks"]["events"]["liquid_max_gap_s"] == 200.0        # not 300
    assert r["status"] == "PARTIAL"                                  # 200 > 60


def test_straddle_open_below_outage_passes(tmp_path):
    """A straddle whose POST-open portion is < 60s -> PASS (proves the pre-open clip)."""
    r = verify_depth(_day(tmp_path, gaps=[("NIFTY_FUT", 300.0, MO + 30 * NS)]))  # 30s post-open
    assert r["checks"]["events"]["liquid_max_gap_s"] == 30.0
    assert r["status"] == "PASS", r["problems"]


def test_non_liquid_gap_not_verdict(tmp_path):
    """A 500s in-hours gap on an EQUITY is logged, not verdict-driving -> PASS."""
    r = verify_depth(_day(tmp_path, gaps=[("HDFCBANK", 500.0, MO + 3 * 3600 * NS)],
                          extra=[("HDFCBANK", 1330, MO, MO + 3600 * NS)]))
    assert r["status"] == "PASS", r["problems"]


# ---- other real drivers still PARTIAL ------------------------------------------

def test_reconnect_partials(tmp_path):
    r = verify_depth(_day(tmp_path, reconnects=1))
    assert r["status"] == "PARTIAL"
    assert any("reconnect" in p for p in r["problems"])


def test_liquid_one_side_missing_partials(tmp_path):
    """A LIQUID instrument that only ever sends bid (or ask) -> PARTIAL."""
    day = _day(tmp_path)
    bid_only = [{"ts_recv_ns": MO, "side": SIDE_BID, "security_id": 61093},
                {"ts_recv_ns": MC, "side": SIDE_BID, "security_id": 61093}]
    _write_depth(day / "depth", "NIFTY_FUT", 61093, bid_only)   # overwrite with bid-only
    r = verify_depth(day)
    assert r["status"] == "PARTIAL"
    assert any("one side missing" in p for p in r["problems"])


def test_non_liquid_empty_not_verdict(tmp_path):
    """A non-liquid instrument with 0 rows is logged, not a PARTIAL."""
    day = _day(tmp_path)
    _write_depth(day / "depth", "SBIN", 3045, [])              # empty equity
    r = verify_depth(day)
    assert r["status"] == "PASS", r["problems"]
    assert any(i["file"].startswith("SBIN") and "no rows" in " ".join(i["problems"])
               for i in r["instruments"])                       # logged on the instrument


def test_low_liquid_coverage_partials(tmp_path):
    r = verify_depth(_day(tmp_path, liquid_span=False))          # liquid span ~60s
    assert r["status"] == "PARTIAL"
    assert any("coverage" in p for p in r["problems"])
