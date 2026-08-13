"""Sweep 2.0 budget guard + plateau + perturbation (Module R6)."""

from __future__ import annotations

import pytest

from signals.perturb import perturb
from signals.sweep import plateau_analysis, sweep


def test_budget_guard_rejects_more_than_three_params():
    specs = [(f"a.{i}", [1, 2]) for i in range(4)]
    with pytest.raises(ValueError, match="budget guard"):
        sweep(specs, run_fn=lambda ov: 0.0)


def test_sweep_runs_grid_and_finds_plateau():
    # metric peaks in a broad plateau around threshold ~30-40
    def run_fn(ov):
        thr = ov["signal"]["fire_threshold"]
        return 10.0 - abs(thr - 35) * 0.1     # flat-topped around 35
    res = sweep([("fire_threshold", [20, 30, 35, 40, 50])], run_fn)
    assert len(res["results"]) == 5
    assert res["plateau"]["is_plateau"] is True
    assert res["plateau"]["plateau_size"] >= 2


def test_plateau_vs_sharp_spike():
    flat = [{"combo": {}, "metric": m} for m in [9.8, 10.0, 9.9]]
    assert plateau_analysis(flat)["is_plateau"] is True
    spike = [{"combo": {}, "metric": m} for m in [1.0, 10.0, 1.0]]
    assert plateau_analysis(spike, rel_tol=0.1)["plateau_size"] == 1
    assert plateau_analysis(spike, rel_tol=0.1)["is_plateau"] is False


def test_perturb_robust_vs_fragile():
    robust = perturb([("x", 5.0, 1.0)], run_fn=lambda ov: 10.0)   # metric constant
    assert robust["robust"] is True
    # fragile: metric collapses when x moves off 5.0
    def fragile_fn(ov):
        return 10.0 if ov["signal"]["x"] == 5.0 else 1.0
    frag = perturb([("x", 5.0, 1.0)], run_fn=fragile_fn, tolerance=0.2)
    assert frag["robust"] is False
