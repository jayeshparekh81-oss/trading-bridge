"""Schema tests for StrategyJSON + condition discriminated union."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from app.strategy_engine.schema.strategy import (
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

# Used in multiple tests below as a known-good base.
_VALID_STRATEGY_PAYLOAD: dict[str, object] = {
    "id": "strategy_001",
    "name": "EMA RSI Beginner",
    "mode": "beginner",
    "version": 1,
    "indicators": [
        {"id": "ema_20", "type": "ema", "params": {"period": 20, "source": "close"}},
        {"id": "ema_50", "type": "ema", "params": {"period": 50, "source": "close"}},
        {"id": "rsi_14", "type": "rsi", "params": {"period": 14, "source": "close"}},
    ],
    "entry": {
        "side": "BUY",
        "operator": "AND",
        "conditions": [
            {"type": "indicator", "left": "ema_20", "op": ">", "right": "ema_50"},
            {"type": "indicator", "left": "rsi_14", "op": "<", "value": 30},
        ],
    },
    "exit": {
        "targetPercent": 2,
        "stopLossPercent": 1,
        "trailingStopPercent": 0.5,
        "partialExits": [{"qtyPercent": 50, "targetPercent": 1}],
        "squareOffTime": "15:20",
    },
    "risk": {
        "maxDailyLossPercent": 2,
        "maxTradesPerDay": 5,
        "maxLossStreak": 3,
        "maxCapitalPerTradePercent": 10,
    },
    "execution": {
        "mode": "backtest",
        "orderType": "MARKET",
        "productType": "INTRADAY",
    },
}


def test_master_prompt_example_strategy_validates() -> None:
    """The example JSON shape from the master prompt must parse cleanly."""
    strategy = StrategyJSON.model_validate(_VALID_STRATEGY_PAYLOAD)
    assert strategy.id == "strategy_001"
    assert strategy.mode is StrategyMode.BEGINNER
    assert strategy.entry.side is Side.BUY
    assert strategy.exit.target_percent == 2.0
    assert strategy.exit.partial_exits[0].qty_percent == 50.0


def test_strategy_json_round_trip_via_alias() -> None:
    """Camel-case JSON in -> camel-case JSON out is loss-less."""
    strategy = StrategyJSON.model_validate(_VALID_STRATEGY_PAYLOAD)
    dumped = json.loads(strategy.model_dump_json(by_alias=True))
    assert dumped["exit"]["targetPercent"] == 2.0
    assert dumped["risk"]["maxDailyLossPercent"] == 2.0
    assert dumped["execution"]["orderType"] == "MARKET"


def test_indicator_ids_must_be_unique() -> None:
    payload = json.loads(json.dumps(_VALID_STRATEGY_PAYLOAD))
    payload["indicators"].append({"id": "ema_20", "type": "ema", "params": {"period": 99}})
    with pytest.raises(ValidationError) as excinfo:
        StrategyJSON.model_validate(payload)
    assert "Duplicate indicator ids" in str(excinfo.value)


def test_unknown_indicator_reference_rejected() -> None:
    payload = json.loads(json.dumps(_VALID_STRATEGY_PAYLOAD))
    payload["entry"]["conditions"][0]["left"] = "unknown_indicator"
    with pytest.raises(ValidationError) as excinfo:
        StrategyJSON.model_validate(payload)
    assert "not declared in 'indicators'" in str(excinfo.value)


def test_indicator_condition_requires_xor_right_or_value() -> None:
    with pytest.raises(ValidationError):
        IndicatorCondition(
            type="indicator",
            left="ema_20",
            op=IndicatorConditionOp.GT,
            right="ema_50",
            value=10,
        )
    with pytest.raises(ValidationError):
        IndicatorCondition(type="indicator", left="ema_20", op=IndicatorConditionOp.GT)


def test_crossover_requires_indicator_rhs_not_value() -> None:
    with pytest.raises(ValidationError) as excinfo:
        IndicatorCondition(
            type="indicator",
            left="ema_20",
            op=IndicatorConditionOp.CROSSOVER,
            value=50,
        )
    assert "crossover/crossunder" in str(excinfo.value)


def test_time_condition_between_requires_end() -> None:
    with pytest.raises(ValidationError):
        TimeCondition(type="time", op=TimeConditionOp.BETWEEN, value="09:15")


def test_time_condition_non_between_rejects_end() -> None:
    with pytest.raises(ValidationError):
        TimeCondition(type="time", op=TimeConditionOp.AFTER, value="09:15", end="15:30")


def test_price_condition_breakout_rejects_value() -> None:
    with pytest.raises(ValidationError):
        PriceCondition(type="price", op=PriceConditionOp.PREVIOUS_HIGH_BREAKOUT, value=100)


def test_price_condition_comparator_requires_value() -> None:
    with pytest.raises(ValidationError):
        PriceCondition(type="price", op=PriceConditionOp.GT)


def test_exit_rules_must_define_at_least_one_exit() -> None:
    with pytest.raises(ValidationError) as excinfo:
        ExitRules()
    assert "at least one exit primitive" in str(excinfo.value)


def test_exit_rules_squareofftime_alone_is_a_valid_exit() -> None:
    rules = ExitRules.model_validate({"squareOffTime": "15:20"})
    assert rules.square_off_time == "15:20"


def test_partial_exit_qty_in_range() -> None:
    PartialExit(qty_percent=50, target_percent=1)
    with pytest.raises(ValidationError):
        PartialExit(qty_percent=0, target_percent=1)
    with pytest.raises(ValidationError):
        PartialExit(qty_percent=101, target_percent=1)


def test_indicator_config_requires_lower_snake() -> None:
    IndicatorConfig(id="ema_20", type="ema", params={"period": 20})
    with pytest.raises(ValidationError):
        IndicatorConfig(id="EMA-20", type="ema")
    with pytest.raises(ValidationError):
        IndicatorConfig(id="ema_20", type="EMA")


def test_extra_fields_on_strategy_rejected() -> None:
    payload = json.loads(json.dumps(_VALID_STRATEGY_PAYLOAD))
    payload["unexpected"] = "nope"
    with pytest.raises(ValidationError):
        StrategyJSON.model_validate(payload)


def test_indicator_referenced_only_in_exit_is_validated() -> None:
    """An indicator id used solely in ``exit.indicatorExits`` must still
    appear in the top-level ``indicators`` list — covers the indicator-exit
    branch of the cross-reference validator.
    """
    # ``Any`` so the nested mutation below (replacing the condition's RHS
    # with an undeclared indicator id) doesn't have to fight mypy.
    payload: dict[str, Any] = {
        "id": "s2",
        "name": "exit-ref",
        "mode": "expert",
        "indicators": [
            {"id": "rsi_14", "type": "rsi", "params": {"period": 14}},
        ],
        "entry": {
            "side": "BUY",
            "operator": "AND",
            "conditions": [
                {"type": "price", "op": ">", "value": 100},
            ],
        },
        "exit": {
            "stopLossPercent": 1,
            "indicatorExits": [
                {"type": "indicator", "left": "rsi_14", "op": ">", "value": 70},
            ],
        },
        "execution": {
            "mode": "backtest",
            "orderType": "MARKET",
            "productType": "INTRADAY",
        },
    }
    strategy = StrategyJSON.model_validate(payload)
    assert strategy.exit.indicator_exits[0].type == "indicator"

    # Now replace the value-style condition with an indicator-vs-indicator
    # one whose RHS is undeclared — should fail the cross-reference check.
    payload["exit"]["indicatorExits"][0]["right"] = "ema_20"
    payload["exit"]["indicatorExits"][0].pop("value")
    with pytest.raises(ValidationError) as excinfo:
        StrategyJSON.model_validate(payload)
    assert "ema_20" in str(excinfo.value)


def test_construct_via_python_attribute_names() -> None:
    """``populate_by_name=True`` lets us build via snake_case kwargs too."""
    strategy = StrategyJSON(
        id="s1",
        name="N",
        mode=StrategyMode.EXPERT,
        indicators=[],
        entry=EntryRules(
            side=Side.BUY,
            conditions=[PriceCondition(type="price", op=PriceConditionOp.GT, value=100)],
        ),
        exit=ExitRules(stop_loss_percent=1.0),
        risk=RiskRules(max_trades_per_day=3),
        execution=ExecutionConfig(
            mode=ExecutionMode.BACKTEST,
            order_type=OrderType.MARKET,
            product_type=ProductType.INTRADAY,
        ),
    )
    assert strategy.exit.stop_loss_percent == 1.0
    assert strategy.risk.max_trades_per_day == 3
    assert strategy.execution.product_type is ProductType.INTRADAY
