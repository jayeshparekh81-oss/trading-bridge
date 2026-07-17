"""Walk-forward validation harness — leak-proofs + statistics guards.

The two leaks that would silently invalidate everything: test-window data influencing
the train-window CHOICE, and a boundary-straddling trade leaking across the split. Both
are pinned here, plus the null-test calibration and Deflated-Sharpe trial deflation.
"""

from __future__ import annotations

import math

import pytest

import research.walkforward as W
from research.walkforward import (
    Split,
    SweepSpec,
    Trade,
    deflated_sharpe,
    embargo_test,
    expected_max_sharpe,
    perturbation_check,
    plateau_report,
    permutation_null,
    profit_factor,
    purge_train,
    sweep_curve,
    walk_forward_splits,
    walk_forward_sweep,
)

DAYS = ["2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16"]
NS = W.NS


def _open(day):
    return W._day_open_ns(day)


# ============================ 1. splitter ====================================
def test_anchored_expands_and_test_is_always_later():
    sp = walk_forward_splits(DAYS, scheme="anchored", train_size=2, test_size=1)
    assert [s.train_days for s in sp] == [("2026-07-13", "2026-07-14"),
                                          ("2026-07-13", "2026-07-14", "2026-07-15")]
    assert [s.test_days for s in sp] == [("2026-07-15",), ("2026-07-16",)]
    for s in sp:                                    # boundary is strict: test strictly after train
        assert max(s.train_days) < min(s.test_days)


def test_rolling_has_fixed_width_train():
    sp = walk_forward_splits(DAYS, scheme="rolling", train_size=2, test_size=1)
    assert all(len(s.train_days) == 2 for s in sp)
    assert sp[1].train_days == ("2026-07-14", "2026-07-15")   # window slid, not expanded


def test_time_order_is_sacred():
    with pytest.raises(ValueError):
        walk_forward_splits(["2026-07-15", "2026-07-13"], scheme="anchored", train_size=1)


def test_embargo_drops_days_between_train_and_test():
    sp = walk_forward_splits(["d1", "d2", "d3", "d4", "d5"] and DAYS + ["2026-07-17"],
                             scheme="anchored", train_size=2, test_size=1, embargo_days=1)
    assert sp[0].train_days == ("2026-07-13", "2026-07-14")
    assert sp[0].embargo_days == ("2026-07-15",)
    assert sp[0].test_days == ("2026-07-16",)      # the embargo day is skipped


# --- LEAK GUARD 1: test data cannot influence the train choice ---------------
def test_test_window_cannot_influence_train_choice():
    """param=1 is best on TRAIN days, param=2 is best on TEST day. The sweep MUST pick 1
    (train-best); picking 2 would prove the test window leaked into the choice."""
    train_days, test_day = {"2026-07-13", "2026-07-14"}, "2026-07-15"

    def ev(param, days):
        out = []
        for d in days:
            fav = 1 if d in train_days else 2
            r = 1.0 if param == fav else -0.5
            out.append(Trade(d, _open(d) + 1, _open(d) + 2, r))
        return out

    spec = SweepSpec("p", (1, 2))
    res = walk_forward_sweep(["2026-07-13", "2026-07-14", "2026-07-15"], ev, spec,
                             scheme="anchored", train_size=2, test_size=1)
    assert res.per_split[0]["chosen_value"] == 1           # train-best, NOT test-best (2)
    assert res.per_split[0]["test_profit_factor"] == 0.0   # param 1 loses on test -> honest OOS


# --- LEAK GUARD 2: a boundary-straddling trade is purged ---------------------
def test_purge_drops_trade_open_into_test_window():
    test_start = _open("2026-07-15")
    straddler = Trade("2026-07-14", test_start - 10, test_start + 10, 5.0)   # exits AFTER test opens
    clean = Trade("2026-07-14", test_start - 100, test_start - 10, 1.0)      # closes before
    kept = purge_train([straddler, clean], test_start)
    assert kept == [clean]                                 # the straddler is removed


def test_embargo_drops_test_trades_near_boundary():
    test_start = _open("2026-07-15")
    near = Trade("2026-07-15", test_start + 5, test_start + 6, 1.0)
    far = Trade("2026-07-15", test_start + 10 * NS, test_start + 11 * NS, 1.0)
    kept = embargo_test([near, far], test_start, embargo_ns=NS)
    assert kept == [far]                                   # the near-boundary trade is embargoed


