"""Full replay through the tape engine: correctness, determinism, salvaged-day run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from replayer.engine import ReplayEngine
from replayer.source import ReplaySource

from tape.config import TapeConfig
from tape.engine import TapeEngine
from tests.replayer import fixtures as RF

HERE = Path(__file__).resolve().parent.parent.parent  # orderflow_engine/


def _snap(ts, vol, ltp, bid, ask, sid):
    return {"ts_recv_ns": ts, "volume": vol, "ltp": ltp, "ltq": 0,
            "bid_price_1": bid, "ask_price_1": ask, "ltt": ts // 1_000_000_000}


def _build_day(tmp_path) -> Path:
    day = tmp_path / "2026-07-13"
    ns = 1_000_000_000
    rows = [
        _snap(1 * ns, 1000, 100.0, 99.5, 100.5, 61093),   # seed
        _snap(2 * ns, 1010, 100.5, 100.0, 100.5, 61093),  # +10 BUY
        _snap(3 * ns, 1030, 100.0, 100.0, 100.5, 61093),  # +20 SELL
        _snap(4 * ns, 1035, 100.5, 100.0, 100.5, 61093),  # +5  BUY
        _snap(5 * ns, 1055, 101.0, 100.5, 101.0, 61093),  # +20 BUY
    ]
    RF.write_instrument(day, "NIFTY_FUT", 61093, rows)
    RF.write_events(day, [{"ts_ns": 0, "kind": "SESSION", "detail": "start", "value_num": None}])
    return day


def _cfg():
    return TapeConfig({"bars": {"tick_bar_size": 2}})


def _hash(engine: TapeEngine) -> str:
    payload = json.dumps({"bars": engine.bar_rows, "events": engine.event_rows},
                         sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def test_engine_builds_bars_and_cvd(tmp_path):
    day = _build_day(tmp_path)
    eng = TapeEngine(_cfg(), {61093: "NIFTY_FUT"})
    ReplayEngine(ReplaySource(day)).drive(eng, speed="max")
    summary = eng.finalize()
    assert summary["counts"]["trades"] == 4              # 4 volume advances after seed
    assert summary["totals"]["bars"] >= 2                # tick_bar_size=2 -> >=2 bars
    # CVD: +10 -10... wait buy10, sell20, buy5, buy20 -> 10-20+5+20 = +15
    assert summary["per_instrument"]["NIFTY_FUT"]["cvd_final"] == 15
    # every bar row carries the full schema
    for r in eng.bar_rows:
        assert r["symbol"] == "NIFTY_FUT" and r["trade_count"] >= 1
        assert "cvd_running" in r and "velocity_ratio" in r


def test_determinism_same_replay_same_hash(tmp_path):
    day = _build_day(tmp_path)
    e1 = TapeEngine(_cfg(), {61093: "NIFTY_FUT"})
    e2 = TapeEngine(_cfg(), {61093: "NIFTY_FUT"})
    ReplayEngine(ReplaySource(day)).drive(e1, speed="max"); e1.finalize()
    ReplayEngine(ReplaySource(day)).drive(e2, speed="max"); e2.finalize()
    assert _hash(e1) == _hash(e2)


def test_bigprint_inert_by_default(tmp_path):
    day = _build_day(tmp_path)
    eng = TapeEngine(TapeConfig({"bars": {"tick_bar_size": 2}}), {61093: "NIFTY_FUT"})
    ReplayEngine(ReplaySource(day)).drive(eng, speed="max"); eng.finalize()
    assert eng.summary()["totals"]["big_prints"] == 0    # inert until calibrated


def test_bigprint_fires_when_calibrated(tmp_path):
    day = _build_day(tmp_path)
    cfg = TapeConfig({"bars": {"tick_bar_size": 2},
                      "bigprint": {"notional_threshold": {"index_fut": 1000}}})
    eng = TapeEngine(cfg, {61093: "NIFTY_FUT"})
    ReplayEngine(ReplaySource(day)).drive(eng, speed="max"); eng.finalize()
    # trades are ~100 px * 5-20 size = 500-2020 notional; some exceed 1000
    assert eng.summary()["totals"]["big_prints"] >= 1


@pytest.mark.skipif(not (HERE / "data" / "2026-07-09").is_dir(),
                    reason="salvaged 2026-07-09 day not present (gitignored raw data)")
def test_salvaged_2026_07_09_day_runs():
    src = ReplaySource(HERE / "data" / "2026-07-09")
    sym = {}
    mf = HERE / "data" / "2026-07-09" / "manifest.json"
    if mf.exists():
        for e in json.loads(mf.read_text()).get("instruments", []):
            sym[int(e["security_id"])] = e["symbol"]
    eng = TapeEngine(TapeConfig({}), sym)
    ReplayEngine(src).drive(eng, speed="max")
    summary = eng.finalize()
    assert summary["counts"]["ticks"] > 0
    assert summary["counts"]["trades"] > 0
    assert summary["totals"]["bars"] > 0        # at least trailing partial bars
    # a liquid future should have extracted trades
    fut = summary["per_instrument"].get("BANKNIFTY_FUT")
    assert fut is not None and fut["trades"] > 0
