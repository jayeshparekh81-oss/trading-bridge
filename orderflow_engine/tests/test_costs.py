"""Round-trip cost model — each component, the future→option conversion with a REAL
recorded delta, net<gross always, and the asymmetry inversion (a loser's net worse than -1R).
"""

from __future__ import annotations

import pytest

from signals.costs import (
    CostConfig,
    atm_option_delta,
    atm_option_premium,
    net_r,
    round_trip_cost,
    trade_net_r,
)

CFG = CostConfig()


def _cost(**kw):
    base = dict(entry_premium=100.0, lot_size=50, delta=0.5, delta_source="recorded",
                r_unit_pts=10.0, cfg=CFG)
    base.update(kw)
    return round_trip_cost(**base)


# --- each component itemised correctly --------------------------------------
def test_each_cost_component():
    b = _cost()                                   # premium 100, lot 50 -> turnover 5000/leg
    assert b.brokerage_inr == pytest.approx(40.0)             # 20 x 2 orders
    assert b.stt_inr == pytest.approx(5.0)                    # 0.1% x 5000 sell
    assert b.exchange_txn_inr == pytest.approx(0.0003503 * 10000)   # both legs
    assert b.sebi_inr == pytest.approx(0.000001 * 10000)
    assert b.stamp_duty_inr == pytest.approx(0.00003 * 5000)  # buy only
    assert b.gst_inr == pytest.approx(0.18 * (40.0 + 0.0003503 * 10000 + 0.000001 * 10000))
    assert b.charges_inr_total == pytest.approx(
        b.brokerage_inr + b.stt_inr + b.exchange_txn_inr + b.sebi_inr + b.stamp_duty_inr + b.gst_inr)


def test_charges_to_option_points_and_spread():
    b = _cost()
    assert b.charges_option_pts == pytest.approx(b.charges_inr_total / 50)
    assert b.spread_option_pts == 1.0                        # measured default
    assert b.total_option_pts == pytest.approx(b.charges_option_pts + 1.0 + 0.0)


def test_spread_and_slippage_are_parameters():
    b = round_trip_cost(entry_premium=100.0, lot_size=50, delta=0.5, delta_source="recorded",
                        r_unit_pts=10.0, cfg=CFG, spread_override=1.6, slippage_override=0.4)
    assert b.spread_option_pts == 1.6 and b.slippage_option_pts == 0.4


# --- the conversion: future <-> option via delta ----------------------------
def test_conversion_uses_delta():
    """Same option-point cost, higher delta -> FEWER future points to cover it."""
    lo = _cost(delta=0.4)
    hi = _cost(delta=0.6)
    assert lo.total_future_pts > hi.total_future_pts          # cost/delta shrinks as delta grows
    assert lo.total_future_pts == pytest.approx(lo.total_option_pts / 0.4)
    assert hi.cost_r == pytest.approx(hi.total_future_pts / 10.0)


# --- net < gross ALWAYS, and the asymmetry inversion ------------------------
def test_net_always_below_gross():
    b = _cost()
    for gross in (-2.0, -1.0, 0.0, 0.849, 3.0):
        assert net_r(gross, b.cost_r) < gross                 # any positive cost shrinks R


def test_loser_net_is_worse_than_minus_1R():
    b = _cost()
    assert b.cost_r > 0
    assert net_r(-1.0, b.cost_r) < -1.0                       # costs deepen a loss past -1R


def test_trade_net_r_derives_exit_premium_and_stays_below_gross():
    net, cost_r, b = trade_net_r(realized_r=0.849, r_unit_pts=7.22, entry_premium=138.0,
                                 delta=0.5075, delta_source="recorded", lot_size=65, cfg=CFG)
    assert cost_r > 0 and net == pytest.approx(0.849 - cost_r)
    assert b.delta_source == "recorded"
    # the 07-15 proof trade lands ~+0.31R (near the hand-figure), loss side worse than -1R
    assert 0.25 < net < 0.36
    assert net_r(-1.0, cost_r) < -1.0


# --- delta sourced from recorded greeks, fallback flagged -------------------
def _row(ts, strike, right, delta, ltp=100.0):
    return {"snapshot_ts_ns": ts, "index": "NIFTY", "strike": strike, "right": right,
            "delta": delta, "ltp": ltp}


def test_delta_sourced_from_recorded_atm():
    rows = [_row(5, 24000, "CE", 0.63), _row(5, 24100, "CE", 0.51), _row(5, 24200, "CE", 0.39),
            _row(5, 24100, "PE", -0.49)]
    d, src = atm_option_delta(rows, ts_ns=9, spot=24090, side="long", cfg=CFG)
    assert src == "recorded" and d == pytest.approx(0.51)     # ATM CE, |delta|
    d2, src2 = atm_option_delta(rows, ts_ns=9, spot=24090, side="short", cfg=CFG)
    assert src2 == "recorded" and d2 == pytest.approx(0.49)   # ATM PE, |delta|


def test_delta_no_lookahead_uses_last_prior_snapshot():
    rows = [_row(5, 24100, "CE", 0.51), _row(100, 24100, "CE", 0.99)]   # future snapshot huge
    d, _ = atm_option_delta(rows, ts_ns=50, spot=24100, side="long", cfg=CFG)
    assert d == pytest.approx(0.51)                           # the ts>50 snapshot is invisible


def test_delta_fallback_flagged_when_no_greeks():
    d, src = atm_option_delta([], ts_ns=9, spot=24100, side="long", cfg=CFG)
    assert src == "fallback" and d == CFG.fallback_delta


def test_premium_sourced_from_atm():
    rows = [_row(5, 24100, "CE", 0.51, ltp=137.6), _row(5, 24200, "CE", 0.39, ltp=95.7)]
    assert atm_option_premium(rows, 9, 24090, "long") == pytest.approx(137.6)


def test_invalid_inputs_rejected():
    for bad in (dict(delta=0.0), dict(lot_size=0), dict(r_unit_pts=0.0)):
        with pytest.raises(ValueError):
            _cost(**bad)
