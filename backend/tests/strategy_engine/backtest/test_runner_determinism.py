"""Determinism — run twice with the same input, deep-equal the output.

This is the trivial-but-essential test: the entire backtest engine must
be a pure function. No clock reads, no randomness, no LLM calls. If a
future PR ever introduces a non-deterministic path, this test fails.
"""

from __future__ import annotations

from app.strategy_engine.backtest import BacktestInput, run_backtest
from app.strategy_engine.schema.ohlcv import Candle
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy


def _build_candles() -> list[Candle]:
    return [
        make_candle(minutes=0, open_=100, high=100, low=100, close=100),
        make_candle(minutes=1, open_=100, high=100.4, low=99.6, close=100),
        make_candle(minutes=2, open_=100, high=102.5, low=99.6, close=102),
        make_candle(minutes=3, open_=102, high=102, low=99, close=99),
        make_candle(minutes=4, open_=99, high=100, low=99, close=100),
        make_candle(minutes=5, open_=100, high=102.5, low=99.6, close=102),
        make_candle(minutes=6, open_=102, high=103, low=101, close=101.5),
    ]


def test_run_twice_same_input_produces_identical_result() -> None:
    candles = _build_candles()
    strat = make_strategy(
        entry_conditions=[{"type": "price", "op": ">", "value": 99.5}],
        exit_block={"targetPercent": 2, "stopLossPercent": 5},
    )
    payload = BacktestInput(candles=candles, strategy=strat)

    a = run_backtest(payload)
    b = run_backtest(payload)

    # Pydantic frozen models implement __eq__ structurally — full deep equal.
    assert a == b


def test_two_separately_constructed_inputs_yield_identical_result() -> None:
    """Even two distinct ``BacktestInput`` instances with the same field values
    must produce equal results. Catches accidental hidden state.
    """
    candles_1 = _build_candles()
    candles_2 = _build_candles()

    strat_1 = make_strategy(
        entry_conditions=[{"type": "price", "op": ">", "value": 99.5}],
        exit_block={"targetPercent": 2, "stopLossPercent": 5},
    )
    strat_2 = make_strategy(
        entry_conditions=[{"type": "price", "op": ">", "value": 99.5}],
        exit_block={"targetPercent": 2, "stopLossPercent": 5},
    )

    a = run_backtest(BacktestInput(candles=candles_1, strategy=strat_1))
    b = run_backtest(BacktestInput(candles=candles_2, strategy=strat_2))

    assert a == b


def test_determinism_holds_under_costs_and_slippage() -> None:
    """Frictional configuration must not introduce float-noise drift."""
    from app.strategy_engine.backtest import CostSettings

    candles = _build_candles()
    strat = make_strategy(
        entry_conditions=[{"type": "price", "op": ">", "value": 99.5}],
        exit_block={"targetPercent": 2, "stopLossPercent": 5},
    )
    costs = CostSettings(fixed_cost=20, percent_cost=0.05, slippage_percent=0.1)
    payload = BacktestInput(candles=candles, strategy=strat, cost_settings=costs)

    a = run_backtest(payload)
    b = run_backtest(payload)
    assert a == b
