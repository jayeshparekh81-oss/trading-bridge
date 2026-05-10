"""Test 1 — 95 % win rate but poor risk/reward should produce warning."""

from __future__ import annotations

from app.strategy_engine.backtest.costs import CostSettings
from app.strategy_engine.truth import evaluate_strategy_truth
from tests.strategy_engine.truth.conftest import (
    make_backtest_result,
    make_reliability,
    make_strategy,
)


def test_high_win_rate_with_dominant_avg_loss_fires_fake_backtest_warning() -> None:
    """Strategy wins 95 % of the time but loses big when it loses.

    avg_loss is 4x avg_win, so the asymmetry trap fires AND the
    high-win-rate trap fires (because the profit factor cushion isn't
    met). Both deductions land in the fakeBacktest bucket.
    """
    backtest = make_backtest_result(
        win_rate=0.95,
        total_trades=60,
        average_win=100.0,
        average_loss=400.0,
        profit_factor=1.1,
        max_drawdown=0.18,
    )
    reliability = make_reliability(backtest)

    report = evaluate_strategy_truth(
        strategy=make_strategy(),
        reliability=reliability,
        cost_settings=CostSettings(
            fixed_cost=20.0, percent_cost=0.03, slippage_percent=0.05
        ),
    )

    assert report.fake_backtest_warnings, "expected fake-backtest bucket to be populated"
    assert any("Win rate is high" in w for w in report.fake_backtest_warnings)
    assert any(
        "Average loss" in w and "average win" in w
        for w in report.fake_backtest_warnings
    )
    assert "High win-rate trap" in report.weaknesses
    assert "Average loss dominates average win" in report.weaknesses
    # The strategy is clearly suspect — score must drop into D/F.
    assert report.truth_score < 55
    assert report.grade in {"D", "F"}
