"""End-to-end: a constructed day fires EXACTLY once long + once short (hand-tuned)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from replayer.engine import ReplayEngine
from replayer.source import ReplaySource

from chain.config import ChainConfig
from chain.engine import ChainEngine
from levels.config import LevelsConfig
from levels.engine import LevelsEngine
from signals.config import SignalConfig
from signals.engine import SignalEngine
from signals.pipeline import MultiConsumer
from tape.config import TapeConfig
from tape.engine import TapeEngine
from tests.replayer import fixtures as RF

NS = 1_000_000_000
SID = 61088
META = {SID: {"symbol": "BANKNIFTY_FUT", "kind": "future", "index": "BANKNIFTY",
              "right": None, "strike": None, "expiry": ""}}


def _row(ts, vol, ltp):
    return {"ts_recv_ns": ts, "volume": vol, "ltp": ltp}


def _day(tmp_path) -> Path:
    day = tmp_path / "2026-07-13"
    rows = [
        _row(1 * NS, 1000, 100.0),                       # seed
        _row(2 * NS, 1001, 100.1), _row(3 * NS, 1002, 100.2),   # bar1: +2 cvd (slope 0)
        _row(4 * NS, 1012, 100.3), _row(5 * NS, 1022, 100.4),   # bar2: +22 cvd (slope +20 -> LONG)
        _row(6 * NS, 1042, 100.0), _row(7 * NS, 1062, 99.0),    # bar3: -18 cvd (slope -10 -> SHORT)
    ]
    RF.write_instrument(day, "BANKNIFTY_FUT", SID, rows)
    return day


def _cfg():
    comps = {c: {"enabled": False, "weight": 0.0} for c in
             ["book_ofi", "big_print", "queue_imbalance", "vwap_value_location",
              "level_zone", "tape_velocity", "regime", "pain_map"]}
    comps["cvd_confirm"] = {"enabled": True, "weight": 10.0}
    return SignalConfig({"signal": {
        "tradeable": ["BANKNIFTY_FUT"], "fire_threshold": 10.0,
        "short": {"fire_threshold": 10.0, "weight_overrides": {}},
        "components": comps,
        "asymmetric_gate": {"enabled": False},
        "gates": {"first_minutes_no_entry": 0, "cooldown_s": 0, "one_open_position": False,
                  "max_trades_per_day": 99, "session_cutoff": "23:59",
                  "expiry_theta_guard": {"enabled": False},
                  "liquidity": {"enabled": False}},
    }})


def _run(tmp_path):
    day = _day(tmp_path)
    tape = TapeEngine(TapeConfig({"bars": {"tick_bar_size": 2}}), {SID: "BANKNIFTY_FUT"})
    lv = LevelsEngine(LevelsConfig({}), {SID: "BANKNIFTY_FUT"}, date="2026-07-13")
    ch = ChainEngine(ChainConfig({}), {}, date(2026, 7, 13))
    sig = SignalEngine(_cfg(), tape, lv, ch, META, date(2026, 7, 13))
    multi = MultiConsumer([tape, lv, ch, sig])
    ReplayEngine(ReplaySource(day)).drive(multi, speed="max")
    sig.finalize()
    return sig


def test_fires_exactly_once_long_and_once_short(tmp_path):
    sig = _run(tmp_path)
    longs = [r for r in sig.rows if r["fired"] and r["side"] == "long"]
    shorts = [r for r in sig.rows if r["fired"] and r["side"] == "short"]
    assert len(longs) == 1, [(r["side"], r["score"], r["fired"]) for r in sig.rows]
    assert len(shorts) == 1
    assert longs[0]["score"] == 10.0 and shorts[0]["score"] == 10.0
    # each fired signal carries an exit plan
    assert longs[0]["entry"] is not None and longs[0]["r_value"] is not None
