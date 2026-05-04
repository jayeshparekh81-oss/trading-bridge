"""Simulator: stop-loss exit path."""

from __future__ import annotations

from app.strategy_engine.backtest import BacktestInput, run_backtest
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy


def test_stoploss_fires_when_low_reaches_sl_level() -> None:
    """Bar 1 entry @100. Bar 2 low touches 99 (SL=1%). Position should exit at 99."""
    candles = [
        make_candle(minutes=0, open_=100, high=100, low=100, close=100),
        make_candle(minutes=1, open_=100, high=100.4, low=99.6, close=100),
        make_candle(minutes=2, open_=100, high=100.4, low=98.5, close=99),
        make_candle(minutes=3, open_=99, high=99, low=99, close=99),
    ]
    strat = make_strategy(
        entry_conditions=[{"type": "price", "op": ">", "value": 99.5}],
        exit_block={"targetPercent": 5, "stopLossPercent": 1},
    )
    result = run_backtest(BacktestInput(candles=candles, strategy=strat))
    sl_trade = next(t for t in result.trades if t.exit_reason == "stop_loss")
    assert sl_trade.entry_price == 100
    assert sl_trade.exit_price == 99
    assert sl_trade.pnl == -1.0
    assert result.loss_rate > 0


def test_sell_stoploss_uses_high_above_entry() -> None:
    candles = [
        make_candle(minutes=0, open_=100, high=100, low=100, close=100),
        make_candle(minutes=1, open_=100, high=100.4, low=99.6, close=100),
        make_candle(minutes=2, open_=100, high=101.5, low=99.6, close=101),
    ]
    strat = make_strategy(
        side="SELL",
        entry_conditions=[{"type": "price", "op": "<", "value": 100.5}],
        exit_block={"targetPercent": 5, "stopLossPercent": 1},
    )
    result = run_backtest(BacktestInput(candles=candles, strategy=strat))
    sl_trade = next(t for t in result.trades if t.exit_reason == "stop_loss")
    # SELL SL at 101 -> P&L = (100 - 101) = -1.
    assert sl_trade.pnl == -1.0
