"""Simulator: daily-loss-percent risk gate."""

from __future__ import annotations

from app.strategy_engine.backtest import BacktestInput, run_backtest
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy


def test_daily_loss_cap_blocks_further_entries() -> None:
    """maxDailyLossPercent=0.5%; one big loss should stop further trading.

    initial_capital=1000, quantity=10, SL=10% => loss/trade = (10*1)*10 = 100? wait.
    Setup: entry@100, SL@90 => loss = (90-100)*10 = -100. As % of capital
    1000, that's -10%. Cap=0.5% => after first loss, daily P&L is -10% which
    is way past 0.5% -> blocked.
    """
    # Pattern: setup, SL-hit, then more bars that should NOT result in entries.
    candles = []
    for i in range(8):
        if i % 2 == 1:
            candles.append(make_candle(minutes=i, open_=100, high=100.4, low=99.6, close=100))
        else:
            candles.append(make_candle(minutes=i, open_=100, high=100.4, low=85, close=88))
    strat = make_strategy(
        entry_conditions=[{"type": "price", "op": ">", "value": 99.5}],
        exit_block={"targetPercent": 50, "stopLossPercent": 10},
        risk={"maxDailyLossPercent": 0.5},
    )
    result = run_backtest(
        BacktestInput(
            candles=candles,
            strategy=strat,
            initial_capital=1000,
            quantity=10,
        )
    )
    sl_trades = [t for t in result.trades if t.exit_reason == "stop_loss"]
    assert len(sl_trades) == 1, (
        f"Expected exactly 1 SL trade once daily-loss cap engaged; got {len(sl_trades)}"
    )


def test_daily_loss_cap_silent_on_winning_day() -> None:
    """A profitable run should not be affected by the daily-loss gate."""
    candles = [
        make_candle(minutes=0, open_=100, high=100, low=100, close=100),
        make_candle(minutes=1, open_=100, high=100.4, low=99.6, close=100),
        make_candle(minutes=2, open_=100, high=102.5, low=99.6, close=102),
    ]
    strat = make_strategy(
        entry_conditions=[{"type": "price", "op": ">", "value": 99.5}],
        exit_block={"targetPercent": 2, "stopLossPercent": 5},
        risk={"maxDailyLossPercent": 0.5},
    )
    result = run_backtest(BacktestInput(candles=candles, strategy=strat))
    assert result.total_pnl > 0
    assert result.total_trades >= 1
