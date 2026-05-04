"""Deterministic strategy-evaluation engines.

Phase 2 of the AI trading system. Pure-Python evaluators built on top of
the Phase 1 schemas. No I/O, no global mutable state — engines accept
position state + indicator values + bars and return decisions.

The final boundary::

    PositionState / open_position / update_on_candle / apply_partial_exit /
        close_position / PartialExitRecord
    detect_candle_pattern
    evaluate_time_condition
    evaluate_price_condition
    evaluate_indicator_condition
    evaluate_entry / EntryDecision
    evaluate_exit / ExitEvent / ExitType
    evaluate_risk / RiskAssessment / RiskMessage / RiskRuntimeStats / RiskSeverity
"""

from __future__ import annotations

from app.strategy_engine.engines.candle_pattern import detect_candle_pattern
from app.strategy_engine.engines.entry import EntryDecision, evaluate_entry
from app.strategy_engine.engines.exit import ExitEvent, ExitType, evaluate_exit
from app.strategy_engine.engines.indicator_eval import evaluate_indicator_condition
from app.strategy_engine.engines.position import (
    PartialExitRecord,
    PositionState,
    apply_partial_exit,
    close_position,
    open_position,
    update_on_candle,
)
from app.strategy_engine.engines.price_condition import evaluate_price_condition
from app.strategy_engine.engines.risk import (
    RiskAssessment,
    RiskMessage,
    RiskRuntimeStats,
    RiskSeverity,
    evaluate_risk,
)
from app.strategy_engine.engines.time_condition import evaluate_time_condition

__all__ = [
    "EntryDecision",
    "ExitEvent",
    "ExitType",
    "PartialExitRecord",
    "PositionState",
    "RiskAssessment",
    "RiskMessage",
    "RiskRuntimeStats",
    "RiskSeverity",
    "apply_partial_exit",
    "close_position",
    "detect_candle_pattern",
    "evaluate_entry",
    "evaluate_exit",
    "evaluate_indicator_condition",
    "evaluate_price_condition",
    "evaluate_risk",
    "evaluate_time_condition",
    "open_position",
    "update_on_candle",
]
