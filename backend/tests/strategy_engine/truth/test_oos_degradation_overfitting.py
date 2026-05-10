"""Test 3 — Out-of-sample degradation should trigger an overfitting warning."""

from __future__ import annotations

from app.strategy_engine.backtest.costs import CostSettings
from app.strategy_engine.truth import evaluate_strategy_truth
from tests.strategy_engine.truth.conftest import (
    make_backtest_result,
    make_oos,
    make_reliability,
    make_sensitivity,
    make_strategy,
)


def test_oos_degradation_above_threshold_lands_in_overfitting_bucket() -> None:
    """30 % degradation > 25 % threshold → overfitting warning fires."""
    backtest = make_backtest_result()
    reliability = make_reliability(
        backtest,
        out_of_sample=make_oos(degradation_percent=0.30),
    )

    report = evaluate_strategy_truth(
        strategy=make_strategy(),
        reliability=reliability,
        cost_settings=CostSettings(
            fixed_cost=20.0, percent_cost=0.03, slippage_percent=0.05
        ),
    )

    assert report.overfitting_warnings, "expected overfitting bucket to fire"
    assert any(
        "out-of-sample result dropped" in w.lower()
        for w in report.overfitting_warnings
    )
    assert "Out-of-sample degradation" in report.weaknesses
    # Cost / fake-backtest buckets stay clean for this strategy.
    assert not report.fake_backtest_warnings


def test_oos_within_threshold_does_not_fire_overfitting() -> None:
    """10 % degradation ≤ 25 % threshold → no warning."""
    reliability = make_reliability(
        make_backtest_result(),
        out_of_sample=make_oos(degradation_percent=0.10),
    )

    report = evaluate_strategy_truth(
        strategy=make_strategy(),
        reliability=reliability,
        cost_settings=CostSettings(
            fixed_cost=20.0, percent_cost=0.03, slippage_percent=0.05
        ),
    )

    assert report.overfitting_warnings == ()


def test_oos_and_fragile_stack_apply_extra_deduction() -> None:
    """Both signals firing yields a stronger penalty than either alone."""
    backtest = make_backtest_result()
    cost_settings = CostSettings(
        fixed_cost=20.0, percent_cost=0.03, slippage_percent=0.05
    )

    only_oos = evaluate_strategy_truth(
        strategy=make_strategy(),
        reliability=make_reliability(
            backtest, out_of_sample=make_oos(degradation_percent=0.30)
        ),
        cost_settings=cost_settings,
    )
    both = evaluate_strategy_truth(
        strategy=make_strategy(),
        reliability=make_reliability(
            backtest,
            out_of_sample=make_oos(degradation_percent=0.30),
            sensitivity=make_sensitivity(fragile=True),
        ),
        cost_settings=cost_settings,
    )

    assert both.truth_score < only_oos.truth_score
    # The stack-penalty message lives in the overfitting bucket.
    assert any("combined evidence" in w.lower() for w in both.overfitting_warnings)
