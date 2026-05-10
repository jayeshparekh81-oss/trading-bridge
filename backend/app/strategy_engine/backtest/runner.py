"""Backtest runner — public ``run_backtest()`` entry point.

Glues together :mod:`normalizer`, :mod:`indicator_runner`,
:mod:`simulator`, and :mod:`metrics` into one deterministic pipeline.
The Pydantic input/output models below are the boundary the rest of
the system (UI builder Phase 5, reliability engine Phase 4) talks to.

Output guarantees:
    * Same input -> same output, byte-for-byte (no clock reads, no
      randomness, no LLM calls — see master prompt's no-AI rule).
    * ``equity_curve`` is always one point per input candle, ordered.
    * ``trades`` is in close-time order; force-closed open positions at
      backtest end appear with ``exit_reason="backtest_end"``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.strategy_engine.backtest.costs import CostSettings
from app.strategy_engine.backtest.indicator_runner import precompute_indicators
from app.strategy_engine.backtest.metrics import (
    average_loss,
    average_win,
    expectancy,
    largest_loss,
    largest_win,
    loss_rate,
    max_drawdown,
    profit_factor,
    total_pnl,
    total_return_percent,
    win_rate,
)
from app.strategy_engine.backtest.normalizer import normalize_candles
from app.strategy_engine.backtest.simulator import simulate
from app.strategy_engine.backtest.trade_log import EquityPoint, Trade
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import StrategyJSON


class AmbiguityMode(StrEnum):
    """How the simulator resolves same-bar target+SL races.

    See ``simulator._prioritise_events`` for the priority tables.
    """

    CONSERVATIVE = "conservative"
    OPTIMISTIC = "optimistic"
    ACCURATE_PLACEHOLDER = "accurate_placeholder"


class BacktestInput(BaseModel):
    """Public input boundary for :func:`run_backtest`.

    ``candles`` is required; everything else has a default that yields
    a frictionless, conservative-mode backtest with single-unit fixed
    sizing — the simplest "does my strategy fire at all?" check.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    candles: list[Candle] = Field(..., min_length=2)
    strategy: StrategyJSON
    initial_capital: float = Field(default=100_000.0, gt=0, alias="initialCapital")
    quantity: float = Field(default=1.0, gt=0)
    cost_settings: CostSettings = Field(default_factory=CostSettings, alias="costSettings")
    ambiguity_mode: AmbiguityMode = Field(default=AmbiguityMode.CONSERVATIVE, alias="ambiguityMode")


class BacktestResult(BaseModel):
    """Public output boundary; matches the master prompt's documented shape."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    total_pnl: float = Field(..., alias="totalPnl")
    total_return_percent: float = Field(..., alias="totalReturnPercent")
    win_rate: float = Field(..., ge=0, le=1, alias="winRate")
    loss_rate: float = Field(..., ge=0, le=1, alias="lossRate")
    total_trades: int = Field(..., ge=0, alias="totalTrades")
    average_win: float = Field(..., alias="averageWin")
    average_loss: float = Field(..., alias="averageLoss")
    largest_win: float = Field(..., alias="largestWin")
    largest_loss: float = Field(..., alias="largestLoss")
    max_drawdown: float = Field(..., ge=0, alias="maxDrawdown")
    profit_factor: float = Field(..., alias="profitFactor")
    expectancy: float
    equity_curve: list[EquityPoint] = Field(..., alias="equityCurve")
    trades: list[Trade]
    warnings: list[str]


def run_backtest(payload: BacktestInput) -> BacktestResult:
    """Run a deterministic backtest. The single public entry point.

    Pipeline:
        1. :func:`normalize_candles` validates + sorts the candle list.
        2. :func:`precompute_indicators` runs every configured indicator
           ONCE end-to-end (O(N) memory; no per-bar recompute).
        3. :func:`simulate` walks bar-by-bar, calling the Phase 2 entry /
           exit / risk engines and the position state transitions.
        4. :mod:`metrics` aggregates the trade log into summary stats.
    """
    candles = normalize_candles(payload.candles)
    indicator_series, indicator_warnings = precompute_indicators(candles, payload.strategy)

    sim_result = simulate(
        candles=candles,
        strategy=payload.strategy,
        indicator_series=indicator_series,
        initial_capital=payload.initial_capital,
        quantity=payload.quantity,
        cost_settings=payload.cost_settings,
        ambiguity_mode=payload.ambiguity_mode.value,
    )

    pnls = [t.pnl for t in sim_result.trades]
    equity_values = [pt.equity for pt in sim_result.equity_curve]
    final_equity = equity_values[-1] if equity_values else payload.initial_capital

    warnings = list(indicator_warnings) + list(sim_result.warnings)

    return BacktestResult(
        total_pnl=total_pnl(pnls),
        total_return_percent=total_return_percent(payload.initial_capital, final_equity),
        win_rate=win_rate(pnls),
        loss_rate=loss_rate(pnls),
        total_trades=len(sim_result.trades),
        average_win=average_win(pnls),
        average_loss=average_loss(pnls),
        largest_win=largest_win(pnls),
        largest_loss=largest_loss(pnls),
        max_drawdown=max_drawdown(equity_values),
        profit_factor=profit_factor(pnls),
        expectancy=expectancy(pnls),
        equity_curve=sim_result.equity_curve,
        trades=sim_result.trades,
        warnings=warnings,
    )


__all__ = [
    "AmbiguityMode",
    "BacktestInput",
    "BacktestResult",
    "run_backtest",
]
