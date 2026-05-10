"""Simulator: max-trades-per-day risk gate."""

from __future__ import annotations

from app.strategy_engine.backtest import BacktestInput, run_backtest
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy


def test_max_trades_per_day_blocks_third_entry() -> None:
    """maxTradesPerDay=2; with always-firing entry, only 2 round-trips happen."""
    # 8 bars on the same calendar day. Each pair (entry, target-hit) closes
    # one trade. Without a cap, we'd get 4 trades; with the cap, only 2.
    candles = []
    for i in range(8):
        # Even bars: target candle (high=102.5). Odd bars: setup (open=100).
        if i % 2 == 1:
            # Setup bar
            candles.append(make_candle(minutes=i, open_=100, high=100.4, low=99.6, close=100))
        else:
            # Re-entry bar after exit
            candles.append(make_candle(minutes=i, open_=100, high=102.5, low=99.6, close=102))
    strat = make_strategy(
        entry_conditions=[{"type": "price", "op": ">", "value": 99.5}],
        exit_block={"targetPercent": 2, "stopLossPercent": 5},
        risk={"maxTradesPerDay": 2},
    )
    result = run_backtest(BacktestInput(candles=candles, strategy=strat))
    completed = [t for t in result.trades if t.exit_reason == "target"]
    assert len(completed) == 2, (
        f"Expected exactly 2 target-hit trades under cap=2; got {len(completed)}: "
        f"{[t.exit_reason for t in result.trades]}"
    )


def test_loss_streak_blocks_further_entries() -> None:
    """maxLossStreak=2; once two losses pile up, no new entry is queued."""
    candles = []
    # Pattern: entry-bar, SL-hit-bar, repeating. Each cycle is 2 bars.
    for i in range(10):
        if i % 2 == 1:
            candles.append(make_candle(minutes=i, open_=100, high=100.4, low=99.6, close=100))
        else:
            candles.append(make_candle(minutes=i, open_=100, high=100.4, low=98.5, close=99))
    strat = make_strategy(
        entry_conditions=[{"type": "price", "op": ">", "value": 99.5}],
        exit_block={"targetPercent": 5, "stopLossPercent": 1},
        risk={"maxLossStreak": 2},
    )
    result = run_backtest(BacktestInput(candles=candles, strategy=strat))
    sl_trades = [t for t in result.trades if t.exit_reason == "stop_loss"]
    assert len(sl_trades) == 2, f"Expected exactly 2 SL trades; got {len(sl_trades)}"
