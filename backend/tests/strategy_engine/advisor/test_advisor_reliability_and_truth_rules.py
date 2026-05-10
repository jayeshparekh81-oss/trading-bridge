"""Reliability + truth rules.

    low trust score   -> paper trading recommendation
    poor truth score  -> do NOT recommend live trading
    overfitting flag  -> overfitting warning
"""

from __future__ import annotations

from app.strategy_engine.advisor import AdviceCategory, generate_advice
from tests.strategy_engine.advisor.conftest import (
    make_backtest_result,
    make_oos,
    make_reliability,
    make_sensitivity,
    make_strategy,
    make_truth_report,
)


def test_low_trust_score_triggers_paper_trading_advice() -> None:
    """A low trust score (< 70) recommends paper trading."""
    backtest = make_backtest_result(total_trades=15, profit_factor=0.9)
    reliability = make_reliability(backtest)

    report = generate_advice(strategy=make_strategy(), reliability=reliability)

    low_trust = [
        a for a in report.advice if a.category == AdviceCategory.LOW_TRUST_SCORE
    ]
    assert len(low_trust) == 1
    assert "Paper trade extensively" in low_trust[0].message
    # Live recommendation is off whenever trust is low.
    assert report.live_trading_recommended is False


def test_poor_truth_score_disables_live_recommendation() -> None:
    """Truth score below the poor-threshold blocks live trading."""
    truth = make_truth_report(truth_score=40)

    report = generate_advice(
        strategy=make_strategy(),
        truth=truth,
    )

    poor_truth = [
        a for a in report.advice if a.category == AdviceCategory.POOR_TRUTH_SCORE
    ]
    assert poor_truth
    assert report.live_trading_recommended is False


def test_truth_overfitting_warning_propagates_to_advisor() -> None:
    """Truth's overfitting bucket fires the advisor's overfitting advice."""
    truth = make_truth_report(truth_score=72, overfitting=True)

    report = generate_advice(strategy=make_strategy(), truth=truth)

    overfit = [
        a for a in report.advice if a.category == AdviceCategory.OVERFITTING
    ]
    assert len(overfit) == 1
    assert "Simplify the strategy" in overfit[0].message


def test_clean_strategy_recommends_live_when_all_signals_strong() -> None:
    """All-green inputs → live recommendation true."""
    backtest = make_backtest_result(
        total_trades=120,
        win_rate=0.58,
        average_win=250.0,
        average_loss=180.0,
        profit_factor=1.8,
        max_drawdown=0.12,
    )
    reliability = make_reliability(
        backtest,
        out_of_sample=make_oos(degradation_percent=0.05),
        sensitivity=make_sensitivity(fragile=False),
    )
    truth = make_truth_report(truth_score=92)

    report = generate_advice(
        strategy=make_strategy(),
        backtest=backtest,
        reliability=reliability,
        truth=truth,
    )

    assert report.paper_trading_recommended is True
    assert report.live_trading_recommended is True
