"""Delta+VWAP-side evaluator tests (i)-(iv).

(i)   golden day: hand-verified delta_al / vwap_dist_al / median / fire decision
(ii)  planted-leak: a test-day extreme can NEVER move the training median
(iii) pricing identity: a would-fire candidate is priced EXACTLY like a live _fire()
(iv)  strict-inequality ties: exactly-at-median and exactly-at-VWAP do NOT fire

Fixture days replay a single instrument (NIFTY_FUT) under a test config with
tick_bar_size=2 (tick bars close on TRADE COUNT), so every bar is exactly two
50-lot trades and its delta / VWAP / OHLC are hand-computable. The frozen repo
config keeps 100; the evaluator itself defaults to it (config_path=None).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from research.delta_vwap_evaluator import (
    DayCapture, capture_day, day_trades, make_evaluator, med, median_delta_al,
    median_for_split, price_candidate, rule_decisions, rule_fires,
)
from research.walkforward import Split
from tape.config import HERE as ENGINE_ROOT
from tests.replayer import fixtures as RF

NS = 1_000_000_000
SID = 61093
T0 = 1000 * NS                                       # seed ts; bars start +360s (>5min gate)


def _tick(ts, vol, ltp):
    return {"ts_recv_ns": ts, "volume": vol, "ltp": ltp, "ltq": 0,
            "bid_price_1": ltp - 0.05, "ask_price_1": ltp + 0.05, "ltt": ts // NS}


def _write_day(root: Path, day: str, ticks):
    d = root / "data" / day
    RF.write_instrument(d, "NIFTY_FUT", SID, ticks)
    RF.write_events(d, [{"ts_ns": 0, "kind": "SESSION", "detail": "start", "value_num": None}])
    (d / "manifest.json").write_text(json.dumps({"instruments": [
        {"symbol": "NIFTY_FUT", "security_id": SID, "kind": "future",
         "exchange_segment": "NSE_FNO", "gap_check": True, "expiry": ""}]}))


def _bar(ts_s, vol0, p1, p2):
    """One 2-trade tick bar: 50 lots @p1 then 50 lots @p2; closes on the 2nd trade."""
    return [_tick(T0 + ts_s * NS, vol0 + 50, p1),
            _tick(T0 + (ts_s + 1) * NS, vol0 + 100, p2)]


# TRAIN day: 4 bars, deltas +100/-100/+100/-100 (Lee-Ready: upticks BUY, downticks
# SELL, zero-tick inherits). Pooled long+short delta_al = {+-100} x4 -> median 0.0.
DAY_A = "2026-06-01"
TICKS_A = ([_tick(T0, 1000, 100.00)]                 # seed, no trade
           + _bar(360, 1000, 100.05, 100.10)         # b1 BUY+BUY   -> +100
           + _bar(420, 1100, 100.05, 100.00)         # b2 SELL+SELL -> -100
           + _bar(480, 1200, 100.10, 100.20)         # b3 BUY+BUY   -> +100
           + _bar(540, 1300, 100.10, 100.05))        # b4 SELL+SELL -> -100

# TEST day (bar closes at the +1s tick):
#   b1: BUY 50 @100.10 + BUY 50 @100.10 (zero-tick) -> delta +100, close 100.10,
#       VWAP 100.10 -> vwap_dist_al(long) = 0.0 EXACTLY (the VWAP tie)
#   b2: BUY+BUY @100.20/100.30 -> delta +100, close 100.30,
#       VWAP = 20035/200 = 100.175 -> vwap_dist_al(long) = +0.125  => the ONE fire
#   b3: SELL 50 @100.20 + BUY 50 @100.30 -> delta 0 == median (the delta tie)
#   b4: BUY+BUY @100.35/100.40 -> +100, close above VWAP => also fires long (hand-ok)
#   b5: SELL+SELL @99.50/99.00 -> delta -100, close below VWAP => fires SHORT
#       (short-aligned delta +100 > 0, short vwap_dist > 0) and stops b2/b4's longs
DAY_B = "2026-06-02"
B1, B2, B3 = T0 + 361 * NS, T0 + 421 * NS, T0 + 481 * NS
B4, B5 = T0 + 541 * NS, T0 + 601 * NS
TICKS_B = ([_tick(T0, 1000, 100.00)]
           + _bar(360, 1000, 100.10, 100.10)
           + _bar(420, 1100, 100.20, 100.30)
           + _bar(480, 1200, 100.20, 100.30)
           + _bar(540, 1300, 100.35, 100.40)
           + _bar(600, 1400, 99.50, 99.00))


@pytest.fixture(scope="module")
def caps(tmp_path_factory):
    root = tmp_path_factory.mktemp("dv")
    cfg = yaml.safe_load((ENGINE_ROOT / "tape_config.yaml").read_text())
    cfg["tape"]["bars"]["tick_bar_size"] = 2         # 2 trades per bar; rest frozen
    cfg_path = root / "test_tape_config.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg))
    _write_day(root, DAY_A, TICKS_A)
    _write_day(root, DAY_B, TICKS_B)
    kw = dict(root=root, instruments=["NIFTY_FUT"], config_path=cfg_path)
    return ({DAY_A: capture_day(DAY_A, **kw), DAY_B: capture_day(DAY_B, **kw)},
            root, cfg_path)


# ---------- (i) golden day: hand-verified values, median, decision -----------
def test_i_golden_hand_verified(caps):
    captures, _, _ = caps
    # training median: pooled +-100 x4 -> exactly 0.0 (hand: mean of middle -100,+100)
    dmed = median_delta_al(captures, [DAY_A], "NIFTY_FUT")
    assert dmed == 0.0
    assert med([-100, -100, -100, -100, 100, 100, 100, 100]) == 0.0   # the hand computation
    cb = captures[DAY_B]
    by = {(c["ts_ns"], c["side"]): c for c in cb.candidates}
    g = by[(B2, "long")]                              # the engineered fire
    assert g["delta_al"] == 100                       # hand: two 50-lot BUYs
    assert g["vwap_dist_al"] == pytest.approx(0.125, abs=1e-9)   # 100.30 - 100.175
    decisions = dict(((c["ts_ns"], c["side"]), f)
                     for c, f in rule_decisions(cb, "NIFTY_FUT", dmed))
    assert decisions[(B2, "long")] is True
    assert decisions[(B2, "short")] is False          # delta_al = -100
    # the EXACT fire set (each hand-verifiable): b2-long, b4-long (delta +100, close
    # above VWAP), b5-short (short-aligned delta +100, close below VWAP). b1/b3 are
    # the tie cases (test iv); everything else is on the wrong side of something.
    assert {k for k, f in decisions.items() if f} == \
        {(B2, "long"), (B4, "long"), (B5, "short")}
    # evaluator seam: day A has no prior days -> dmed None -> zero trades, by design
    ev = make_evaluator([DAY_A, DAY_B], captures, "NIFTY_FUT")
    assert ev(None, [DAY_A]) == []
    # b5-short fires on the day's LAST bar -> no bar after entry -> unpriceable ->
    # SKIPPED AND COUNTED (deep-dive indep_R semantics; never guessed)
    trades, audit = day_trades(cb, "NIFTY_FUT", dmed)
    assert [t.entry_ns for t in trades] == [B2, B4] and all(t.day == DAY_B for t in trades)
    assert audit["rule_fires"] == 3 and audit["priced"] == 2
    assert audit["skipped_unpriceable"] == 1
    assert ev(None, [DAY_B]) == trades                # seam == the same day pipeline
    rec = price_candidate(cb, g)
    assert trades[0].r == rec["realized_r"]           # Trade.r is the priced outcome


# ---------- (ii) planted leak: test-day extreme never moves the median -------
def test_ii_planted_leak_median_train_only():
    def cand(delta, vwap=1.0):
        return {"ts_ns": 0, "sid": 1, "instrument": "NIFTY_FUT", "side": "long",
                "fired": False, "score": 0.0, "delta_al": delta, "vwap_dist_al": vwap}
    train = DayCapture(day="d1", candidates=[cand(10), cand(-10), cand(30), cand(-30)])
    test = DayCapture(day="d2", candidates=[cand(1e9), cand(5)])   # PLANTED extreme
    captures = {"d1": train, "d2": test}
    split = Split(0, ("d1",), ("d2",), ())
    dmed = median_for_split(split, captures, "NIFTY_FUT")
    assert dmed == 0.0                                # hand median of train ONLY
    # had the planted 1e9 leaked in: med([-30,-10,10,30,1e9]) = 10 -> 5 would NOT fire
    assert med([-30, -10, 10, 30, 1e9]) == 10
    decisions = dict((c["delta_al"], f) for c, f in rule_decisions(test, "NIFTY_FUT", dmed))
    assert decisions[5] is True                       # fires <=> the median is train-only
    # evaluator seam is equally causal: d1 (no prior day) yields no trades
    assert make_evaluator(["d1", "d2"], captures, "NIFTY_FUT")(None, ["d1"]) == []


# ---------- (iii) pricing identity with a real live _fire() ------------------
def test_iii_priced_identically_to_live_fire(caps):
    captures, root, cfg_path = caps
    from replayer.engine import ReplayEngine
    from replayer.source import ReplaySource
    from signals.config import load_signal_config
    from signals.pipeline import build_pipeline
    # fire-mode replay of DAY_B: long threshold -1000 -> the first gate-eligible long
    # candidate (b1: 361s > 5-min warmup) fires through the REAL _fire() path; the
    # 300s cooldown then blocks every later bar, so exactly one live trade exists.
    sc = load_signal_config(cfg_path)
    sc.d["fire_threshold"] = -1000.0
    dd = Path(root) / "data" / DAY_B
    multi, parts = build_pipeline(dd, sc, config_path=cfg_path)
    ReplayEngine(ReplaySource(dd, instruments=["NIFTY_FUT"])).drive(multi, speed="max")
    parts["signal"].finalize()
    live = [r for r in parts["signal"].rows if r["fired"]]
    assert len(live) == 1 and live[0]["ts_ns"] == B1 and live[0]["side"] == "long"
    assert live[0]["realized_r"] is not None
    # the evaluator prices the SAME candidate from its own (fence-999) capture
    cb = captures[DAY_B]
    cand = next(c for c in cb.candidates if c["ts_ns"] == B1 and c["side"] == "long")
    rec = price_candidate(cb, cand)
    for k in ("entry", "stop", "target", "r_value", "exit_reason", "realized_r"):
        assert rec[k] == live[0][k], f"{k}: evaluator {rec[k]} != live {live[0][k]}"
    assert rec["exit_reason"] == "stop"               # b5 low 99.00 takes the stop, not EOD
    assert rec["cost_r"] is None                      # no chain/lot on fixture -> gross only,
    #                                                   same guard as live _apply_costs


# ---------- (iv) strict-inequality ties do not fire --------------------------
def test_iv_tie_behavior_preserved(caps):
    # unit level, quirks verbatim
    assert rule_fires(100.0, 0.10, 100.0) is False    # delta EXACTLY at median
    assert rule_fires(0.0, 0.10, 0.0) is False        # delta tie at 0
    assert rule_fires(100.0, 0.0, 0.0) is False       # price EXACTLY at VWAP ('or' falsy)
    assert rule_fires(100.0, None, 0.0) is False      # VWAP missing
    assert rule_fires(None, 0.10, 0.0) is False       # delta missing
    assert rule_fires(100.0, 0.10, None) is False     # no training median -> never
    assert rule_fires(100.0, 0.10, 0.0) is True       # the passing shape
    assert rule_fires(100.0, -0.10, 0.0) is False     # wrong VWAP side
    # engine level, from the real replay: b1-long (vwap_dist_al == 0.0 exactly) and
    # b3-long (delta_al == 0 == median exactly) both refused
    captures, _, _ = caps
    cb = captures[DAY_B]
    by = {(c["ts_ns"], c["side"]): c for c in cb.candidates}
    assert by[(B1, "long")]["vwap_dist_al"] == 0.0
    assert by[(B3, "long")]["delta_al"] == 0
    decisions = dict(((c["ts_ns"], c["side"]), f)
                     for c, f in rule_decisions(cb, "NIFTY_FUT", 0.0))
    assert decisions[(B1, "long")] is False
    assert decisions[(B3, "long")] is False
