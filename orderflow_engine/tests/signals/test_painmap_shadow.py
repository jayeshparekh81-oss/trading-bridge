"""pain_map SHADOW wiring (2026-07-23) — buildup_matrix now flows ChainEngine -> ctx.

O1 audit gap: ChainEngine computes _buildup_matrix but _fill_chain dropped it, so pain_map's
fuel term read an always-empty dict. This wires it (additive), records the real activation,
and stays INERT (pain_map weight 0 -> contribution 0 -> score/fire unchanged).

  (i)   golden: a hand-built buildup_matrix flows through _fill_chain into ctx, and pain_map's
        activation computes correctly from it;
  (ii)  contribution stays 0 at weight 0, total score unchanged;
  (iii) inertness: score + fire identical with the buildup populated vs empty (weight 0).
        (The full replay-day R2-hash byte-identical proof is deferred to post-close per the
        market-hours I/O constraint.)
"""

from __future__ import annotations

from datetime import date

from chain.config import ChainConfig
from chain.engine import ChainEngine
from levels.config import LevelsConfig
from levels.engine import LevelsEngine
from signals.config import SignalConfig
from signals.engine import SignalEngine
from signals.painmap import trapped_pressure
from signals.scorer import score_side
from tape.config import TapeConfig
from tape.engine import TapeEngine
from tests.signals.fixtures import make_ctx

NS = 1_000_000_000
SID = 61088
IDX = "BANKNIFTY"
META = {SID: {"symbol": "BANKNIFTY_FUT", "kind": "future", "index": IDX,
              "right": None, "strike": None, "expiry": ""}}


def _sig() -> SignalEngine:
    tape = TapeEngine(TapeConfig({"bars": {"tick_bar_size": 2}}), {SID: "BANKNIFTY_FUT"})
    lv = LevelsEngine(LevelsConfig({}), {SID: "BANKNIFTY_FUT"}, date="2026-07-13")
    ch = ChainEngine(ChainConfig({}), {}, date(2026, 7, 13))
    return SignalEngine(SignalConfig({}), tape, lv, ch, META, date(2026, 7, 13))


def _bar():
    return {"close": 50000.0, "delta": 0, "high": 50000.0, "low": 50000.0, "cvd_slope": 0.0,
            "velocity_spike": False, "velocity_ratio": 1.0, "ofi": 0.0, "queue_imbalance": None}


# ---------- (i) golden: buildup flows through _fill_chain into ctx ----------
def test_i_golden_buildup_flows_and_pain_map_computes():
    sig = _sig()
    ts = 100 * NS
    # a minimal-but-complete chain grid so _fill_chain proceeds (analytics run harmlessly)
    row = lambda right: {"index": IDX, "snapshot_ts_ns": ts, "right": right, "strike": 50000,
                         "oi": 100, "ltp": 50.0, "volume": 10, "gamma": 0.0, "delta": 0.5, "iv": None}
    sig.chain.rows = [row("CE"), row("PE")]
    sig.chain.spot[IDX] = (50000.0, ts)
    # hand-built buildup matrix (the ChainEngine's causal output, stubbed to a known value)
    sig.chain._buildup_matrix = lambda index: {"short_buildup": 3, "long_buildup": 1}

    ctx = sig._build_context(SID, _bar(), ts)
    assert ctx.buildup_matrix == {"short_buildup": 3, "long_buildup": 1}   # WIRING proven
    # isolate the fuel term from the max-pain nudge, then hand-check pain_map:
    # total=4, long fuel = short_buildup+short_covering = 3+0 = 3 -> 3/4 = 0.75
    ctx.max_pain = None
    assert trapped_pressure(ctx, "long") == 0.75
    assert trapped_pressure(ctx, "short") == 0.25   # long_buildup+long_unwinding = 1/4


def test_i_empty_when_chain_has_no_rows():
    # no chain rows for the index -> _fill_chain early-returns -> buildup stays the default {}
    sig = _sig()
    sig.chain.rows = []
    ctx = sig._build_context(SID, _bar(), 100 * NS)
    assert ctx.buildup_matrix == {}                 # no chain data -> empty, no crash


# ---------- (ii) contribution stays 0 at weight 0, score unchanged ----------
def test_ii_contribution_zero_weight_zero():
    ctx = make_ctx(buildup_matrix={"short_buildup": 10})   # strong long fuel
    s = score_side(ctx, SignalConfig({}), "long")
    pm = s["breakdown"]["pain_map"]
    assert pm["weight"] == 0.0
    assert pm["activation"] > 0                      # RECORDED (real fuel)
    assert pm["contribution"] == 0.0                # ...but contributes nothing


# ---------- (iii) inertness: score + fire identical, populated vs empty ----------
def test_iii_score_and_fire_identical_populated_vs_empty():
    cfg = SignalConfig({})
    filled = make_ctx(buildup_matrix={"short_buildup": 8, "long_buildup": 2})
    empty = make_ctx(buildup_matrix={})
    for side in ("long", "short"):
        sf = score_side(filled, cfg, side)
        se = score_side(empty, cfg, side)
        assert sf["score"] == se["score"]                                   # total unchanged
        assert (sf["score"] >= sf["threshold"]) == (se["score"] >= se["threshold"])  # fire same
    # the only difference is the recorded pain_map activation (the shadow record itself)
    assert score_side(filled, cfg, "long")["breakdown"]["pain_map"]["activation"] > 0
    assert score_side(empty, cfg, "long")["breakdown"]["pain_map"]["activation"] == 0.0
