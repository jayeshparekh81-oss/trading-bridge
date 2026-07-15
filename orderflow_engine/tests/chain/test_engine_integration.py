"""ChainEngine over a replayed day: correctness, determinism, salvaged-day run."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from replayer.engine import ReplayEngine
from replayer.source import ReplaySource

from chain.config import ChainConfig
from chain.engine import ChainEngine
from chain.symbols import parse_symbol
from tests.replayer import fixtures as RF

HERE = Path(__file__).resolve().parent.parent.parent  # orderflow_engine/
NS = 1_000_000_000
# 2026-07-15 intraday-T fix: greeks measure T to the expiry-day 15:30 IST close, so
# rows use a real 2026-07-13 09:20 base (was ~1970 with bare 1..4*NS -> 56yr T -> no IV).
_IST = timezone(timedelta(hours=5, minutes=30))
BASE = int(datetime(2026, 7, 13, 9, 20, tzinfo=_IST).timestamp() * NS)

META = {
    13: {"kind": "spot", "index": "NIFTY", "right": None, "strike": None, "expiry": ""},
    51355: {"kind": "option", "index": "NIFTY", "right": "CE", "strike": 100, "expiry": "2026-07-20"},
    51356: {"kind": "option", "index": "NIFTY", "right": "PE", "strike": 100, "expiry": "2026-07-20"},
}


def _row(ts, **kw):
    r = {"ts_recv_ns": ts}
    r.update(kw)
    return r


def _day(tmp_path) -> Path:
    day = tmp_path / "2026-07-13"
    RF.write_instrument(day, "NIFTY_SPOT", 13,
                        [_row(BASE + 1 * NS, ltp=100.0), _row(BASE + 3 * NS, ltp=101.0)])
    RF.write_instrument(day, "NIFTY_CE_100", 51355,
                        [_row(BASE + 2 * NS, ltp=7.0, oi=1000, volume=10),
                         _row(BASE + 4 * NS, ltp=7.5, oi=1200, volume=20)])
    RF.write_instrument(day, "NIFTY_PE_100", 51356,
                        [_row(BASE + 2 * NS, ltp=6.5, oi=2000, volume=15),
                         _row(BASE + 4 * NS, ltp=6.0, oi=1800, volume=25)])
    return day


def _cfg():
    return ChainConfig({"chain": {"snapshot_interval_s": 0}})   # per-tick for a short day


def _hash(eng) -> str:
    return hashlib.sha256(json.dumps(eng.rows, sort_keys=True, default=str).encode()).hexdigest()


def test_chain_analytics_over_replay(tmp_path):
    eng = ChainEngine(_cfg(), META, date(2026, 7, 13))
    ReplayEngine(ReplaySource(_day(tmp_path))).drive(eng, speed="max")
    summary = eng.finalize()
    ni = summary["per_index"]["NIFTY"]
    assert ni["strikes"] == 2                       # CE + PE at 100
    assert ni["strikes_with_iv"] == 2               # both got IV (spot present)
    assert ni["pcr_oi"] is not None                 # 1800/1200 = 1.5
    assert ni["pcr_oi"] == pytest.approx(1800 / 1200)
    assert ni["max_pain"] == 100
    assert ni["atm_iv"] is not None
    assert ni["spot_missing"] is False


def test_determinism_same_replay_same_rows(tmp_path):
    day = _day(tmp_path)
    e1 = ChainEngine(_cfg(), META, date(2026, 7, 13))
    e2 = ChainEngine(_cfg(), META, date(2026, 7, 13))
    ReplayEngine(ReplaySource(day)).drive(e1, speed="max"); e1.finalize()
    ReplayEngine(ReplaySource(day)).drive(e2, speed="max"); e2.finalize()
    assert _hash(e1) == _hash(e2)


@pytest.mark.skipif(not (HERE / "data" / "2026-07-09").is_dir(),
                    reason="salvaged 2026-07-09 day not present (gitignored raw data)")
def test_salvaged_day_runs_and_reports_coverage_honestly():
    day = HERE / "data" / "2026-07-09"
    meta = {}
    for e in json.loads((day / "manifest.json").read_text()).get("instruments", []):
        p = parse_symbol(e["symbol"])
        if p.kind != "other":
            meta[int(e["security_id"])] = {"kind": p.kind, "index": p.index,
                                           "right": p.right, "strike": p.strike,
                                           "expiry": e.get("expiry", "")}
    eng = ChainEngine(ChainConfig({}), meta, date(2026, 7, 9))
    ReplayEngine(ReplaySource(day)).drive(eng, speed="max")
    summary = eng.finalize()   # must not raise on a sparse/partial day
    assert summary["counts"]["ticks"] > 0
    assert summary["indices"] >= 1
    # coverage reported honestly: each index states strikes vs strikes_with_iv and
    # whether spot was missing (BANKNIFTY spot is empty on this salvaged day)
    for index, s in summary["per_index"].items():
        assert "strikes" in s and "strikes_with_iv" in s and "spot_missing" in s
        assert s["strikes_with_iv"] <= s["strikes"]
