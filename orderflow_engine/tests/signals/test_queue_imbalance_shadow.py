"""queue_imbalance SHADOW build-out (2026-07-22).

The component now RECORDS its depth-computed value per candidate but stays INERT
(weight 0 -> contribution 0 -> score/fire unchanged). Three proofs:
  (i)   golden: a known bid/ask book -> the recorded queue_imbalance value is correct,
        end to end (depth packets -> tape bar -> SignalContext -> scorer breakdown);
  (ii)  contribution stays 0 (weight 0) so the total score is unchanged;
  (iii) inertness: fired decision + score identical whether the shadow value flows or not.
"""

from __future__ import annotations

from datetime import date

from chain.config import ChainConfig
from chain.engine import ChainEngine
from levels.config import LevelsConfig
from levels.engine import LevelsEngine
from recorder.depth_schema import SIDE_ASK, SIDE_BID
from signals.config import SignalConfig
from signals.engine import SignalEngine
from signals.scorer import score_side
from tape.config import TapeConfig
from tape.engine import TapeEngine

NS = 1_000_000_000
SID = 61088
META = {SID: {"symbol": "BANKNIFTY_FUT", "kind": "future", "index": "BANKNIFTY",
              "right": None, "strike": None, "expiry": ""}}


def _sig(ofi_enabled: bool = False) -> SignalEngine:
    tape = TapeEngine(TapeConfig({"depth": {"ofi_enabled": ofi_enabled},
                                  "bars": {"tick_bar_size": 2}}), {SID: "BANKNIFTY_FUT"})
    lv = LevelsEngine(LevelsConfig({}), {SID: "BANKNIFTY_FUT"}, date="2026-07-13")
    ch = ChainEngine(ChainConfig({}), {}, date(2026, 7, 13))
    return SignalEngine(SignalConfig({}), tape, lv, ch, META, date(2026, 7, 13))


def _bid(ts, **lv):
    return {"security_id": SID, "side": SIDE_BID, **lv}


def _ask(ts, **lv):
    return {"security_id": SID, "side": SIDE_ASK, **lv}


def _tick(eng, ts, vol, ltp):
    # feed the TAPE (the bar builder), not the SignalEngine — they are separate consumers
    eng.tape.on_packet({"is_tick": True, "security_id": SID, "ts_recv_ns": ts, "volume": vol,
                        "ltp": ltp, "ltq": 0, "bid_price_1": ltp - 0.5, "ask_price_1": ltp + 0.5,
                        "ltt": ts // NS}, ts)


# ---------- (i) golden: known book -> correct recorded value, end to end ----------
def test_i_golden_recorded_value_from_known_book():
    """Bid qtys [100,50], ask qtys [30,20] over the top levels ->
    (150 - 50)/(150 + 50) = 100/200 = +0.5 (bid-heavy). OFI stays OFF the whole time."""
    eng = _sig(ofi_enabled=False)
    tape = eng.tape
    # a complete book at the same ts (bid+ask paired) BEFORE the bar closes
    tape.on_depth(_bid(1 * NS, price_1=100.0, qty_1=100, price_2=99.9, qty_2=50), 1 * NS)
    tape.on_depth(_ask(1 * NS, price_1=100.5, qty_1=30, price_2=100.6, qty_2=20), 1 * NS)
    _tick(eng, 1 * NS + 1, 1000, 100.0)          # seed (no trade)
    _tick(eng, 1 * NS + 2, 1010, 100.2)          # trade 1
    _tick(eng, 1 * NS + 3, 1020, 100.4)          # trade 2 -> closes the tick bar
    bar = next(b for b in reversed(tape.bar_rows) if b["bar_type"] == "tick")
    assert bar["queue_imbalance"] == 0.5         # hand value from the known book
    # and it reaches the context EVEN WITH OFI OFF (the shadow wiring)
    ctx = eng._build_context(SID, bar, bar["end_ts_ns"])
    assert ctx.queue_imbalance == 0.5
    assert ctx.book_ofi is None                  # book-OFI scoring stayed gated off
    # ...and it lands in the scorer breakdown as a recorded activation
    bd = score_side(ctx, eng.cfg, "long")["breakdown"]["queue_imbalance"]
    assert bd["activation"] == 0.5               # long-aligned bid-heavy imbalance recorded


# ---------- (ii) contribution stays 0 (weight 0) -> score unaffected ----------
def test_ii_contribution_is_zero_weight_zero():
    eng = _sig()
    bar = {"close": 100.0, "delta": 0, "high": 100.0, "low": 100.0, "cvd_slope": 0.0,
           "velocity_spike": False, "velocity_ratio": 1.0, "ofi": 0.0, "queue_imbalance": 0.5}
    ctx = eng._build_context(SID, bar, 1 * NS)
    s = score_side(ctx, eng.cfg, "long")
    qi = s["breakdown"]["queue_imbalance"]
    assert qi["weight"] == 0.0                    # config weight is 0
    assert qi["activation"] == 0.5               # value is RECORDED
    assert qi["contribution"] == 0.0             # ...but contributes nothing to the score


# ---------- (iii) inertness: score + fire identical with/without the shadow value ----------
def test_iii_score_and_fire_identical_shadow_vs_none():
    eng = _sig()
    base = {"close": 100.0, "delta": 0, "high": 100.0, "low": 100.0, "cvd_slope": 0.0,
            "velocity_spike": False, "velocity_ratio": 1.0, "ofi": 0.0}
    # identical bars except the shadow value: one carries it, one has no book
    ctx_val = eng._build_context(SID, {**base, "queue_imbalance": 0.9}, 1 * NS)
    ctx_none = eng._build_context(SID, {**base, "queue_imbalance": None}, 1 * NS)
    for side in ("long", "short"):
        s_val = score_side(ctx_val, eng.cfg, side)
        s_none = score_side(ctx_none, eng.cfg, side)
        assert s_val["score"] == s_none["score"]                    # total unchanged
        assert (s_val["score"] >= s_val["threshold"]) == \
               (s_none["score"] >= s_none["threshold"])             # fire decision unchanged
    # the ONLY difference is the recorded activation field (the shadow record itself)
    assert score_side(ctx_val, eng.cfg, "long")["breakdown"]["queue_imbalance"]["activation"] == 0.9
    assert score_side(ctx_none, eng.cfg, "long")["breakdown"]["queue_imbalance"]["activation"] == 0.0
