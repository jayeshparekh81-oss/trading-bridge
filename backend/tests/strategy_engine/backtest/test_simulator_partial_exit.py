"""Simulator: partial-exit booking + dedup across bars."""

from __future__ import annotations

from app.strategy_engine.backtest import BacktestInput, run_backtest
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy


def test_partial_exit_fires_once_then_target_closes_remainder() -> None:
    """50% off at +1%, full target at +2%."""
    candles = [
        make_candle(minutes=0, open_=100, high=100, low=100, close=100),
        make_candle(minutes=1, open_=100, high=100.4, low=99.6, close=100),  # entry @ 100
        make_candle(minutes=2, open_=100, high=101.5, low=99.6, close=101),  # crosses partial @ 101
        make_candle(minutes=3, open_=101, high=102.5, low=100.5, close=102),  # crosses target @ 102
    ]
    strat = make_strategy(
        entry_conditions=[{"type": "price", "op": ">", "value": 99.5}],
        exit_block={
            "targetPercent": 2,
            "stopLossPercent": 5,
            "partialExits": [{"qtyPercent": 50, "targetPercent": 1}],
        },
    )
    result = run_backtest(BacktestInput(candles=candles, strategy=strat, quantity=10))
    partials = [t for t in result.trades if "partial" in t.exit_reason]
    targets = [t for t in result.trades if t.exit_reason == "target"]
    assert len(partials) == 1
    assert len(targets) == 1
    assert partials[0].quantity == 5  # 50% of 10
    assert targets[0].quantity == 5
    assert partials[0].pnl == 5  # (101 - 100) * 5
    assert targets[0].pnl == 10  # (102 - 100) * 5


def test_partial_exit_not_re_booked_on_subsequent_bars() -> None:
    """Once partial fires on bar 2, re-touching the same level on bar 3 must not re-fire."""
    candles = [
        make_candle(minutes=0, open_=100, high=100, low=100, close=100),
        make_candle(minutes=1, open_=100, high=100.4, low=99.6, close=100),
        make_candle(minutes=2, open_=100, high=101.5, low=100, close=101),  # partial fires
        make_candle(minutes=3, open_=101, high=101.5, low=100, close=101),  # touches 101 again
        make_candle(minutes=4, open_=101, high=101, low=101, close=101),  # backtest_end
    ]
    strat = make_strategy(
        entry_conditions=[{"type": "price", "op": ">", "value": 99.5}],
        exit_block={
            "stopLossPercent": 5,
            "partialExits": [{"qtyPercent": 50, "targetPercent": 1}],
        },
    )
    result = run_backtest(BacktestInput(candles=candles, strategy=strat, quantity=10))
    partials = [t for t in result.trades if "partial" in t.exit_reason]
    assert len(partials) == 1, "Partial booked twice — dedup against position state failed"
