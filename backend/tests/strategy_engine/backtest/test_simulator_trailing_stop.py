"""Simulator: trailing-stop exit path."""

from __future__ import annotations

from app.strategy_engine.backtest import BacktestInput, run_backtest
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy


def test_trailing_stop_fires_after_high_then_pullback() -> None:
    """Trail = 1%. Run-up to 110, pullback to 108.5 should hit trail at 108.9.

    Sequence:
        bar 0: setup
        bar 1: entry @100 open
        bar 2: bar pushes to 110 high (trail seeds at 108.9 after this bar's close)
        bar 3: bar drops to 108 low — crosses trail at 108.9 -> exit
    """
    candles = [
        make_candle(minutes=0, open_=100, high=100, low=100, close=100),
        make_candle(minutes=1, open_=100, high=100, low=99.6, close=100),
        make_candle(minutes=2, open_=100, high=110, low=100, close=110),
        make_candle(minutes=3, open_=110, high=110, low=108, close=108.5),
    ]
    strat = make_strategy(
        entry_conditions=[{"type": "price", "op": ">", "value": 99.5}],
        exit_block={"trailingStopPercent": 1, "stopLossPercent": 50},
    )
    result = run_backtest(BacktestInput(candles=candles, strategy=strat))
    trail_trade = next(t for t in result.trades if t.exit_reason == "trailing_stop")
    # Exit price is the trail level (108.9), not the bar's close (108.5).
    assert trail_trade.exit_price == 108.9
    # P&L = (108.9 - 100) * 1 = 8.9
    assert abs(trail_trade.pnl - 8.9) < 1e-9


def test_trailing_stop_does_not_fire_on_entry_bar_pullback() -> None:
    """Trail is None on the entry bar (no prior close has updated it yet)."""
    candles = [
        make_candle(minutes=0, open_=100, high=100, low=100, close=100),
        make_candle(minutes=1, open_=100, high=100, low=99, close=100),  # entry @ 100; no trail yet
        make_candle(minutes=2, open_=100, high=100, low=99, close=99.5),  # pullback BUT no trail
    ]
    strat = make_strategy(
        entry_conditions=[{"type": "price", "op": ">", "value": 99.5}],
        exit_block={"trailingStopPercent": 1, "stopLossPercent": 50},
    )
    result = run_backtest(BacktestInput(candles=candles, strategy=strat))
    # No trailing-stop trade should appear.
    assert all(t.exit_reason != "trailing_stop" for t in result.trades)
