"""Bar-size sweep tests — multi-tape isolation, per-fire roundtrip, de-dup golden,
hard-stop clock guard, resume-from-state. Fixture replays only (tiny), no real days."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from research.barsize_sweep import (
    capture_day_multi, dedup_sequential, may_start_unit, perfire_records, plan_units,
    result_path, stub_path,
)
from research.delta_vwap_evaluator import capture_day
from tape.config import HERE as ENGINE_ROOT
from tests.replayer import fixtures as RF

IST = timezone(timedelta(hours=5, minutes=30))
NS = 1_000_000_000
SID = 61093
T0 = 1000 * NS
DAY = "2026-06-01"


def _tick(ts, vol, ltp):
    return {"ts_recv_ns": ts, "volume": vol, "ltp": ltp, "ltq": 0,
            "bid_price_1": ltp - 0.05, "ask_price_1": ltp + 0.05, "ltt": ts // NS}


def _write_day(root: Path):
    d = root / "data" / DAY
    ticks = [_tick(T0, 1000, 100.00)]
    px = [100.05, 100.10, 100.00, 100.20, 100.10, 100.30, 100.25, 100.40,
          100.35, 100.50, 100.45, 100.60]
    for i, p in enumerate(px):                       # 12 trades of 50 -> bars close at
        ticks.append(_tick(T0 + (360 + i) * NS, 1000 + 50 * (i + 1), p))   # sizes 2,3,4...
    RF.write_instrument(d, "NIFTY_FUT", SID, ticks)
    RF.write_events(d, [{"ts_ns": 0, "kind": "SESSION", "detail": "start", "value_num": None}])
    (d / "manifest.json").write_text(json.dumps({"instruments": [
        {"symbol": "NIFTY_FUT", "security_id": SID, "kind": "future",
         "exchange_segment": "NSE_FNO", "gap_check": True, "expiry": ""}]}))
    return d


def _cfg_for(root: Path, size: int) -> Path:
    cfg = yaml.safe_load((ENGINE_ROOT / "tape_config.yaml").read_text())
    cfg["tape"]["bars"]["tick_bar_size"] = size
    p = root / f"cfg_s{size}.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return p


# ---------- multi-tape isolation: byte-match vs single-size runs ----------
def test_multi_tape_isolation_matches_single_runs(tmp_path):
    _write_day(tmp_path)
    multi = capture_day_multi(DAY, [2, 3], root=tmp_path)
    for size in (2, 3):
        single = capture_day(DAY, root=tmp_path, instruments=["NIFTY_FUT"],
                             config_path=_cfg_for(tmp_path, size))
        m, s = multi[size], single
        mb = [(b["end_ts_ns"], b["open"], b["close"], b["delta"], b["volume"])
              for b in m.bars.get(SID, [])]
        sb = [(b["end_ts_ns"], b["open"], b["close"], b["delta"], b["volume"])
              for b in s.bars.get(SID, [])]
        assert mb == sb, f"size {size}: bars differ between multi and single capture"
        mc = [(c["ts_ns"], c["side"], c["delta_al"], c["vwap_dist_al"]) for c in m.candidates]
        sc = [(c["ts_ns"], c["side"], c["delta_al"], c["vwap_dist_al"]) for c in s.candidates]
        assert mc == sc, f"size {size}: candidates differ"
    # and the two sizes genuinely differ from each other (no accidental sharing)
    assert len(multi[2].bars[SID]) != len(multi[3].bars[SID])


# ---------- per-fire roundtrip ----------
def test_perfire_records_roundtrip(tmp_path):
    _write_day(tmp_path)
    caps = capture_day_multi(DAY, [2], root=tmp_path)
    fires = perfire_records(caps[2], "NIFTY_FUT", dmed=0.0)
    assert fires, "expected at least one priced rule-fire on the fixture"
    for f in fires:
        assert set(f) == {"entry_ns", "exit_ns", "gross", "net", "cost_r"}
        assert f["exit_ns"] >= f["entry_ns"] and f["gross"] is not None
    # JSON roundtrip preserves everything (the persistence contract)
    assert json.loads(json.dumps(fires)) == fires


# ---------- de-dup golden: hand-built overlapping fires ----------
def test_dedup_sequential_golden():
    F = lambda e, x, g: {"entry_ns": e, "exit_ns": x, "gross": g, "net": g, "cost_r": 0.1}
    fires = [F(100, 500, 1.0),      # kept (first)
             F(200, 300, -1.0),     # overlaps kept #1 -> dropped
             F(500, 700, 0.5),      # entry == prev exit -> kept (>= boundary)
             F(600, 800, -2.0),     # overlaps kept #2 -> dropped
             F(900, 950, 0.25)]     # after -> kept
    kept = dedup_sequential(fires)
    assert [(f["entry_ns"], f["exit_ns"]) for f in kept] == [(100, 500), (500, 700), (900, 950)]
    # order-independence: shuffled input, same result
    kept2 = dedup_sequential(list(reversed(fires)))
    assert kept == kept2


# ---------- hard-stop clock guard ----------
def test_hard_stop_clock_guard():
    def at(h, m):
        return datetime(2026, 7, 24, h, m, tzinfo=IST)
    assert may_start_unit(at(22, 0))[0] is True          # evening: allowed
    assert may_start_unit(at(2, 0))[0] is True           # overnight: allowed
    assert may_start_unit(at(8, 29))[0] is True          # last permitted start window
    ok, why = may_start_unit(at(8, 31))
    assert ok is False and "08:30" in why                # no starts after 08:30
    ok2, why2 = may_start_unit(at(8, 46))
    assert ok2 is False and "08:45" in why2              # hard refuse
    assert may_start_unit(at(12, 0))[0] is False         # market hours: never
    assert may_start_unit(at(16, 1))[0] is True          # post-close: allowed again


# ---------- resume-from-state ----------
def test_resume_from_state(tmp_path):
    days = ["2026-07-15", "2026-07-16"]
    sizes = [200, 300, 400]
    # nothing done -> all units, chronological, batched by width
    u0 = plan_units(days, sizes, 3, tmp_path)
    assert u0 == [("2026-07-15", [200, 300, 400]), ("2026-07-16", [200, 300, 400])]
    # mark 07-15 s200+s300 done -> 07-15 batch shrinks to the pending size only
    result_path(tmp_path, "2026-07-15", 200).write_text("{}")
    result_path(tmp_path, "2026-07-15", 300).write_text("{}")
    u1 = plan_units(days, sizes, 3, tmp_path)
    assert u1 == [("2026-07-15", [400]), ("2026-07-16", [200, 300, 400])]
    # width splits batches
    u2 = plan_units(days, sizes, 2, tmp_path)
    assert u2 == [("2026-07-15", [400]), ("2026-07-16", [200, 300]), ("2026-07-16", [400])]
    # all done -> empty plan
    for d in days:
        for s in sizes:
            result_path(tmp_path, d, s).write_text("{}")
    assert plan_units(days, sizes, 3, tmp_path) == []
