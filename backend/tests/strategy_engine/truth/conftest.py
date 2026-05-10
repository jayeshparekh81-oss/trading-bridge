"""Helpers for the Truth Engine tests.

The truth engine is pure and consumes Phase 3/4 outputs without
touching the simulator, so these fixtures fabricate fully-formed
:class:`BacktestResult` / :class:`OOSResult` / :class:`SensitivityResult`
objects directly. That keeps each test under 100 ms and lets us
assert against exact metric inputs (a 95 % win rate, 50 trades, etc.)
without engineering a candle stream that produces them.
"""

from __future__ import annotations

from typing import Any

from app.strategy_engine.backtest.runner import BacktestResult
from app.strategy_engine.reliability.out_of_sample import OOSResult
from app.strategy_engine.reliability.parameter_sensitivity import (
    SensitivityResult,
)
from app.strategy_engine.reliability.reliability_report import ReliabilityReport
from app.strategy_engine.reliability.trust_score import calculate_trust_score
from app.strategy_engine.schema.strategy import StrategyJSON


def make_backtest_result(
    *,
    total_pnl: float = 1000.0,
    total_return_percent: float = 10.0,
    win_rate: float = 0.55,
    total_trades: int = 50,
    average_win: float = 200.0,
    average_loss: float = 150.0,
    largest_win: float | None = None,
    largest_loss: float | None = None,
    max_drawdown: float = 0.10,
    profit_factor: float = 1.5,
    expectancy: float = 20.0,
) -> BacktestResult:
    """Synthesise a :class:`BacktestResult` with the metrics that matter.

    ``equity_curve``, ``trades``, and ``warnings`` default to empty
    lists — the truth engine doesn't inspect them.
    """
    return BacktestResult(
        total_pnl=total_pnl,
        total_return_percent=total_return_percent,
        win_rate=win_rate,
        loss_rate=max(0.0, min(1.0, 1.0 - win_rate)),
        total_trades=total_trades,
        average_win=average_win,
        average_loss=average_loss,
        largest_win=largest_win if largest_win is not None else average_win * 2,
        largest_loss=largest_loss if largest_loss is not None else average_loss * 2,
        max_drawdown=max_drawdown,
        profit_factor=profit_factor,
        expectancy=expectancy,
        equity_curve=[],
        trades=[],
        warnings=[],
    )


def make_oos(
    *, degradation_percent: float, training: BacktestResult | None = None
) -> OOSResult:
    """Build an :class:`OOSResult` with the requested degradation."""
    train = training if training is not None else make_backtest_result()
    test = make_backtest_result()
    return OOSResult(
        training=train,
        testing=test,
        degradation_percent=degradation_percent,
        warning="",
    )


def make_sensitivity(*, fragile: bool, base_score: int = 70) -> SensitivityResult:
    """Build a :class:`SensitivityResult` with the requested fragility."""
    return SensitivityResult(
        base_score=base_score,
        tested_variants=(),
        fragile=fragile,
        stability_score=0.3 if fragile else 0.9,
        warning="",
    )


def make_reliability(
    backtest: BacktestResult,
    *,
    out_of_sample: OOSResult | None = None,
    sensitivity: SensitivityResult | None = None,
) -> ReliabilityReport:
    """Build a :class:`ReliabilityReport` with a real, computed trust score.

    The trust score is computed via :func:`calculate_trust_score` so
    Truth Engine tests cross-reference real Phase 4 logic — handy when
    the truth engine starts surfacing the trust grade alongside its
    own (Phase 9 stretch).
    """
    trust = calculate_trust_score(
        backtest,
        oos_degradation=(out_of_sample.degradation_percent if out_of_sample else None),
        sensitivity_fragile=(sensitivity.fragile if sensitivity else None),
    )
    return ReliabilityReport(
        backtest=backtest,
        trust_score=trust,
        out_of_sample=out_of_sample,
        walk_forward=None,
        sensitivity=sensitivity,
    )


def make_strategy(**overrides: Any) -> StrategyJSON:
    """Minimal valid StrategyJSON — used as the ``strategy`` argument."""
    payload: dict[str, Any] = {
        "id": "phase6_truth_test",
        "name": "Phase 6 truth test",
        "mode": "expert",
        "indicators": [
            {"id": "ema_20", "type": "ema", "params": {"period": 20}},
        ],
        "entry": {
            "side": "BUY",
            "operator": "AND",
            "conditions": [
                {"type": "indicator", "left": "ema_20", "op": ">", "value": 100.0}
            ],
        },
        "exit": {"targetPercent": 2.0, "stopLossPercent": 1.0},
        "risk": {},
        "execution": {
            "mode": "backtest",
            "orderType": "MARKET",
            "productType": "INTRADAY",
        },
    }
    payload.update(overrides)
    return StrategyJSON.model_validate(payload)
