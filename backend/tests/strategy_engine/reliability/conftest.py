"""Shared fixtures for the reliability test suite.

The Phase 3 :class:`BacktestResult` is a Pydantic model — we build them
by hand here rather than running real backtests, because the trust-
score engine is supposed to be exercisable from a serialised result
without ever touching the simulator.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from app.strategy_engine.backtest import BacktestResult, EquityPoint, Trade
from app.strategy_engine.schema.strategy import Side

T0 = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)


def make_backtest_result(
    *,
    total_pnl: float = 100.0,
    total_return_percent: float = 1.0,
    win_rate: float = 0.6,
    loss_rate: float = 0.4,
    total_trades: int = 50,
    average_win: float = 5.0,
    average_loss: float = 3.0,
    largest_win: float = 12.0,
    largest_loss: float = -8.0,
    max_drawdown: float = 0.10,
    profit_factor: float = 1.6,
    expectancy: float = 0.6,
    n_equity_points: int = 5,
    initial_capital: float = 100_000.0,
) -> BacktestResult:
    """Build a synthetic :class:`BacktestResult` with sensible defaults.

    Override any field via kwargs; the trade list and equity curve are
    minimal stand-ins — the trust-score engine never inspects their
    contents, only the summary metrics.
    """
    trades = [
        Trade(
            entry_time=T0 + timedelta(minutes=i),
            exit_time=T0 + timedelta(minutes=i + 1),
            side=Side.BUY,
            entry_price=100.0,
            exit_price=101.0,
            quantity=1.0,
            pnl=1.0,
            exit_reason="target",
        )
        for i in range(min(2, total_trades))
    ]
    equity_curve = [
        EquityPoint(
            timestamp=T0 + timedelta(minutes=i),
            equity=initial_capital + i,
        )
        for i in range(n_equity_points)
    ]
    return BacktestResult(
        total_pnl=total_pnl,
        total_return_percent=total_return_percent,
        win_rate=win_rate,
        loss_rate=loss_rate,
        total_trades=total_trades,
        average_win=average_win,
        average_loss=average_loss,
        largest_win=largest_win,
        largest_loss=largest_loss,
        max_drawdown=max_drawdown,
        profit_factor=profit_factor,
        expectancy=expectancy,
        equity_curve=equity_curve,
        trades=trades,
        warnings=[],
    )


def make_strong_strategy_result() -> BacktestResult:
    """A 'strong strategy' baseline that should grade A.

    100 trades, win rate 0.62, profit factor 2.1, max drawdown 8 %,
    avg_win > avg_loss. Every check passes -> score == 100.
    """
    return make_backtest_result(
        total_pnl=15_000.0,
        total_return_percent=15.0,
        win_rate=0.62,
        loss_rate=0.38,
        total_trades=100,
        average_win=300.0,
        average_loss=180.0,
        largest_win=900.0,
        largest_loss=-450.0,
        max_drawdown=0.08,
        profit_factor=2.1,
        expectancy=72.6,
    )


def make_high_win_rate_trap_result() -> BacktestResult:
    """A 90 % win rate but profit factor only 1.2 (small wins, rare big losses)."""
    return make_backtest_result(
        total_pnl=200.0,
        total_return_percent=0.2,
        win_rate=0.90,
        loss_rate=0.10,
        total_trades=50,
        average_win=10.0,
        average_loss=72.0,  # big losses on the 10 %
        largest_win=20.0,
        largest_loss=-200.0,
        max_drawdown=0.18,
        profit_factor=1.2,
        expectancy=4.0,
    )


def make_low_trade_count_result() -> BacktestResult:
    """Only 12 trades — well under the 30 threshold."""
    return make_backtest_result(
        total_pnl=400.0,
        total_return_percent=0.4,
        win_rate=0.60,
        loss_rate=0.40,
        total_trades=12,
        average_win=80.0,
        average_loss=50.0,
        max_drawdown=0.15,
        profit_factor=1.7,
        expectancy=33.0,
    )


def make_unprofitable_result() -> BacktestResult:
    """Profit factor 0.7 — strategy loses money."""
    return make_backtest_result(
        total_pnl=-2000.0,
        total_return_percent=-2.0,
        win_rate=0.40,
        loss_rate=0.60,
        total_trades=80,
        average_win=70.0,
        average_loss=120.0,
        max_drawdown=0.25,
        profit_factor=0.7,
        expectancy=-44.0,
    )


def make_perfect_result_for_grading() -> BacktestResult:
    """Edge-case helper: result whose every check passes — used by grading
    boundary tests to inject synthetic OOS / WF / sensitivity inputs.
    """
    return make_strong_strategy_result()


def safe_pf(value: float | None) -> float:
    """Helper for tests — turn None into math.inf, useful for table-driven cases."""
    return math.inf if value is None else value
