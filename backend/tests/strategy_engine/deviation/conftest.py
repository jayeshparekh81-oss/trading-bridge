"""Fixtures for the Deviation Monitor tests.

The monitor is pure math, so tests fabricate :class:`BacktestResult`
and :class:`LiveTradingStats` directly. That keeps each test under
50 ms and lets us pin specific boundary conditions
(win-rate diff = 0.25, drawdown ratio = 1.8, etc.) without engineering
a whole backtest pipeline that produces them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.strategy_engine.backtest.runner import BacktestResult
from app.strategy_engine.backtest.trade_log import EquityPoint
from app.strategy_engine.deviation.models import LiveTradingStats


def make_backtest(
    *,
    win_rate: float = 0.6,
    total_trades: int = 50,
    max_drawdown: float = 0.10,
    profit_factor: float = 2.0,
    average_win: float = 200.0,
    average_loss: float = 100.0,
    period_days: float = 10.0,
) -> BacktestResult:
    """Synthesise a healthy :class:`BacktestResult`.

    ``period_days`` controls the synthetic equity curve — two
    timestamped points spanning that many days so the trade-frequency
    estimator inside the monitor lands deterministically.
    """
    start = datetime(2026, 1, 1, 9, 30, tzinfo=UTC)
    end = start + timedelta(days=period_days)
    equity_curve = [
        EquityPoint(timestamp=start, equity=100_000.0),
        EquityPoint(timestamp=end, equity=100_000.0 + total_trades * average_win),
    ]
    return BacktestResult(
        total_pnl=total_trades * (average_win * win_rate - average_loss * (1 - win_rate)),
        total_return_percent=10.0,
        win_rate=win_rate,
        loss_rate=max(0.0, min(1.0, 1.0 - win_rate)),
        total_trades=total_trades,
        average_win=average_win,
        average_loss=average_loss,
        largest_win=average_win * 2,
        largest_loss=average_loss * 2,
        max_drawdown=max_drawdown,
        profit_factor=profit_factor,
        expectancy=20.0,
        equity_curve=equity_curve,
        trades=[],
        warnings=[],
    )


def make_live_stats(
    *,
    total_trades: int = 50,
    sessions: int = 10,
    win_rate: float = 0.6,
    profit_factor: float = 2.0,
    max_drawdown: float = 0.10,
    total_pnl: float = 5000.0,
) -> LiveTradingStats:
    """Synthesise a healthy :class:`LiveTradingStats`.

    Defaults match :func:`make_backtest` so the "perfect match" test
    can pass them straight through and assert ``status="normal"``.
    """
    return LiveTradingStats(
        total_trades=total_trades,
        sessions=sessions,
        win_rate=win_rate,
        profit_factor=profit_factor,
        max_drawdown=max_drawdown,
        total_pnl=total_pnl,
    )
