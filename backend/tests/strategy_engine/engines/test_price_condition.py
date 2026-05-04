"""Price-condition evaluator tests."""

from __future__ import annotations

from datetime import UTC, datetime

from app.strategy_engine.engines.price_condition import evaluate_price_condition
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import PriceCondition, PriceConditionOp

T0 = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)


def _bar(o: float, h: float, low: float, c: float, v: float = 1000.0) -> Candle:
    return Candle(timestamp=T0, open=o, high=h, low=low, close=c, volume=v)


# ─── Comparators ────────────────────────────────────────────────────────


def test_gt_compares_against_close() -> None:
    cond = PriceCondition(type="price", op=PriceConditionOp.GT, value=100)
    assert evaluate_price_condition(cond, current=_bar(99, 105, 98, 101)) is True
    assert evaluate_price_condition(cond, current=_bar(99, 105, 98, 100)) is False
    assert evaluate_price_condition(cond, current=_bar(99, 105, 98, 99)) is False


def test_lt_compares_against_close() -> None:
    cond = PriceCondition(type="price", op=PriceConditionOp.LT, value=100)
    assert evaluate_price_condition(cond, current=_bar(101, 105, 98, 99)) is True
    assert evaluate_price_condition(cond, current=_bar(101, 105, 98, 100)) is False


def test_gte_includes_equality() -> None:
    cond = PriceCondition(type="price", op=PriceConditionOp.GTE, value=100)
    assert evaluate_price_condition(cond, current=_bar(99, 105, 98, 100)) is True
    assert evaluate_price_condition(cond, current=_bar(99, 105, 98, 99.99)) is False


def test_lte_includes_equality() -> None:
    cond = PriceCondition(type="price", op=PriceConditionOp.LTE, value=100)
    assert evaluate_price_condition(cond, current=_bar(99, 105, 98, 100)) is True
    assert evaluate_price_condition(cond, current=_bar(99, 105, 98, 100.01)) is False


# ─── Breakouts ─────────────────────────────────────────────────────────


def test_previous_high_breakout_when_current_high_above_prior_high() -> None:
    cond = PriceCondition(type="price", op=PriceConditionOp.PREVIOUS_HIGH_BREAKOUT)
    prior = _bar(100, 105, 99, 104)
    current = _bar(104, 110, 103, 108)
    assert evaluate_price_condition(cond, current=current, prior=prior) is True


def test_previous_high_breakout_false_when_equal_or_below() -> None:
    cond = PriceCondition(type="price", op=PriceConditionOp.PREVIOUS_HIGH_BREAKOUT)
    prior = _bar(100, 105, 99, 104)
    current_eq = _bar(102, 105, 100, 103)
    current_lo = _bar(102, 104, 100, 103)
    assert evaluate_price_condition(cond, current=current_eq, prior=prior) is False
    assert evaluate_price_condition(cond, current=current_lo, prior=prior) is False


def test_previous_low_breakdown_when_current_low_below_prior_low() -> None:
    cond = PriceCondition(type="price", op=PriceConditionOp.PREVIOUS_LOW_BREAKDOWN)
    prior = _bar(100, 105, 99, 100)
    current = _bar(100, 102, 95, 96)
    assert evaluate_price_condition(cond, current=current, prior=prior) is True


def test_breakout_false_when_no_prior_bar() -> None:
    cond_high = PriceCondition(type="price", op=PriceConditionOp.PREVIOUS_HIGH_BREAKOUT)
    cond_low = PriceCondition(type="price", op=PriceConditionOp.PREVIOUS_LOW_BREAKDOWN)
    bar = _bar(100, 110, 90, 105)
    assert evaluate_price_condition(cond_high, current=bar, prior=None) is False
    assert evaluate_price_condition(cond_low, current=bar, prior=None) is False
