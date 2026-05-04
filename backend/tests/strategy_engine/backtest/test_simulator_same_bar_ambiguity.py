"""Simulator: same-bar target+SL ambiguity — three modes.

Same input, three modes, three different exit outcomes. This is the
single highest-stakes correctness test in Phase 3 — it locks the
behaviour the master prompt mandated.
"""

from __future__ import annotations

from app.strategy_engine.backtest import AmbiguityMode, BacktestInput, run_backtest
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy

_CANDLES = [
    make_candle(minutes=0, open_=100, high=100, low=100, close=100),
    make_candle(minutes=1, open_=100, high=100.4, low=99.6, close=100),  # entry @100
    # Bar 2: BOTH target (102) and SL (99) inside the bar's range.
    make_candle(minutes=2, open_=100, high=103, low=98, close=100),
]
_STRAT = make_strategy(
    entry_conditions=[{"type": "price", "op": ">", "value": 99.5}],
    exit_block={"targetPercent": 2, "stopLossPercent": 1},
)


def test_conservative_mode_picks_stop_loss() -> None:
    result = run_backtest(
        BacktestInput(
            candles=_CANDLES,
            strategy=_STRAT,
            ambiguity_mode=AmbiguityMode.CONSERVATIVE,
        )
    )
    sl_trades = [t for t in result.trades if t.exit_reason == "stop_loss"]
    target_trades = [t for t in result.trades if t.exit_reason == "target"]
    assert len(sl_trades) == 1
    assert len(target_trades) == 0
    assert sl_trades[0].pnl == -1.0


def test_optimistic_mode_picks_target() -> None:
    result = run_backtest(
        BacktestInput(
            candles=_CANDLES,
            strategy=_STRAT,
            ambiguity_mode=AmbiguityMode.OPTIMISTIC,
        )
    )
    target_trades = [t for t in result.trades if t.exit_reason == "target"]
    sl_trades = [t for t in result.trades if t.exit_reason == "stop_loss"]
    assert len(target_trades) == 1
    assert len(sl_trades) == 0
    assert target_trades[0].pnl == 2.0


def test_accurate_placeholder_falls_back_to_conservative() -> None:
    """Phase 3 contract: accurate_placeholder behaves identically to conservative."""
    accurate = run_backtest(
        BacktestInput(
            candles=_CANDLES,
            strategy=_STRAT,
            ambiguity_mode=AmbiguityMode.ACCURATE_PLACEHOLDER,
        )
    )
    conservative = run_backtest(
        BacktestInput(
            candles=_CANDLES,
            strategy=_STRAT,
            ambiguity_mode=AmbiguityMode.CONSERVATIVE,
        )
    )
    assert accurate.total_pnl == conservative.total_pnl
    assert [(t.exit_reason, t.pnl) for t in accurate.trades] == [
        (t.exit_reason, t.pnl) for t in conservative.trades
    ]


def test_ambiguity_mode_does_not_affect_single_trigger_bars() -> None:
    """If only ONE of target/SL is in range, mode shouldn't matter."""
    candles = [
        make_candle(minutes=0, open_=100, high=100, low=100, close=100),
        make_candle(minutes=1, open_=100, high=100.4, low=99.6, close=100),
        make_candle(minutes=2, open_=100, high=102.5, low=99.6, close=102),
    ]
    strat = make_strategy(
        entry_conditions=[{"type": "price", "op": ">", "value": 99.5}],
        exit_block={"targetPercent": 2, "stopLossPercent": 1},
    )
    cons = run_backtest(
        BacktestInput(candles=candles, strategy=strat, ambiguity_mode=AmbiguityMode.CONSERVATIVE)
    )
    opt = run_backtest(
        BacktestInput(candles=candles, strategy=strat, ambiguity_mode=AmbiguityMode.OPTIMISTIC)
    )
    assert cons.total_pnl == opt.total_pnl
