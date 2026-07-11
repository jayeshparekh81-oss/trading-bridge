"""IV/Greeks use the contemporaneous spot from the merged stream + staleness flag."""

from __future__ import annotations

from datetime import date

from chain.config import ChainConfig
from chain.engine import ChainEngine
from tests.chain import fixtures as F

NS = 1_000_000_000
META = {
    13: {"kind": "spot", "index": "NIFTY", "right": None, "strike": None, "expiry": ""},
    51355: {"kind": "option", "index": "NIFTY", "right": "CE", "strike": 100,
            "expiry": "2026-07-20"},
}


def _engine():
    cfg = ChainConfig({"chain": {"snapshot_interval_s": 0, "spot_staleness_s": 5}})
    return ChainEngine(cfg, META, date(2026, 7, 13))


def test_iv_computed_from_contemporaneous_spot():
    eng = _engine()
    eng.on_packet(F.spot_tick(0, 13, 100.0), 0)                    # spot 100
    eng.on_packet(F.opt_tick(0, 51355, oi=1000, volume=10, ltp=7.0), 0)
    ce = [r for r in eng.rows if r["right"] == "CE"]
    assert ce and ce[-1]["spot"] == 100.0
    assert ce[-1]["spot_stale"] is False
    assert ce[-1]["iv"] is not None and ce[-1]["delta"] is not None


def test_stale_spot_flagged_but_last_known_used():
    eng = _engine()
    eng.on_packet(F.spot_tick(0, 13, 100.0), 0)
    eng.on_packet(F.opt_tick(0, 51355, oi=1000, volume=10, ltp=7.0), 0)
    # 10s later, a new option tick but NO new spot -> stale (last-known still used)
    eng.on_packet(F.opt_tick(10 * NS, 51355, oi=1000, volume=10, ltp=7.0), 10 * NS)
    ce = [r for r in eng.rows if r["right"] == "CE"]
    assert ce[-1]["spot"] == 100.0                # last-known spot still applied
    assert ce[-1]["spot_stale"] is True


def test_no_spot_yields_no_iv():
    eng = _engine()
    # option tick with no spot ever seen -> spot None, iv None, stale True
    eng.on_packet(F.opt_tick(0, 51355, oi=1000, volume=10, ltp=7.0), 0)
    ce = [r for r in eng.rows if r["right"] == "CE"]
    assert ce[-1]["spot"] is None and ce[-1]["iv"] is None
    assert ce[-1]["spot_stale"] is True
