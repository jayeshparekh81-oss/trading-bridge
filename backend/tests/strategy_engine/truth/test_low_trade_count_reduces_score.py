"""Test 2 — Low trade count should reduce the truth score."""

from __future__ import annotations

from app.strategy_engine.backtest.costs import CostSettings
from app.strategy_engine.truth import evaluate_strategy_truth
from tests.strategy_engine.truth.conftest import (
    make_backtest_result,
    make_reliability,
    make_strategy,
)


def test_low_trade_count_drops_truth_score_and_emits_warning() -> None:
    """A handful of trades is statistically noisy regardless of metrics.

    Compare a baseline 50-trade backtest to a 5-trade one that is
    otherwise identical. The low-trade run must score strictly lower
    AND emit the low-trade-count warning into the fakeBacktest bucket.
    """
    cost_settings = CostSettings(
        fixed_cost=20.0, percent_cost=0.03, slippage_percent=0.05
    )

    baseline = evaluate_strategy_truth(
        strategy=make_strategy(),
        reliability=make_reliability(make_backtest_result(total_trades=50)),
        cost_settings=cost_settings,
    )
    sparse = evaluate_strategy_truth(
        strategy=make_strategy(),
        reliability=make_reliability(make_backtest_result(total_trades=5)),
        cost_settings=cost_settings,
    )

    assert sparse.truth_score < baseline.truth_score
    assert any("trade(s)" in w for w in sparse.fake_backtest_warnings)
    assert "Low trade count" in sparse.weaknesses
    # Baseline (50 trades) does NOT emit the low-count warning.
    assert not any("trade(s)" in w for w in baseline.fake_backtest_warnings)
