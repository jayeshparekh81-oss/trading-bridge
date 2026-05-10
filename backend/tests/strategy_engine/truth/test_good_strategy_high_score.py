"""Test 5 — A good strategy should get a better truth score."""

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


def test_clean_strategy_lands_in_grade_a_with_no_warnings() -> None:
    """No deductions = score 100, grade A, verdict 'Ready for paper trading'."""
    backtest = make_backtest_result(
        total_trades=120,
        win_rate=0.58,
        average_win=250.0,
        average_loss=180.0,
        profit_factor=1.8,
        max_drawdown=0.12,
        total_pnl=12_000.0,
    )
    reliability = make_reliability(
        backtest,
        out_of_sample=make_oos(degradation_percent=0.05),
        sensitivity=make_sensitivity(fragile=False),
    )

    report = evaluate_strategy_truth(
        strategy=make_strategy(),
        reliability=reliability,
        cost_settings=CostSettings(
            fixed_cost=20.0, percent_cost=0.03, slippage_percent=0.05
        ),
    )

    assert report.truth_score == 100
    assert report.grade == "A"
    assert report.verdict == "Ready for paper trading"
    assert report.risk_level == "low"
    assert report.fake_backtest_warnings == ()
    assert report.overfitting_warnings == ()
    assert report.execution_warnings == ()
    assert report.cost_warnings == ()
    # Strengths are populated when the corresponding good-condition holds.
    assert "Sufficient trade count for statistical confidence" in report.strengths
    assert "Strong profit factor" in report.strengths
    assert "Out-of-sample performance held up" in report.strengths
    assert "Robust to ±20 % parameter perturbations" in report.strengths


def test_clean_strategy_outscores_a_strategy_with_a_single_red_flag() -> None:
    """Adding any deduction must lower the score relative to the clean baseline."""
    cost_settings = CostSettings(
        fixed_cost=20.0, percent_cost=0.03, slippage_percent=0.05
    )

    clean = evaluate_strategy_truth(
        strategy=make_strategy(),
        reliability=make_reliability(
            make_backtest_result(
                total_trades=120,
                win_rate=0.58,
                average_win=250.0,
                average_loss=180.0,
                profit_factor=1.8,
                max_drawdown=0.12,
            ),
            sensitivity=make_sensitivity(fragile=False),
        ),
        cost_settings=cost_settings,
    )

    high_dd = evaluate_strategy_truth(
        strategy=make_strategy(),
        reliability=make_reliability(
            make_backtest_result(
                total_trades=120,
                win_rate=0.58,
                average_win=250.0,
                average_loss=180.0,
                profit_factor=1.8,
                max_drawdown=0.45,  # > 30 % threshold
            ),
            sensitivity=make_sensitivity(fragile=False),
        ),
        cost_settings=cost_settings,
    )

    assert high_dd.truth_score < clean.truth_score
    assert "High max drawdown" in high_dd.weaknesses
