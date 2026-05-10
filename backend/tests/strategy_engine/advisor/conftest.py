"""Helpers for the Phase 7 advisor + doctor tests.

Re-uses Phase 6's fabricated-result helpers (``make_backtest_result``,
``make_oos``, etc.) so the advisor tests assert against precise metric
inputs without engineering candle streams.
"""

from __future__ import annotations

from typing import Any

from app.strategy_engine.schema.strategy import StrategyJSON
from app.strategy_engine.truth.truth_score import TruthReport

# Pull the truth-test helpers transitively — they already produce
# fully-formed Phase 3/4 result objects that we can reuse here.
from tests.strategy_engine.truth.conftest import (
    make_backtest_result,
    make_oos,
    make_reliability,
    make_sensitivity,
)

__all__ = [
    "make_backtest_result",
    "make_oos",
    "make_reliability",
    "make_sensitivity",
    "make_strategy",
    "make_strategy_payload",
    "make_truth_report",
]


def make_strategy_payload(
    *,
    indicators: list[dict[str, Any]] | None = None,
    entry_block: dict[str, Any] | None = None,
    exit_block: dict[str, Any] | None = None,
    name: str = "Phase 7 advisor test",
) -> dict[str, Any]:
    """Raw dict shape for a StrategyJSON — easy to mutate per-test.

    When ``indicators`` is overridden but ``entry_block`` is not, the
    helper auto-rewrites the default entry condition to reference the
    first declared indicator. This keeps Phase 1's cross-reference
    validator happy without forcing every caller to spell out an entry
    block.
    """
    if indicators is None:
        indicators = [{"id": "ema_20", "type": "ema", "params": {"period": 20}}]
    if exit_block is None:
        exit_block = {"targetPercent": 2.0, "stopLossPercent": 1.0}
    if entry_block is None:
        entry_block = {
            "side": "BUY",
            "operator": "AND",
            "conditions": [
                {
                    "type": "indicator",
                    "left": indicators[0]["id"],
                    "op": ">",
                    "value": 100.0,
                }
            ],
        }
    return {
        "id": "phase7_advisor_test",
        "name": name,
        "mode": "expert",
        "indicators": indicators,
        "entry": entry_block,
        "exit": exit_block,
        "risk": {},
        "execution": {
            "mode": "backtest",
            "orderType": "MARKET",
            "productType": "INTRADAY",
        },
    }


def make_strategy(**overrides: Any) -> StrategyJSON:
    payload = make_strategy_payload(**overrides)
    return StrategyJSON.model_validate(payload)


def make_truth_report(
    *,
    truth_score: int = 90,
    overfitting: bool = False,
    cost_warning: bool = False,
) -> TruthReport:
    """Build a TruthReport directly. The advisor only reads the
    aggregate fields, so we don't need to invoke the truth engine."""
    grade_for_score = "A" if truth_score >= 85 else (
        "B" if truth_score >= 70 else (
            "C" if truth_score >= 55 else (
                "D" if truth_score >= 40 else "F"
            )
        )
    )
    return TruthReport(
        truth_score=truth_score,
        grade=grade_for_score,  # type: ignore[arg-type]
        verdict=(
            "Ready for paper trading"
            if truth_score >= 70
            else ("Needs improvement" if truth_score >= 40 else "Not ready")
        ),
        risk_level="low",
        fake_backtest_warnings=(),
        overfitting_warnings=("Overfitting risk",) if overfitting else (),
        execution_warnings=(),
        cost_warnings=("Cost impact",) if cost_warning else (),
        strengths=(),
        weaknesses=(),
        recommended_next_actions=(),
    )
