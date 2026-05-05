"""Test 4 — Cost impact should trigger a cost warning."""

from __future__ import annotations

from app.strategy_engine.backtest.costs import CostSettings
from app.strategy_engine.truth import evaluate_strategy_truth
from tests.strategy_engine.truth.conftest import (
    make_backtest_result,
    make_reliability,
    make_strategy,
)


def test_explicit_pre_cost_pnl_above_post_cost_fires_cost_warning() -> None:
    """Caller-supplied pre_cost_pnl > 20 % above post-cost → cost warning."""
    backtest = make_backtest_result(total_pnl=1000.0)
    reliability = make_reliability(backtest)

    report = evaluate_strategy_truth(
        strategy=make_strategy(),
        reliability=reliability,
        cost_settings=CostSettings(
            fixed_cost=20.0, percent_cost=0.05, slippage_percent=0.05
        ),
        pre_cost_pnl=2000.0,  # half of gross was eaten by costs
    )

    assert report.cost_warnings, "expected cost bucket to fire"
    assert any(
        "Cost-adjusted performance is weak" in w for w in report.cost_warnings
    )
    assert "Cost-impact risk" in report.weaknesses


def test_marginal_pf_with_costs_fires_heuristic_cost_warning() -> None:
    """No pre_cost_pnl supplied; profit factor is marginal AND costs > 0."""
    backtest = make_backtest_result(profit_factor=1.15)
    reliability = make_reliability(backtest)

    report = evaluate_strategy_truth(
        strategy=make_strategy(),
        reliability=reliability,
        cost_settings=CostSettings(
            fixed_cost=20.0, percent_cost=0.05, slippage_percent=0.05
        ),
    )

    assert any(
        "fees and slippage may remove most profits" in w
        for w in report.cost_warnings
    )


def test_no_cost_warning_when_strategy_clears_marginal_profit_factor() -> None:
    """Strong profit factor → marginal-cost heuristic does not fire."""
    backtest = make_backtest_result(profit_factor=2.0)
    reliability = make_reliability(backtest)

    report = evaluate_strategy_truth(
        strategy=make_strategy(),
        reliability=reliability,
        cost_settings=CostSettings(
            fixed_cost=20.0, percent_cost=0.05, slippage_percent=0.05
        ),
    )

    assert report.cost_warnings == ()
