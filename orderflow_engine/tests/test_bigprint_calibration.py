"""Big-print calibration tool — guards the two things that would silently invalidate it:
forward-outcome LEAK (peeking past the horizon) and mis-computed percentiles/lot size.
"""

from __future__ import annotations

from research.bigprint_calibration import (
    NS,
    derive_lot_size,
    forward_point_move,
    max_favorable_excursion,
    percentile,
    predictive_futures,
)
from tape.trades import Trade


# -- LEAK GUARDS ------------------------------------------------------------
def test_forward_point_move_ignores_tick_past_horizon():
    """A huge tick one ns past t+horizon must NOT affect the measured move."""
    ts = [0, 5 * NS, 10 * NS, 10 * NS + 1]        # last tick is 1ns past a 10s horizon
    price = [100.0, 101.0, 102.0, 999.0]          # the 999 spike is out of window
    # from i=0, horizon 10s: last in-window tick is index 2 (ts=10s) -> 102-100
    assert forward_point_move(ts, price, 0, 10 * NS) == 2.0
    # the spike at 10s+1ns is invisible
    assert forward_point_move(ts, price, 0, 10 * NS) != 899.0


def test_forward_point_move_none_when_no_tick_in_window():
    ts = [0, 100 * NS]
    price = [100.0, 200.0]
    assert forward_point_move(ts, price, 0, 5 * NS) is None       # nothing within 5s


def test_max_favorable_excursion_hard_bounded():
    """MFE uses only (t_i, t_i+horizon]; a bigger favorable tick past horizon is excluded."""
    ts = [0, 3 * NS, 6 * NS, 61 * NS]
    price = [100.0, 105.0, 103.0, 200.0]          # +100 move is at 61s, past the 60s window
    # BUY side (+1), horizon 60s: best favorable in-window = 105-100 = 5
    assert max_favorable_excursion(ts, price, 1, 0, 60 * NS) == 5.0
    # SELL side (-1): favorable = downward; best in-window = -(103-100)= -3 vs -(105-100)=-5 -> -3
    assert max_favorable_excursion(ts, price, -1, 0, 60 * NS) == -3.0


def test_max_favorable_excursion_none_when_empty_window():
    ts = [0, 100 * NS]
    price = [100.0, 100.0]
    assert max_favorable_excursion(ts, price, 1, 0, 60 * NS) is None


# -- PERCENTILE / LOT -------------------------------------------------------
def test_percentile_nearest_rank():
    v = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    assert percentile(v, 50) == 5.0        # ceil(0.5*10)=5 -> v[4]
    assert percentile(v, 90) == 9.0        # ceil(0.9*10)=9 -> v[8]
    assert percentile(v, 100) == 10.0
    assert percentile([], 90) == 0.0


def test_derive_lot_size_is_gcd():
    trades = [Trade(0, 100.0, 65, 1, 6500.0), Trade(1, 100.0, 130, 1, 13000.0),
              Trade(2, 100.0, 195, 1, 19500.0)]
    assert derive_lot_size(trades) == 65
    assert derive_lot_size([]) == 1


# -- PREDICTIVE plumbing ----------------------------------------------------
def test_predictive_conditional_subsets_by_threshold():
    """A synthetic future where only big prints move favorably: conditional P(>=R) must
    exceed baseline, and prints are counted per day."""
    # NIFTY R=20pt. 40 tiny flat prints (no move within their 60s windows), then FAR later
    # a lone big BUY print immediately followed by a +25pt move. Only the big print can
    # "see" the move, so conditional P(>=R)=1 while baseline stays near 0.
    day = []
    t = 0
    for _ in range(40):
        day.append(Trade(t, 24000.0, 65, 1, 24000.0 * 65)); t += 1 * NS   # flat cluster 0..39s
    big_t = 1000 * NS                                                      # long gap -> isolated
    day.append(Trade(big_t, 24000.0, 6500, 1, 24000.0 * 6500))
    day.append(Trade(big_t + 1 * NS, 24025.0, 65, 1, 24025.0 * 65))       # +25pt within 60s
    res = predictive_futures({"2026-07-15": day}, "NIFTY")
    assert res["n"] == 42
    assert res["lot_size"] == 65
    # the p99 threshold isolates the big print; its favorable excursion reaches 20pt
    assert res["conditional_cost"][99]["p_reach_R"] == 1.0
    # baseline (dominated by flat prints that never see the move) reaches R far less often
    assert res["baseline_cost"]["p_reach_R"] < 0.1
