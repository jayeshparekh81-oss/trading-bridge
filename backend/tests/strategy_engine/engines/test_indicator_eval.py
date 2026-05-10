"""Indicator-condition evaluator tests."""

from __future__ import annotations

from app.strategy_engine.engines.indicator_eval import evaluate_indicator_condition
from app.strategy_engine.schema.strategy import IndicatorCondition, IndicatorConditionOp

# ─── Comparator vs constant ─────────────────────────────────────────────


def test_indicator_gt_constant() -> None:
    cond = IndicatorCondition(type="indicator", left="rsi_14", op=IndicatorConditionOp.GT, value=70)
    assert evaluate_indicator_condition(cond, current_values={"rsi_14": 75}) is True
    assert evaluate_indicator_condition(cond, current_values={"rsi_14": 70}) is False
    assert evaluate_indicator_condition(cond, current_values={"rsi_14": 50}) is False


def test_indicator_lt_constant() -> None:
    cond = IndicatorCondition(type="indicator", left="rsi_14", op=IndicatorConditionOp.LT, value=30)
    assert evaluate_indicator_condition(cond, current_values={"rsi_14": 25}) is True
    assert evaluate_indicator_condition(cond, current_values={"rsi_14": 30}) is False


def test_indicator_eq_neq() -> None:
    eq = IndicatorCondition(type="indicator", left="rsi_14", op=IndicatorConditionOp.EQ, value=50)
    neq = IndicatorCondition(type="indicator", left="rsi_14", op=IndicatorConditionOp.NEQ, value=50)
    assert evaluate_indicator_condition(eq, current_values={"rsi_14": 50}) is True
    assert evaluate_indicator_condition(eq, current_values={"rsi_14": 51}) is False
    assert evaluate_indicator_condition(neq, current_values={"rsi_14": 51}) is True
    assert evaluate_indicator_condition(neq, current_values={"rsi_14": 50}) is False


# ─── Comparator vs indicator ────────────────────────────────────────────


def test_indicator_gt_indicator() -> None:
    cond = IndicatorCondition(
        type="indicator",
        left="ema_20",
        op=IndicatorConditionOp.GT,
        right="ema_50",
    )
    assert evaluate_indicator_condition(cond, current_values={"ema_20": 110, "ema_50": 100}) is True
    assert evaluate_indicator_condition(cond, current_values={"ema_20": 90, "ema_50": 100}) is False


# ─── Missing / warm-up handling ─────────────────────────────────────────


def test_returns_false_when_left_value_missing() -> None:
    cond = IndicatorCondition(type="indicator", left="rsi_14", op=IndicatorConditionOp.GT, value=70)
    assert evaluate_indicator_condition(cond, current_values={"rsi_14": None}) is False
    assert evaluate_indicator_condition(cond, current_values={}) is False


def test_returns_false_when_rhs_indicator_missing() -> None:
    cond = IndicatorCondition(
        type="indicator",
        left="ema_20",
        op=IndicatorConditionOp.GT,
        right="ema_50",
    )
    assert (
        evaluate_indicator_condition(cond, current_values={"ema_20": 100, "ema_50": None}) is False
    )


# ─── Crossover / crossunder ─────────────────────────────────────────────


def test_crossover_fires_on_bar_relationship_flips() -> None:
    cond = IndicatorCondition(
        type="indicator",
        left="ema_fast",
        op=IndicatorConditionOp.CROSSOVER,
        right="ema_slow",
    )
    # Prior: fast <= slow; current: fast > slow -> crossover.
    assert (
        evaluate_indicator_condition(
            cond,
            current_values={"ema_fast": 102, "ema_slow": 100},
            prior_values={"ema_fast": 99, "ema_slow": 100},
        )
        is True
    )


def test_crossover_false_when_no_flip() -> None:
    cond = IndicatorCondition(
        type="indicator",
        left="ema_fast",
        op=IndicatorConditionOp.CROSSOVER,
        right="ema_slow",
    )
    # Already above on prior bar — no flip on current.
    assert (
        evaluate_indicator_condition(
            cond,
            current_values={"ema_fast": 105, "ema_slow": 100},
            prior_values={"ema_fast": 102, "ema_slow": 100},
        )
        is False
    )


def test_crossunder_fires_on_bar_relationship_flips() -> None:
    cond = IndicatorCondition(
        type="indicator",
        left="ema_fast",
        op=IndicatorConditionOp.CROSSUNDER,
        right="ema_slow",
    )
    assert (
        evaluate_indicator_condition(
            cond,
            current_values={"ema_fast": 98, "ema_slow": 100},
            prior_values={"ema_fast": 101, "ema_slow": 100},
        )
        is True
    )


def test_crossover_false_without_prior_values() -> None:
    cond = IndicatorCondition(
        type="indicator",
        left="ema_fast",
        op=IndicatorConditionOp.CROSSOVER,
        right="ema_slow",
    )
    assert (
        evaluate_indicator_condition(
            cond,
            current_values={"ema_fast": 102, "ema_slow": 100},
        )
        is False
    )


def test_crossover_false_when_any_value_is_none() -> None:
    cond = IndicatorCondition(
        type="indicator",
        left="ema_fast",
        op=IndicatorConditionOp.CROSSOVER,
        right="ema_slow",
    )
    assert (
        evaluate_indicator_condition(
            cond,
            current_values={"ema_fast": 102, "ema_slow": 100},
            prior_values={"ema_fast": None, "ema_slow": 100},
        )
        is False
    )
