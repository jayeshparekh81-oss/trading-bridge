"""R8 paper executor — sizing (even lots, reject <2, D1 sizedown), risk gates (D1/D2,
daily-loss + consecutive-loss halt), ledger (₹ consistency + equity + TCA), router fence.
Encodes the founder's 17-Jul decisions.
"""

from __future__ import annotations

import pytest

from signals.ledger import Ledger
from signals.order_router import OrderRouter, OrderRouterConfig
from signals.risk import (
    RiskConfig,
    RiskState,
    d1_size_factor,
    on_close,
    on_open,
    pre_trade_gate,
)
from signals.sizing import SizingConfig, size_position

CAP = 500_000.0
SC = SizingConfig()          # risk_pct 1%, max 8, even, min 2


# ---------- sizing ----------
def test_even_round_down_and_reject_below_2():
    # NIFTY ₹5L, 20pt stop, delta .508, lot 65 -> raw 7.57 -> floor 7 -> EVEN 6
    r = size_position(equity_inr=CAP, stop_pts=20, delta=0.508, lot_size=65, cfg=SC)
    assert r.raw_lots == pytest.approx(7.57, abs=0.05) and r.lots == 6 and not r.rejected
    # BANKNIFTY ₹5L, 40pt, .5, 30 -> raw 8.33 -> 8
    assert size_position(equity_inr=CAP, stop_pts=40, delta=0.5, lot_size=30, cfg=SC).lots == 8


def test_1L_is_structurally_untradeable_reject():
    for stop, d, lot in [(20, 0.508, 65), (40, 0.5, 30)]:            # NIFTY, BANKNIFTY
        r = size_position(equity_inr=100_000, stop_pts=stop, delta=d, lot_size=lot, cfg=SC)
        assert r.rejected and r.lots == 0 and r.reason == "sub_2lot_reject"  # 1.5/1.67 -> <2


def test_customer_max_lots_cap_even():
    r = size_position(equity_inr=50_000_000, stop_pts=20, delta=0.5, lot_size=65, cfg=SC)
    assert r.lots == 8 and r.capped_by == "customer_max_lots"       # huge equity -> hits cap (even)


def test_d1_sizedown_halves_size():
    full = size_position(equity_inr=CAP, stop_pts=20, delta=0.508, lot_size=65, cfg=SC)
    half = size_position(equity_inr=CAP, stop_pts=20, delta=0.508, lot_size=65, cfg=SC, size_factor=0.5)
    assert full.lots == 6 and half.lots == 2          # budget halves 5000->2500 -> raw 3.78 -> 2


def test_invalid_inputs_reject_not_raise():
    assert size_position(equity_inr=CAP, stop_pts=0, delta=0.5, lot_size=65, cfg=SC).reason == "invalid_inputs"


# ---------- risk gates ----------
def test_d1_triggers_after_two_consecutive_wins():
    cfg = RiskConfig()
    st = RiskState(equity_inr=CAP, consecutive_wins=1)
    assert d1_size_factor(st, cfg) == 1.0
    st.consecutive_wins = 2
    assert d1_size_factor(st, cfg) == 0.5


def test_d2_global_one_position_blocks():
    cfg, st = RiskConfig(), RiskState(equity_inr=CAP)
    assert pre_trade_gate(st, cfg) == (True, "")
    on_open(st)
    allow, reason = pre_trade_gate(st, cfg)
    assert allow is False and reason == "r8:d2_global_one_position"


def test_daily_loss_limit_halts_the_day():
    cfg, st = RiskConfig(), RiskState(equity_inr=CAP)
    on_close(st, cfg, -1.6)
    on_close(st, cfg, -1.6)            # day_pnl -3.2 <= -3R
    assert st.halted and st.halt_reason == "daily_loss_limit"
    assert pre_trade_gate(st, cfg)[0] is False


def test_three_consecutive_losses_halt():
    cfg, st = RiskConfig(), RiskState(equity_inr=CAP)
    for _ in range(3):
        on_close(st, cfg, -0.5)
    assert st.halted and st.halt_reason == "consecutive_loss_halt"


def test_win_resets_loss_streak():
    cfg, st = RiskConfig(), RiskState(equity_inr=CAP)
    on_close(st, cfg, -0.5); on_close(st, cfg, -0.5)
    on_close(st, cfg, +0.8)            # win resets
    assert st.consecutive_losses == 0 and st.consecutive_wins == 1 and not st.halted


