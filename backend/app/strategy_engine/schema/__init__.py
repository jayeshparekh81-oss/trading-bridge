"""Pydantic models for the strategy-engine contracts.

This sub-package holds the JSON-serialisable shapes that flow between
the builder UI, the indicator registry, the backtest engine, the
reliability engine, the AI advisor, the Pine importer, and (eventually)
the execution bridge. Keep these models pure data — no DB session, no
broker call, no LLM dependency — so every later sub-system can validate
its input/output independently.
"""

from __future__ import annotations

from app.strategy_engine.schema.indicator import (
    IndicatorChartType,
    IndicatorDifficulty,
    IndicatorMetadata,
    IndicatorStatus,
    InputSpec,
    InputType,
)
from app.strategy_engine.schema.ohlcv import Candle, PriceSource
from app.strategy_engine.schema.strategy import (
    CandleCondition,
    CandlePattern,
    Condition,
    EntryRules,
    ExecutionConfig,
    ExecutionMode,
    ExitRules,
    IndicatorCondition,
    IndicatorConditionOp,
    IndicatorConfig,
    OrderType,
    PartialExit,
    PriceCondition,
    PriceConditionOp,
    ProductType,
    RiskRules,
    Side,
    StrategyJSON,
    StrategyMode,
    TimeCondition,
    TimeConditionOp,
)

__all__ = [
    "Candle",
    "CandleCondition",
    "CandlePattern",
    "Condition",
    "EntryRules",
    "ExecutionConfig",
    "ExecutionMode",
    "ExitRules",
    "IndicatorChartType",
    "IndicatorCondition",
    "IndicatorConditionOp",
    "IndicatorConfig",
    "IndicatorDifficulty",
    "IndicatorMetadata",
    "IndicatorStatus",
    "InputSpec",
    "InputType",
    "OrderType",
    "PartialExit",
    "PriceCondition",
    "PriceConditionOp",
    "PriceSource",
    "ProductType",
    "RiskRules",
    "Side",
    "StrategyJSON",
    "StrategyMode",
    "TimeCondition",
    "TimeConditionOp",
]
