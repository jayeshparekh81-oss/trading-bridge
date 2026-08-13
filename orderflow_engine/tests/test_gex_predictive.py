"""GEX predictive tool — early-window no-look-ahead + realized outcomes.

Guards the two things that would silently invalidate the measurement: an early GEX
read that peeks at post-window snapshots, and mis-computed outcome metrics.
"""

from __future__ import annotations

from research.gex_predictive import early_gex, realized_outcomes
from chain.gex import net_gex

NS = 1_000_000_000
CS = 75


def _strike(ts, strike, gamma, oi, right):
    return {"snapshot_ts_ns": ts, "strike": strike, "gamma": gamma, "oi": oi, "right": right}


def test_early_gex_ignores_post_window_snapshots():
    """The T+30min snapshot (outside a 15-min window) must NOT affect the early read."""
    t0 = 1_000_000 * NS
    early = [_strike(t0, 24000, 0.01, 1000, "CE"), _strike(t0, 24000, 0.01, 800, "PE")]
    late = [_strike(t0 + 30 * 60 * NS, 24000, 0.05, 9_000_000, "PE")]   # huge, opposite
    res = early_gex(early + late, n_minutes=15, contract_size=CS)
    assert res["read_ts_ns"] == t0                       # read is the in-window snapshot
    assert res["window_snapshots"] == 1                  # the late one is excluded
    # value equals net_gex of ONLY the early strikes — the late snapshot is invisible
    assert res["early_net_gex"] == net_gex(early, CS)
    assert res["early_net_gex"] != net_gex(early + late, CS)


def test_early_gex_uses_last_snapshot_inside_window():
    """Two snapshots inside the window -> the read is the later (T+N) one."""
    t0 = 5 * NS
    s1 = [_strike(t0, 24000, 0.01, 1000, "CE")]
    s2 = [_strike(t0 + 10 * 60 * NS, 24100, 0.02, 2000, "CE")]           # +10min, still <15
    res = early_gex(s1 + s2, n_minutes=15, contract_size=CS)
    assert res["window_snapshots"] == 2
    assert res["read_ts_ns"] == t0 + 10 * 60 * NS
    assert res["early_net_gex"] == net_gex(s2, CS)


def test_early_gex_empty_returns_none():
    assert early_gex([], n_minutes=15, contract_size=CS) is None


def test_realized_outcomes_metrics():
    ts = [i * NS for i in range(5)]
    ltp = [24000.0, 24100.0, 23950.0, 24050.0, 24050.0]   # O24000 H24100 L23950 C24050
    o = realized_outcomes({"ts": ts, "ltp": ltp}, max_pain=24000.0, pin_pts=60.0, resample_s=1)
    assert o["day_range"] == 150.0                         # 24100 - 23950
    assert o["range_pct"] == 0.62                          # 150/24000 -> 0.62%
    assert o["trend_proxy"] == 0.333                       # |24050-24000|/150
    assert o["pin_dist_pts"] == 50.0                       # |close - max_pain|
    # time within 60pts of 24000: intervals starting at 24000, 23950, 24050 (3 of 4)
    assert o["pin_time_frac"] == 0.75
    assert o["realized_vol"] >= 0.0


def test_realized_outcomes_too_short_returns_none():
    assert realized_outcomes({"ts": [0], "ltp": [1.0]}, max_pain=1.0) is None
