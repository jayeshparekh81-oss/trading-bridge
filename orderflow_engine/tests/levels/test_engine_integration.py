"""LevelsEngine over a replayed day: correctness, determinism, salvaged-day run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from replayer.engine import ReplayEngine
from replayer.source import ReplaySource

from levels.config import LevelsConfig
from levels.engine import LevelsEngine
from tests.replayer import fixtures as RF

HERE = Path(__file__).resolve().parent.parent.parent  # orderflow_engine/


def _snap(ts, vol, ltp, bid, ask, sid=61093):
    return {"ts_recv_ns": ts, "volume": vol, "ltp": ltp, "ltq": 0,
            "bid_price_1": bid, "ask_price_1": ask, "ltt": ts // 1_000_000_000}


def _day(tmp_path) -> Path:
    day = tmp_path / "2026-07-13"
    ns = 1_000_000_000
    rows = [
        _snap(1 * ns, 1000, 100.0, 99.5, 100.5),   # seed
        _snap(2 * ns, 1010, 100.0, 99.5, 100.5),   # +10 @100 -> bin 100
        _snap(3 * ns, 1020, 110.0, 109.5, 110.5),  # +10 @110 -> bin 110
    ]
    RF.write_instrument(day, "NIFTY_FUT", 61093, rows)
    return day


def _cfg():
    return LevelsConfig({"levels": {"volume_profile": {"bin_size": {"index_fut": 5.0}},
                                    "vwap": {"snapshot_every_trades": 1}}})


def _hash(engine) -> str:
    rows = []
    for sid, reg in sorted(engine.registries.items()):
        rows.append(reg.to_rows())
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()


def test_vwap_and_profile_over_replay(tmp_path):
    day = _day(tmp_path)
    eng = LevelsEngine(_cfg(), {61093: "NIFTY_FUT"}, date="2026-07-13")
    ReplayEngine(ReplaySource(day)).drive(eng, speed="max")
    summary = eng.finalize()
    assert summary["counts"]["trades"] == 2                 # two volume advances
    inst = summary["per_instrument"]["NIFTY_FUT"]
    assert inst["vwap"] == 105.0                            # (100*10 + 110*10)/20
    reg = eng.registries[61093]
    types = {l.level_type for l in reg.levels()}
    assert {"VWAP", "POC", "VAH", "VAL"} <= types
    # nearest level to 106 should be VWAP@105
    assert reg.distance_to_nearest(106.0)["level_type"] == "VWAP"


def test_determinism_same_replay_same_levels(tmp_path):
    day = _day(tmp_path)
    e1 = LevelsEngine(_cfg(), {61093: "NIFTY_FUT"}, date="2026-07-13")
    e2 = LevelsEngine(_cfg(), {61093: "NIFTY_FUT"}, date="2026-07-13")
    ReplayEngine(ReplaySource(day)).drive(e1, speed="max"); e1.finalize()
    ReplayEngine(ReplaySource(day)).drive(e2, speed="max"); e2.finalize()
    assert _hash(e1) == _hash(e2)


@pytest.mark.skipif(not (HERE / "data" / "2026-07-09").is_dir(),
                    reason="salvaged 2026-07-09 day not present (gitignored raw data)")
def test_salvaged_day_runs():
    src = ReplaySource(HERE / "data" / "2026-07-09")
    sym = {}
    mf = HERE / "data" / "2026-07-09" / "manifest.json"
    if mf.exists():
        for e in json.loads(mf.read_text()).get("instruments", []):
            sym[int(e["security_id"])] = e["symbol"]
    eng = LevelsEngine(LevelsConfig({}), sym, date="2026-07-09")
    ReplayEngine(src).drive(eng, speed="max")
    summary = eng.finalize()
    assert summary["counts"]["trades"] > 0
    fut = summary["per_instrument"].get("BANKNIFTY_FUT")
    assert fut is not None and fut["vwap"] is not None and fut["poc"] is not None
