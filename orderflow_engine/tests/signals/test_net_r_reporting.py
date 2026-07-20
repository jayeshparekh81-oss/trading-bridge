"""Net-R reporting wiring (2026-07-20) — gross AND net, everywhere, reporting-only.

Three guarantees:
  1. GOLDEN: the locked 17-trade baseline fixture — gross total unchanged (+2.018, the
     3dp-rounded locked sum) AND net == gross − Σ per-trade cost via the REAL model
     (trade_net_r), never a duplicate formula.
  2. slippage_multiplier stress knob scales ONLY the friction terms (spread+slippage),
     default 1.0 == byte-identical.
  3. finalize() summary carries gross_r_total / cost_r_total / net_r_total /
     costed_trades, with net_simulated_r kept == gross for backward compat.
"""

from __future__ import annotations

from datetime import date

import pytest

from chain.config import ChainConfig
from chain.engine import ChainEngine
from levels.config import LevelsConfig
from levels.engine import LevelsEngine
from signals.config import SignalConfig
from signals.costs import CostConfig, round_trip_cost, trade_net_r
from signals.engine import SignalEngine
from tape.config import TapeConfig
from tape.engine import TapeEngine

# --- the LOCKED 17-trade baseline (07-15/16/17, threshold 40, OFI on, GROSS) ----------
# (instrument, r_unit_pts, gross_R) — exactly the frozen reference; 3dp-rounded sum +2.018.
LOCKED_17 = [
    ("NIFTY", 19.20, +2.680), ("NIFTY", 28.07, +1.065), ("BANKNIFTY", 65.68, +0.582),
    ("BANKNIFTY", 91.70, +1.014), ("NIFTY", 24.81, -1.004), ("NIFTY", 15.55, +0.497),
    ("NIFTY", 9.85, -1.010), ("NIFTY", 9.00, -1.011), ("BANKNIFTY", 23.59, -1.004),
    ("BANKNIFTY", 25.65, +0.967), ("BANKNIFTY", 23.72, +0.498), ("BANKNIFTY", 25.07, +0.498),
    ("BANKNIFTY", 30.10, -1.003), ("BANKNIFTY", 20.52, -1.005), ("NIFTY", 7.27, -1.014),
    ("NIFTY", 7.27, -1.014), ("NIFTY", 14.65, +2.282),
]
# scrip-master lots (2026-07, SEM_LOT_UNITS — the lot-size ROOT-fix values, not config's old 75/35)
LOT = {"NIFTY": 65, "BANKNIFTY": 30}
PREMIUM = 300.0          # representative ATM premium for the golden (fixed, stated)
DELTA = 0.5              # fallback delta (greeks-free golden), FLAGGED source


def test_golden_17_gross_unchanged_and_net_is_gross_minus_model_cost():
    cfg = CostConfig()
    gross_total = sum(g for _, _, g in LOCKED_17)
    assert gross_total == pytest.approx(2.018, abs=5e-4)     # frozen baseline GROSS untouched
    costs = []
    nets = []
    for idx, r_unit, gross in LOCKED_17:
        net, cost_r, b = trade_net_r(realized_r=gross, r_unit_pts=r_unit,
                                     entry_premium=PREMIUM, delta=DELTA,
                                     delta_source="fallback", lot_size=LOT[idx], cfg=cfg)
        assert cost_r > 0
        assert net == pytest.approx(gross - cost_r)          # additive, never multiplicative
        costs.append(cost_r)
        nets.append(net)
    # THE reporting identity: net total == gross total − (Σ 17 per-trade costs), REAL model
    assert sum(nets) == pytest.approx(gross_total - sum(costs))
    assert sum(nets) < gross_total                           # any positive cost shrinks
    # cost_r is R-unit-relative: the tightest stop (7.27) pays MORE R than the widest (91.70)
    tight = next(c for (i, r, g), c in zip(LOCKED_17, costs) if r == 7.27)
    wide = next(c for (i, r, g), c in zip(LOCKED_17, costs) if r == 91.70)
    assert tight > wide


def test_slippage_multiplier_scales_friction_only():
    base = CostConfig()
    stressed = CostConfig.from_dict({"slippage_multiplier": 1.5})
    kw = dict(entry_premium=PREMIUM, lot_size=65, delta=DELTA, delta_source="fallback",
              r_unit_pts=10.0)
    b1 = round_trip_cost(cfg=base, **kw)
    b15 = round_trip_cost(cfg=stressed, **kw)
    # ₹ charges identical (rates are not execution quality)
    assert b15.charges_inr_total == pytest.approx(b1.charges_inr_total)
    assert b15.charges_option_pts == pytest.approx(b1.charges_option_pts)
    # friction terms scale exactly 1.5x
    assert b15.spread_option_pts == pytest.approx(1.5 * b1.spread_option_pts)
    assert b15.total_option_pts == pytest.approx(
        b1.charges_option_pts + 1.5 * (b1.spread_option_pts + b1.slippage_option_pts))
    assert b15.cost_r > b1.cost_r
    # default 1.0 == byte-identical (the INERT guarantee)
    assert round_trip_cost(cfg=CostConfig.from_dict({}), **kw).cost_r == pytest.approx(b1.cost_r)


SID = 61088
META = {SID: {"symbol": "BANKNIFTY_FUT", "kind": "future", "index": "BANKNIFTY",
              "right": None, "strike": None, "expiry": ""}}


def _sig(cost_model: dict | None = None) -> SignalEngine:
    scfg = SignalConfig({"signal": {"cost_model": cost_model}} if cost_model else {})
    tape = TapeEngine(TapeConfig({"bars": {"tick_bar_size": 2}}), {SID: "BANKNIFTY_FUT"})
    lv = LevelsEngine(LevelsConfig({}), {SID: "BANKNIFTY_FUT"}, date="2026-07-13")
    ch = ChainEngine(ChainConfig({}), {}, date(2026, 7, 13))
    return SignalEngine(scfg, tape, lv, ch, META, date(2026, 7, 13))


def test_config_plumbs_multiplier_into_engine_cost_cfg():
    assert SignalConfig({}).cost_model == {"slippage_multiplier": 1.0}
    assert _sig().cost_cfg.slippage_multiplier == 1.0
    assert _sig({"slippage_multiplier": 1.5}).cost_cfg.slippage_multiplier == 1.5


def test_finalize_summary_reports_gross_and_net_keys():
    s = _sig().finalize()
    for k in ("gross_r_total", "cost_r_total", "net_r_total", "costed_trades"):
        assert k in s
    # backward compat: net_simulated_r stays == GROSS (the frozen-baseline number)
    assert s["net_simulated_r"] == s["gross_r_total"]
    # no trades -> zeroes, and net == gross − cost even in the trivial case
    assert s["costed_trades"] == 0
    assert s["net_r_total"] == pytest.approx(s["gross_r_total"] - s["cost_r_total"])
