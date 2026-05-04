"""End-to-end integration: master-prompt-style strategy on a longer series.

This test is intentionally close to a "real" use case — it constructs
the EMA + RSI Beginner strategy from the master prompt's Phase 1 example
and runs it on a hand-crafted price sequence designed to exercise multi-
trade lifecycle + warm-up handling. The goal is "system runs end-to-end
and emits a coherent BacktestResult", not a specific numerical target.
"""

from __future__ import annotations

import math

from app.strategy_engine.backtest import BacktestInput, run_backtest
from app.strategy_engine.schema.ohlcv import Candle
from tests.strategy_engine.backtest.conftest import make_candle, make_strategy


def _series() -> list[Candle]:
    """40-bar series with two distinct rallies separated by a pullback.

    The shape doesn't try to encode a specific edge — just exercises
    enough of the lifecycle (entry, partial, target, re-entry, force-
    close-at-end) for the integration assertions to be meaningful.
    """
    candles: list[Candle] = []
    # Phase 1 (bars 0-9): flat around 100, builds EMA warm-up.
    for i in range(10):
        candles.append(make_candle(minutes=i, open_=100, high=100.5, low=99.5, close=100))
    # Phase 2 (bars 10-19): rally from 100 to 110, pulls back to 105.
    rally = [100.5, 101.5, 103, 105, 107, 108.5, 110, 109, 107, 105]
    for offset, close in enumerate(rally):
        candles.append(
            make_candle(
                minutes=10 + offset,
                open_=close - 0.5,
                high=close + 0.5,
                low=close - 1,
                close=close,
            )
        )
    # Phase 3 (bars 20-29): consolidation around 105.
    for i in range(10):
        candles.append(make_candle(minutes=20 + i, open_=105, high=105.5, low=104.5, close=105))
    # Phase 4 (bars 30-39): second rally + pullback.
    second = [105.5, 106.5, 108, 110, 112, 114, 113, 111, 109, 108]
    for offset, close in enumerate(second):
        candles.append(
            make_candle(
                minutes=30 + offset,
                open_=close - 0.5,
                high=close + 0.5,
                low=close - 1,
                close=close,
            )
        )
    return candles


def test_full_integration_runs_end_to_end_and_emits_coherent_result() -> None:
    """Strategy: BUY when price > 99.5; target 2 %, SL 5 %, partial 50 % @ 1 %."""
    strat = make_strategy(
        indicators=[
            {"id": "ema_5", "type": "ema", "params": {"period": 5}},
            {"id": "rsi_14", "type": "rsi", "params": {"period": 14}},
        ],
        entry_conditions=[
            {"type": "indicator", "left": "ema_5", "op": ">", "value": 99},
        ],
        exit_block={
            "targetPercent": 2,
            "stopLossPercent": 5,
            "partialExits": [{"qtyPercent": 50, "targetPercent": 1}],
        },
    )
    payload = BacktestInput(
        candles=_series(),
        strategy=strat,
        initial_capital=100_000.0,
        quantity=10,
    )
    result = run_backtest(payload)

    # Coherence checks — run completed without raising.
    assert len(result.equity_curve) == len(_series())
    assert result.total_trades >= 1
    assert 0 <= result.win_rate <= 1
    assert 0 <= result.loss_rate <= 1
    assert 0 <= result.max_drawdown <= 1
    assert math.isfinite(result.total_pnl)
    assert math.isfinite(result.expectancy)

    # Trade-log internal consistency: pnl sum within 1 paisa of total_pnl.
    summed = sum(t.pnl for t in result.trades)
    assert abs(summed - result.total_pnl) < 0.01

    # If win_rate > 0, there must actually be a positive-pnl trade in the log.
    if result.win_rate > 0:
        assert any(t.pnl > 0 for t in result.trades)


def test_full_integration_serialises_round_trip() -> None:
    """``BacktestResult`` must round-trip through model_dump_json without loss."""
    strat = make_strategy(
        entry_conditions=[{"type": "price", "op": ">", "value": 99.5}],
        exit_block={"targetPercent": 2, "stopLossPercent": 5},
    )
    payload = BacktestInput(candles=_series(), strategy=strat)
    result = run_backtest(payload)

    from app.strategy_engine.backtest import BacktestResult

    blob = result.model_dump_json(by_alias=True)
    rehydrated = BacktestResult.model_validate_json(blob)
    assert rehydrated == result
