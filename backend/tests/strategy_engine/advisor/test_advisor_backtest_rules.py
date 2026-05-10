"""Backtest-derived rules.

    high win rate    -> caution
    high drawdown    -> reduce risk suggestion
"""

from __future__ import annotations

from app.strategy_engine.advisor import AdviceCategory, generate_advice
from tests.strategy_engine.advisor.conftest import (
    make_backtest_result,
    make_strategy,
)


def test_high_win_rate_triggers_caution_advice() -> None:
    backtest = make_backtest_result(win_rate=0.95, total_trades=80)

    report = generate_advice(strategy=make_strategy(), backtest=backtest)

    caution = [
        a for a in report.advice if a.category == AdviceCategory.HIGH_WIN_RATE_CAUTION
    ]
    assert len(caution) == 1
    assert "95 % win rate" in caution[0].message
    assert "reliability and truth checks" in caution[0].message


def test_high_drawdown_triggers_risk_advice() -> None:
    backtest = make_backtest_result(max_drawdown=0.45)

    report = generate_advice(strategy=make_strategy(), backtest=backtest)

    drawdown = [
        a for a in report.advice if a.category == AdviceCategory.HIGH_DRAWDOWN
    ]
    assert len(drawdown) == 1
    assert "45.0 %" in drawdown[0].message
    assert "Reduce position size" in drawdown[0].message


def test_normal_backtest_emits_no_backtest_specific_advice() -> None:
    backtest = make_backtest_result(win_rate=0.55, max_drawdown=0.10)

    report = generate_advice(strategy=make_strategy(), backtest=backtest)

    backtest_categories = {
        AdviceCategory.HIGH_WIN_RATE_CAUTION,
        AdviceCategory.HIGH_DRAWDOWN,
    }
    assert not any(a.category in backtest_categories for a in report.advice)
