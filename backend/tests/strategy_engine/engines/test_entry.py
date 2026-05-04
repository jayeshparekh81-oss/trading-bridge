"""Entry engine tests — combination logic + dispatch."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.strategy_engine.engines.entry import evaluate_entry
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import StrategyJSON

T0 = datetime(2026, 5, 4, 10, 0, tzinfo=UTC)


def _bar(o: float, h: float, low: float, c: float, *, ts: datetime = T0) -> Candle:
    return Candle(timestamp=ts, open=o, high=h, low=low, close=c, volume=1000)


def _strategy_with(
    *,
    operator: str,
    conditions: list[dict[str, Any]],
    indicators: list[dict[str, Any]] | None = None,
) -> StrategyJSON:
    payload: dict[str, Any] = {
        "id": "s1",
        "name": "test",
        "mode": "expert",
        "indicators": indicators or [],
        "entry": {
            "side": "BUY",
            "operator": operator,
            "conditions": conditions,
        },
        "exit": {"stopLossPercent": 1},
        "execution": {
            "mode": "backtest",
            "orderType": "MARKET",
            "productType": "INTRADAY",
        },
    }
    return StrategyJSON.model_validate(payload)


# ─── AND combinator ─────────────────────────────────────────────────────


def test_entry_and_all_pass_fires() -> None:
    strat = _strategy_with(
        operator="AND",
        indicators=[
            {"id": "ema_20", "type": "ema", "params": {"period": 20}},
            {"id": "ema_50", "type": "ema", "params": {"period": 50}},
        ],
        conditions=[
            {"type": "indicator", "left": "ema_20", "op": ">", "right": "ema_50"},
            {"type": "price", "op": ">", "value": 100},
        ],
    )
    decision = evaluate_entry(
        strat,
        current_candle=_bar(99, 105, 98, 102),
        indicator_values={"ema_20": 110, "ema_50": 100},
    )
    assert decision.should_enter is True
    assert decision.side is not None and decision.side.value == "BUY"
    assert len(decision.reasons) == 2
    assert decision.failed_conditions == ()


def test_entry_and_one_fails_blocks() -> None:
    strat = _strategy_with(
        operator="AND",
        indicators=[
            {"id": "rsi_14", "type": "rsi", "params": {"period": 14}},
        ],
        conditions=[
            {"type": "indicator", "left": "rsi_14", "op": "<", "value": 30},
            {"type": "price", "op": ">", "value": 100},
        ],
    )
    decision = evaluate_entry(
        strat,
        current_candle=_bar(99, 105, 98, 102),
        indicator_values={"rsi_14": 50},  # > 30, fails
    )
    assert decision.should_enter is False
    assert decision.side is None
    assert len(decision.failed_conditions) == 1
    assert len(decision.reasons) == 1


# ─── OR combinator ──────────────────────────────────────────────────────


def test_entry_or_any_pass_fires() -> None:
    strat = _strategy_with(
        operator="OR",
        indicators=[
            {"id": "rsi_14", "type": "rsi", "params": {"period": 14}},
        ],
        conditions=[
            {"type": "indicator", "left": "rsi_14", "op": "<", "value": 30},
            {"type": "price", "op": ">", "value": 100},
        ],
    )
    decision = evaluate_entry(
        strat,
        current_candle=_bar(99, 105, 98, 102),  # close=102 > 100 — passes
        indicator_values={"rsi_14": 50},  # rsi fails
    )
    assert decision.should_enter is True
    assert len(decision.reasons) == 1
    assert len(decision.failed_conditions) == 1


def test_entry_or_all_fail_blocks() -> None:
    strat = _strategy_with(
        operator="OR",
        indicators=[
            {"id": "rsi_14", "type": "rsi", "params": {"period": 14}},
        ],
        conditions=[
            {"type": "indicator", "left": "rsi_14", "op": "<", "value": 30},
            {"type": "price", "op": ">", "value": 100},
        ],
    )
    decision = evaluate_entry(
        strat,
        current_candle=_bar(99, 102, 98, 99),  # close < 100, fails
        indicator_values={"rsi_14": 50},  # fails
    )
    assert decision.should_enter is False
    assert len(decision.failed_conditions) == 2


# ─── Dispatch coverage ──────────────────────────────────────────────────


def test_entry_dispatches_to_candle_pattern() -> None:
    strat = _strategy_with(
        operator="AND",
        conditions=[{"type": "candle", "pattern": "bullish"}],
    )
    bullish_bar = _bar(o=100, h=110, low=99, c=108)
    bearish_bar = _bar(o=110, h=112, low=99, c=100)
    assert (
        evaluate_entry(strat, current_candle=bullish_bar, indicator_values={}).should_enter is True
    )
    assert (
        evaluate_entry(strat, current_candle=bearish_bar, indicator_values={}).should_enter is False
    )


def test_entry_dispatches_to_time_condition() -> None:
    strat = _strategy_with(
        operator="AND",
        conditions=[{"type": "time", "op": "after", "value": "09:30"}],
    )
    after = _bar(100, 105, 99, 102, ts=datetime(2026, 5, 4, 9, 31, tzinfo=UTC))
    before = _bar(100, 105, 99, 102, ts=datetime(2026, 5, 4, 9, 29, tzinfo=UTC))
    assert evaluate_entry(strat, current_candle=after, indicator_values={}).should_enter is True
    assert evaluate_entry(strat, current_candle=before, indicator_values={}).should_enter is False


def test_entry_dispatches_to_price_breakout_with_prior_bar() -> None:
    strat = _strategy_with(
        operator="AND",
        conditions=[{"type": "price", "op": "previous_high_breakout"}],
    )
    prior = _bar(100, 105, 98, 104)
    current = _bar(104, 110, 103, 108)
    decision = evaluate_entry(
        strat,
        current_candle=current,
        prior_candle=prior,
        indicator_values={},
    )
    assert decision.should_enter is True


def test_entry_dispatches_to_indicator_crossover() -> None:
    strat = _strategy_with(
        operator="AND",
        indicators=[
            {"id": "ema_fast", "type": "ema", "params": {"period": 9}},
            {"id": "ema_slow", "type": "ema", "params": {"period": 20}},
        ],
        conditions=[
            {
                "type": "indicator",
                "left": "ema_fast",
                "op": "crossover",
                "right": "ema_slow",
            },
        ],
    )
    decision = evaluate_entry(
        strat,
        current_candle=_bar(100, 105, 99, 103),
        indicator_values={"ema_fast": 102, "ema_slow": 100},
        prior_indicator_values={"ema_fast": 99, "ema_slow": 100},
    )
    assert decision.should_enter is True


def test_entry_decision_immutable() -> None:
    strat = _strategy_with(
        operator="AND",
        conditions=[{"type": "price", "op": ">", "value": 100}],
    )
    decision = evaluate_entry(strat, current_candle=_bar(99, 105, 98, 102), indicator_values={})
    import pytest as _pytest

    with _pytest.raises((TypeError, ValueError)):
        decision.should_enter = False  # type: ignore[misc]


def test_entry_reasons_describe_conditions_human_readably() -> None:
    strat = _strategy_with(
        operator="AND",
        indicators=[
            {"id": "rsi_14", "type": "rsi", "params": {"period": 14}},
        ],
        conditions=[
            {"type": "indicator", "left": "rsi_14", "op": ">", "value": 70},
            {"type": "candle", "pattern": "bullish"},
        ],
    )
    decision = evaluate_entry(
        strat,
        current_candle=_bar(100, 110, 99, 108),
        indicator_values={"rsi_14": 75},
    )
    joined = " | ".join(decision.reasons)
    assert "rsi_14" in joined
    assert "bullish" in joined
