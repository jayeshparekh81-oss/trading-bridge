"""Deterministic backtesting engine.

Phase 3 of the AI trading system. Pure-Python simulator built on top of
the Phase 1 schemas + Phase 2 engines. **AI never calculates results
here** — every number in :class:`BacktestResult` comes from deterministic
Python so the output is auditable, replayable, and safe to display.

Public boundary::

    AmbiguityMode             enum: conservative | optimistic | accurate_placeholder
    BacktestInput             pydantic — candles + strategy + capital + costs
    BacktestResult            pydantic — totals + equity curve + trades
    Trade / EquityPoint       individual rows
    CostSettings              pydantic — fixed / percent / slippage / spread
    run_backtest(input)       single entry point
"""

from __future__ import annotations

from app.strategy_engine.backtest.costs import CostSettings
from app.strategy_engine.backtest.runner import (
    AmbiguityMode,
    BacktestInput,
    BacktestResult,
    run_backtest,
)
from app.strategy_engine.backtest.trade_log import EquityPoint, Trade

__all__ = [
    "AmbiguityMode",
    "BacktestInput",
    "BacktestResult",
    "CostSettings",
    "EquityPoint",
    "Trade",
    "run_backtest",
]
