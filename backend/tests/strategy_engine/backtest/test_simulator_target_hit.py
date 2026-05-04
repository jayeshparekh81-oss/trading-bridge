"""Simulator: target-hit exit path."""

from __future__ import annotations

from app.strategy_engine.backtest import BacktestInput, run_backtest
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy


def test_target_fires_when_high_reaches_target_level() -> None:
    """Bar 1 entry @100. Bar 2 high=102.5 crosses target=102. The
    always-firing entry condition will queue another entry on bar 2 close
    that force-closes flat at backtest_end — we only assert the target
    trade itself.
    """
    candles = [
        make_candle(minutes=0, open_=100, high=100, low=100, close=100),
        make_candle(minutes=1, open_=100, high=100, low=99.6, close=100),
        make_candle(minutes=2, open_=100, high=102.5, low=99.6, close=102),
        make_candle(minutes=3, open_=102, high=102, low=102, close=102),
    ]
    strat = make_strategy(
        entry_conditions=[{"type": "price", "op": ">", "value": 99.5}],
        exit_block={"targetPercent": 2, "stopLossPercent": 5},  # SL out of range
    )
    result = run_backtest(BacktestInput(candles=candles, strategy=strat))
    targets = [t for t in result.trades if t.exit_reason == "target"]
    assert len(targets) == 1
    assert targets[0].entry_price == 100  # bar 1 open
    assert targets[0].exit_price == 102  # target level
    assert targets[0].pnl == 2.0


def test_target_does_not_fire_when_high_below_level() -> None:
    """Same setup but bar 2's high never reaches 102 -> no exit, force-close at end."""
    candles = [
        make_candle(minutes=0, open_=100, high=100, low=100, close=100),
        make_candle(minutes=1, open_=100, high=100, low=99.6, close=100),
        make_candle(minutes=2, open_=100, high=101.5, low=99.6, close=101),
        make_candle(minutes=3, open_=101, high=101, low=101, close=101),
    ]
    strat = make_strategy(
        entry_conditions=[{"type": "price", "op": ">", "value": 99.5}],
        exit_block={"targetPercent": 2, "stopLossPercent": 5},
    )
    result = run_backtest(BacktestInput(candles=candles, strategy=strat))
    # One forced close at backtest end (entry at bar 1 open=100, exit at bar 3 close=101).
    assert len(result.trades) == 1
    assert result.trades[0].exit_reason == "backtest_end"


def test_sell_target_uses_low_below_entry() -> None:
    """SELL strategy: target_percent=2 means exit when price drops 2% from entry."""
    candles = [
        make_candle(minutes=0, open_=100, high=100, low=100, close=100),
        make_candle(minutes=1, open_=100, high=100.4, low=100, close=100),  # entry @ 100 SELL
        make_candle(
            minutes=2, open_=100, high=100.4, low=97.5, close=98
        ),  # low = 97.5; target = 98
    ]
    strat = make_strategy(
        side="SELL",
        entry_conditions=[{"type": "price", "op": "<", "value": 100.5}],
        exit_block={"targetPercent": 2, "stopLossPercent": 5},
    )
    result = run_backtest(BacktestInput(candles=candles, strategy=strat))
    sell_trade = next(t for t in result.trades if t.exit_reason == "target")
    # SELL P&L = (entry - exit) * qty = (100 - 98) * 1 = 2.
    assert sell_trade.pnl == 2.0
