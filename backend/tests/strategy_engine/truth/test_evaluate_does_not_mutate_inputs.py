"""Test 6 — Truth Engine must not mutate backtest results.

Inputs are frozen Pydantic models, so accidental mutation is impossible
by construction. This test pins the contract anyway: round-trip the
backtest's JSON dump and assert it survives the call unchanged. If a
future refactor introduces a non-frozen helper that does mutate, this
test catches it before the change ships.
"""

from __future__ import annotations

from app.strategy_engine.backtest.costs import CostSettings
from app.strategy_engine.backtest.runner import AmbiguityMode
from app.strategy_engine.truth import evaluate_strategy_truth
from tests.strategy_engine.truth.conftest import (
    make_backtest_result,
    make_oos,
    make_reliability,
    make_sensitivity,
    make_strategy,
)


def test_evaluate_does_not_mutate_backtest_or_reliability() -> None:
    backtest = make_backtest_result(
        total_trades=20,  # triggers low-trade-count
        win_rate=0.92,    # triggers high-win-rate
        average_win=80.0,
        average_loss=300.0,  # triggers asymmetry + bad R:R
        profit_factor=0.9,   # also unprofitable
        max_drawdown=0.40,   # triggers high drawdown
    )
    reliability = make_reliability(
        backtest,
        out_of_sample=make_oos(degradation_percent=0.45),
        sensitivity=make_sensitivity(fragile=True),
    )
    backtest_snapshot = backtest.model_dump_json()
    reliability_snapshot = reliability.model_dump_json()

    report = evaluate_strategy_truth(
        strategy=make_strategy(),
        reliability=reliability,
        cost_settings=CostSettings(
            fixed_cost=20.0, percent_cost=0.05, slippage_percent=0.05
        ),
        ambiguity_mode=AmbiguityMode.OPTIMISTIC,
        pre_cost_pnl=5_000.0,
    )

    # Deep-equality via JSON round-trip — anything mutated would diff.
    assert backtest.model_dump_json() == backtest_snapshot
    assert reliability.model_dump_json() == reliability_snapshot
    # Sanity: a strategy this bad should land in F territory.
    assert report.grade == "F"
    assert report.risk_level == "extreme"