# ---------- ledger ----------
def test_ledger_rupee_consistency_and_equity():
    led = Ledger(CAP)
    # 6 lots NIFTY, stop 20, delta .508, lot 65; gross +0.849R, cost_r 0.543
    e = led.record(ts_ns=1, instrument="NIFTY_FUT", side="long", lots=6, stop_pts=20,
                   delta=0.508, lot_size=65, gross_r=0.849, cost_r=0.543,
                   tca_per_lot={"brokerage": 40.0, "spread": 660.0})
    assert e.risk_inr == pytest.approx(6 * 20 * 0.508 * 65)          # ₹ risked = 1R
    assert e.net_r == pytest.approx(0.306)
    assert e.cost_inr == pytest.approx(e.cost_r * e.risk_inr)
    assert e.net_inr == pytest.approx(e.gross_inr - e.cost_inr)
    assert led.equity_inr == pytest.approx(CAP + e.net_inr)          # equity updated
    assert e.tca["spread"] == pytest.approx(660.0 * 6)               # TCA scaled by lots


def test_ledger_net_below_gross_and_summary():
    led = Ledger(CAP)
    led.record(ts_ns=1, instrument="NIFTY_FUT", side="long", lots=6, stop_pts=20, delta=0.5,
               lot_size=65, gross_r=1.0, cost_r=0.2)
    led.record(ts_ns=2, instrument="NIFTY_FUT", side="long", lots=6, stop_pts=20, delta=0.5,
               lot_size=65, gross_r=-1.0, cost_r=0.2)
    s = led.summary()
    assert s["trades"] == 2 and s["net_r"] < s["gross_r"]            # costs shrink net
    assert s["cost_r"] == pytest.approx(0.4)


# ---------- order router fence ----------
def test_router_off_by_default_and_refuses():
    r = OrderRouter()
    assert r.is_live() is False
    for fn in (r.place, r.modify, r.cancel):
        with pytest.raises(RuntimeError):
            fn()


def test_router_live_requires_enabled_and_live_mode():
    assert OrderRouter(OrderRouterConfig(enabled=True, mode="readonly")).is_live() is False
    assert OrderRouter(OrderRouterConfig(enabled=True, mode="live")).is_live() is True


# ---------- full session loop (the engine's orchestration, module-level) ----------
def _run_trade(st, rcfg, scfg, led, gross_r, cost_r=0.1, stop=20, delta=0.5, lot=65):
    allow, reason = pre_trade_gate(st, rcfg)
    if not allow:
        return ("blocked", reason, None)
    sf = d1_size_factor(st, rcfg)
    sr = size_position(equity_inr=st.equity_inr, stop_pts=stop, delta=delta, lot_size=lot,
                       cfg=scfg, size_factor=sf)
    if sr.rejected:
        return ("reject", sr.reason, sf)
    on_open(st)
    e = led.record(ts_ns=0, instrument="NIFTY_FUT", side="long", lots=sr.lots, stop_pts=stop,
                   delta=delta, lot_size=lot, gross_r=gross_r, cost_r=cost_r)
    on_close(st, rcfg, e.net_r)
    st.equity_inr = led.equity_inr
    return ("done", sr.size_factor, sr.lots)


def test_r8_session_loop_d1_and_equity_compounding():
    rcfg, scfg = RiskConfig(), SizingConfig()
    st, led = RiskState(equity_inr=rcfg.starting_capital_inr), Ledger(rcfg.starting_capital_inr)
    assert _run_trade(st, rcfg, scfg, led, +1.0)[1] == 1.0     # win 1 (full size)
    assert _run_trade(st, rcfg, scfg, led, +1.0)[1] == 1.0     # win 2 (full size)
    r3 = _run_trade(st, rcfg, scfg, led, +1.0)                 # D1: 3rd after 2 wins -> half size
    assert r3[1] == 0.5
    assert led.equity_inr > rcfg.starting_capital_inr          # equity compounded up


def test_r8_session_loop_consecutive_loss_halt_blocks():
    rcfg, scfg = RiskConfig(), SizingConfig()
    st, led = RiskState(equity_inr=rcfg.starting_capital_inr), Ledger(rcfg.starting_capital_inr)
    for _ in range(3):
        _run_trade(st, rcfg, scfg, led, -1.0)                  # 3 straight losses
    assert _run_trade(st, rcfg, scfg, led, +1.0)[:2] == ("blocked", "r8:consecutive_loss_halt")
