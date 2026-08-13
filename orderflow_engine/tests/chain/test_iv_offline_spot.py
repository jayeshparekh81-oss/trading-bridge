"""IV/Greeks use the contemporaneous spot from the merged stream + staleness flag."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from chain.config import ChainConfig
from chain.engine import ChainEngine
from tests.chain import fixtures as F

NS = 1_000_000_000
_IST = timezone(timedelta(hours=5, minutes=30))
# 2026-07-15 intraday-T fix: greeks now need a realistic snapshot timestamp (T is
# measured to the expiry-day 15:30 IST close), so tests use a real 07-13 09:20 base.
BASE = int(datetime(2026, 7, 13, 9, 20, tzinfo=_IST).timestamp() * NS)
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
    eng.on_packet(F.spot_tick(BASE, 13, 100.0), BASE)              # spot 100
    eng.on_packet(F.opt_tick(BASE, 51355, oi=1000, volume=10, ltp=7.0), BASE)
    ce = [r for r in eng.rows if r["right"] == "CE"]
    assert ce and ce[-1]["spot"] == 100.0
    assert ce[-1]["spot_stale"] is False
    assert ce[-1]["iv"] is not None and ce[-1]["delta"] is not None


def test_stale_spot_flagged_but_last_known_used():
    eng = _engine()
    eng.on_packet(F.spot_tick(BASE, 13, 100.0), BASE)
    eng.on_packet(F.opt_tick(BASE, 51355, oi=1000, volume=10, ltp=7.0), BASE)
    # 10s later, a new option tick but NO new spot -> stale (last-known still used)
    eng.on_packet(F.opt_tick(BASE + 10 * NS, 51355, oi=1000, volume=10, ltp=7.0),
                  BASE + 10 * NS)
    ce = [r for r in eng.rows if r["right"] == "CE"]
    assert ce[-1]["spot"] == 100.0                # last-known spot still applied
    assert ce[-1]["spot_stale"] is True


def test_no_spot_yields_no_iv():
    eng = _engine()
    # option tick with no spot ever seen -> spot None, iv None, stale True
    eng.on_packet(F.opt_tick(BASE, 51355, oi=1000, volume=10, ltp=7.0), BASE)
    ce = [r for r in eng.rows if r["right"] == "CE"]
    assert ce[-1]["spot"] is None and ce[-1]["iv"] is None
    assert ce[-1]["spot_stale"] is True


def _proxy_engine(mode="future_fallback"):
    cfg = ChainConfig({"chain": {"snapshot_interval_s": 0, "spot_staleness_s": 5,
                                 "spot_proxy": mode}})
    meta = dict(META)
    meta[61093] = {"kind": "future", "index": "NIFTY", "right": None, "strike": None,
                   "expiry": ""}
    return ChainEngine(cfg, meta, date(2026, 7, 13))


def test_future_proxy_used_when_spot_missing():
    """2026-07-13 finding: IDX_I spots delivered zero packets. With
    spot_proxy=future_fallback the FUTURE price stands in for IV/greeks — marked
    in the summary (spot_source=future_proxy), spot_missing stays True, basis
    stays None (never trivially fut-vs-itself)."""
    eng = _proxy_engine()
    eng.on_packet(F.spot_tick(BASE, 61093, 100.0), BASE)      # FUTURE ticks (100)
    eng.on_packet(F.opt_tick(BASE, 51355, oi=1000, volume=10, ltp=7.0), BASE)
    s = eng.finalize()["per_index"]["NIFTY"]
    assert s["spot_source"] == "future_proxy"
    assert s["spot_missing"] is True                           # real spot still absent
    assert s["spot"] == 100.0                                  # proxy value
    assert s["strikes_with_iv"] == 1 and s["atm_iv"] is not None
    assert s["basis"] is None and s["annualized_basis"] is None
    ce = [r for r in eng.rows if r["right"] == "CE"]
    assert ce[-1]["iv"] is not None and ce[-1]["spot"] == 100.0


def test_strict_mode_regression_no_proxy():
    eng = _proxy_engine(mode="strict")
    eng.on_packet(F.spot_tick(BASE, 61093, 100.0), BASE)      # future ticks
    eng.on_packet(F.opt_tick(BASE, 51355, oi=1000, volume=10, ltp=7.0), BASE)
    s = eng.finalize()["per_index"]["NIFTY"]
    assert s["spot_source"] == "none" and s["spot"] is None
    assert s["strikes_with_iv"] == 0 and s["atm_iv"] is None   # old behavior


def test_real_spot_wins_over_proxy():
    eng = _proxy_engine()
    eng.on_packet(F.spot_tick(BASE, 61093, 100.0), BASE)      # future
    eng.on_packet(F.spot_tick(BASE + NS, 13, 99.5), BASE + NS)   # REAL spot ticks too
    eng.on_packet(F.opt_tick(BASE + NS, 51355, oi=1000, volume=10, ltp=7.0), BASE + NS)
    s = eng.finalize()["per_index"]["NIFTY"]
    assert s["spot_source"] == "spot" and s["spot"] == 99.5
    assert s["spot_missing"] is False
    assert s["basis"] == 0.5                                   # fut 100 - spot 99.5
