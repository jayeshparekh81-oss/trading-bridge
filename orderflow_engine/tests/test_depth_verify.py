"""Tests for depth session verification (Module R1)."""

from __future__ import annotations

import pyarrow as pa
import pyarrow.parquet as pq

from recorder.depth_schema import DEPTH_SCHEMA, SIDE_ASK, SIDE_BID, normalize_depth_row
from recorder.depth_verify import EXPECTED_SESSION_S, verify_depth
from recorder.schema import EVENT_SCHEMA, normalize_event_row


def _write_depth(depth_dir, symbol, sid, rows):
    depth_dir.mkdir(parents=True, exist_ok=True)
    tbl = pa.Table.from_pylist([normalize_depth_row(r) for r in rows], schema=DEPTH_SCHEMA)
    pq.write_table(tbl, str(depth_dir / f"{symbol}_{sid}.parquet"))


def _row(ts, side, sid=1):
    return {"ts_recv_ns": ts, "side": side, "security_id": sid}


def test_fail_when_no_depth_dir(tmp_path):
    r = verify_depth(tmp_path / "2026-07-13")
    assert r["status"] == "FAIL"


def test_pass_full_both_sides(tmp_path):
    day = tmp_path / "2026-07-13"
    span = int(EXPECTED_SESSION_S * 1e9)
    rows = [_row(0, SIDE_BID), _row(span, SIDE_ASK)]
    _write_depth(day / "depth", "NIFTY_FUT", 1, rows)
    r = verify_depth(day)
    assert r["status"] == "PASS"
    inst = r["instruments"][0]
    assert inst["bid_packets"] == 1 and inst["ask_packets"] == 1
    assert r["coverage"]["coverage_pct"] >= 99.0


def test_partial_when_one_side_missing(tmp_path):
    day = tmp_path / "2026-07-13"
    _write_depth(day / "depth", "X", 2, [_row(0, SIDE_BID), _row(10, SIDE_BID)])
    r = verify_depth(day)
    assert r["status"] == "PARTIAL"
    assert any("one side missing" in p for p in r["problems"])


def test_partial_when_instrument_empty(tmp_path):
    day = tmp_path / "2026-07-13"
    _write_depth(day / "depth", "E", 3, [])
    r = verify_depth(day)
    assert r["status"] == "PARTIAL"
    assert any("no rows" in p for p in r["problems"])


def test_gap_events_make_partial(tmp_path):
    day = tmp_path / "2026-07-13"
    span = int(EXPECTED_SESSION_S * 1e9)
    _write_depth(day / "depth", "G", 4, [_row(0, SIDE_BID), _row(span, SIDE_ASK)])
    ev = [normalize_event_row({"ts_ns": 5, "kind": "GAP", "detail": "g", "value_num": 4.0})]
    pq.write_table(pa.Table.from_pylist(ev, schema=EVENT_SCHEMA),
                   str(day / "depth" / "events.parquet"))
    r = verify_depth(day)
    assert r["status"] == "PARTIAL"
    assert r["checks"]["events"]["gap_count"] == 1