# ============================ 2. sweep / plateau =============================
def test_sweep_curve_is_full_and_ordered():
    spec = SweepSpec("k", (0.0, 0.5, 1.0))
    curve = sweep_curve(spec, lambda v: v * 10)
    assert curve == [(0.0, 0.0), (0.5, 5.0), (1.0, 10.0)]  # every point, in order


def test_plateau_vs_spike():
    flat = [(0, 1.0), (1, 1.9), (2, 2.0), (3, 1.9), (4, 1.0)]   # broad top
    rep = plateau_report(flat)
    assert rep["best_value"] == 2 and rep["is_spike"] is False and rep["plateau_width"] >= 3
    spike = [(0, 0.1), (1, 0.1), (2, 5.0), (3, 0.1), (4, 0.1)]  # lone spike
    rep2 = plateau_report(spike)
    assert rep2["best_value"] == 2 and rep2["is_spike"] is True and rep2["plateau_width"] == 1


def test_perturbation_flags_fragile_point():
    # smooth function: chosen point sits within its neighbourhood -> not fragile
    stable = perturbation_check(1.0, lambda v: 2.0 - abs(v - 1.0))
    assert stable["within_2sd"] is True
    # a needle: score collapses off the exact point -> fragile
    spike = perturbation_check(1.0, lambda v: 100.0 if abs(v - 1.0) < 1e-9 else 0.0)
    assert spike["fragile"] is True


# ============================ 3. permutation null ============================
def _edge_ev(center):
    def ev(param, days):
        out = []
        for d in days:
            mu = 1.0 if param == center else -0.3
            for i in range(6):
                out.append(Trade(d, _open(d) + i, _open(d) + i + 1, mu + 0.05 * W._det_noise(d, i)))
        return out
    return ev


def test_permutation_null_real_edge_beats_floor():
    spec = SweepSpec("p", (0, 1, 2))
    wf = dict(scheme="anchored", train_size=2, test_size=1)
    perm = permutation_null(DAYS, _edge_ev(1), spec, n_perm=100, seed=7, wf_kwargs=wf)
    assert perm["beats_floor"] is True and perm["p_value"] < 0.05     # real signal clears noise


def test_permutation_null_no_edge_does_not_beat_floor():
    """r independent of the knob (pure noise) -> real must NOT clear the null floor and the
    permutation p-value must be non-significant. This is the false-positive guard that
    killed loss-autocorrelation: on noise, the sweep looks no better than its own shuffle."""
    def ev(param, days):
        return [Trade(d, _open(d) + i, _open(d) + i + 1, W._det_noise(d, i))
                for d in days for i in range(40)]      # param-independent, ample sample
    spec = SweepSpec("p", (0, 1, 2))
    wf = dict(scheme="anchored", train_size=2, test_size=1)
    perm = permutation_null(DAYS, ev, spec, n_perm=100, seed=3, wf_kwargs=wf)
    assert perm["beats_floor"] is False and perm["p_value"] > 0.05


def test_permutation_is_deterministic():
    spec = SweepSpec("p", (0, 1, 2))
    wf = dict(scheme="anchored", train_size=2, test_size=1)
    a = permutation_null(DAYS, _edge_ev(1), spec, n_perm=50, seed=11, wf_kwargs=wf)
    b = permutation_null(DAYS, _edge_ev(1), spec, n_perm=50, seed=11, wf_kwargs=wf)
    assert a == b                                           # same seed -> identical


# ============================ 4. deflated Sharpe =============================
def test_norm_cdf_ppf_roundtrip():
    for x in (-2.0, -0.5, 0.3, 1.64, 2.33):
        assert W._norm_ppf(W._norm_cdf(x)) == pytest.approx(x, abs=1e-6)


def test_expected_max_sharpe_grows_with_trials():
    v = 0.25
    assert expected_max_sharpe(2, v) < expected_max_sharpe(10, v) < expected_max_sharpe(100, v)


def test_more_trials_deflates_dsr():
    returns = [0.8, -0.4, 1.2, -0.3, 0.9, -0.5, 1.1, 0.2, -0.1, 0.7]
    trials = [0.1, 0.3, 0.05, 0.25, 0.4]                   # spread -> sr_variance > 0
    few = deflated_sharpe(returns, n_trials=2, trial_sharpes=trials)
    many = deflated_sharpe(returns, n_trials=200, trial_sharpes=trials)
    assert many["sr0_expected_max"] > few["sr0_expected_max"]   # more trials -> higher bar
    assert many["dsr"] < few["dsr"]                             # -> harder to pass


def test_dsr_reports_on_short_series_safely():
    assert deflated_sharpe([1.0], n_trials=5)["dsr"] is None
