"""Pydantic boundary models for the backtest extension layer.

Decoupled from the engine's own ``BacktestInput`` / ``BacktestResult``
because the extension's API request includes things the engine doesn't
care about (which symbol's candles to fetch, which date range, which
user the run belongs to). The engine continues to consume its own
boundary types untouched.

All models are Pydantic v2 with ``ConfigDict(extra="forbid")`` — drift
between the API + the DB + the engine surfaces at request boundary,
never silently.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.strategy_engine.backtest import (
    AmbiguityMode,
    CostSettings,
)


# ─── Enums ─────────────────────────────────────────────────────────────


class BacktestRunStatus(StrEnum):
    """State-machine values for ``backtest_runs.status``.

    Transitions are one-way:

        PENDING  → RUNNING        (worker pick-up)
        RUNNING  → SUCCEEDED      (run_backtest returns cleanly)
        RUNNING  → FAILED         (run_backtest raises)
        PENDING  → FAILED         (worker rejects without running, rare)

    There is no REQUEUED — a transient infra failure exhausts Celery's
    max_retries and lands the row in FAILED. Re-running is a brand-new
    request from the API.
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


# ─── Request shapes ────────────────────────────────────────────────────


class BacktestEnqueueRequest(BaseModel):
    """``POST /api/backtest`` body.

    Either ``strategy_id`` or ``strategy_config`` must be present:

    - ``strategy_id`` set → server loads the user-owned Strategy row,
      uses its ``strategy_json`` as the StrategyJSON payload. Mirrors
      the existing Phase D Strategy Tester contract.

    - ``strategy_config`` set → anonymous-config preview path used by
      the Phase 5 Strategy Builder (pre-save) + the template gallery
      preview button. The ``BacktestRun.strategy_id`` lands as NULL.

    If both are set the request is 422. If neither is set the request
    is 422.

    ``symbol`` / ``timeframe`` / ``start`` / ``end`` describe the
    historical-data window the engine will simulate against. Defaults
    fall back to a Phase-1 reasonable preview window (60 days of 5m
    candles on NIFTY) when omitted — final defaulting logic ships Day 6
    of the Week 2 sprint.
    """

    model_config = ConfigDict(extra="forbid")

    strategy_id: uuid.UUID | None = Field(
        default=None,
        description="Owned Strategy row id; mutually exclusive with strategy_config.",
    )
    strategy_config: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Anonymous strategy_json payload — Phase 5 builder / "
            "template preview. Validated as StrategyJSON at the API "
            "layer (Day 4 Week 2 work). Mutually exclusive with strategy_id."
        ),
    )

    symbol: str = Field(
        default="NIFTY",
        min_length=1,
        max_length=32,
        description="Index or stock symbol the engine pulls candles for.",
    )
    timeframe: str = Field(
        default="5m",
        description="Candle timeframe; passed to fetch_historical_candles.",
    )
    start: datetime | None = Field(
        default=None, description="Window start; defaults to now-60d."
    )
    end: datetime | None = Field(
        default=None, description="Window end; defaults to now."
    )

    initial_capital: float = Field(default=100_000.0, gt=0)
    quantity: float = Field(default=1.0, gt=0)
    cost_settings: CostSettings = Field(default_factory=CostSettings)
    ambiguity_mode: AmbiguityMode = Field(default=AmbiguityMode.CONSERVATIVE)


class BacktestEnqueueResponse(BaseModel):
    """``POST /api/backtest`` response."""

    model_config = ConfigDict(extra="forbid")

    run_id: uuid.UUID = Field(..., description="Persisted backtest_runs.id")
    status: BacktestRunStatus = Field(
        ...,
        description=(
            "Initial status. SUCCEEDED when cache hit, PENDING when "
            "newly enqueued."
        ),
    )
    cached: bool = Field(
        ..., description="True when an identical SUCCEEDED run was reused."
    )
    request_hash: str = Field(..., min_length=64, max_length=64)
    engine_version: str = Field(..., min_length=2, max_length=16)


# ─── Response shapes ───────────────────────────────────────────────────


class BacktestTradeOut(BaseModel):
    """One closed-trade row for ``GET /api/backtest/{id}/trades``."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trade_index: int = Field(..., ge=0)
    entry_time: datetime
    exit_time: datetime
    side: str = Field(..., pattern="^(BUY|SELL)$")
    entry_price: float = Field(..., gt=0)
    exit_price: float = Field(..., gt=0)
    quantity: float = Field(..., gt=0)
    pnl: float
    exit_reason: str = Field(..., min_length=1, max_length=128)
    entry_reasons: list[str] = Field(default_factory=list)


class BacktestTradesResponse(BaseModel):
    """Wrapper for paginated trades.

    Cursor is the last-seen ``trade_index`` — clients pass it back as
    ``?cursor=<n>`` to fetch the next page. ``has_more`` is True when
    the run has more trades beyond the last row in ``trades``.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: uuid.UUID
    trades: list[BacktestTradeOut]
    page_size: int = Field(..., gt=0, le=1000)
    has_more: bool
    next_cursor: int | None = Field(default=None, ge=0)


class BacktestMetricsOut(BaseModel):
    """Summary stats from a SUCCEEDED run. Mirrors BacktestResult minus
    equity_curve + trades."""

    model_config = ConfigDict(from_attributes=True)

    total_pnl: float
    total_return_percent: float
    win_rate: float = Field(..., ge=0, le=1)
    loss_rate: float = Field(..., ge=0, le=1)
    total_trades: int = Field(..., ge=0)
    average_win: float
    average_loss: float
    largest_win: float
    largest_loss: float
    max_drawdown: float = Field(..., ge=0, le=1)
    profit_factor: float | None = Field(
        default=None,
        description=(
            "NULL = wins-only deck. Treat as +inf for comparison/ranking."
        ),
    )
    expectancy: float
    warnings: list[str] = Field(default_factory=list)


class BacktestRunOut(BaseModel):
    """``GET /api/backtest/{id}`` response.

    Carries the run-level metadata + (when SUCCEEDED) the metrics
    block. Trades come from the separate /trades endpoint for paging.
    """

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    user_id: uuid.UUID
    strategy_id: uuid.UUID | None
    request_hash: str
    engine_version: str
    status: BacktestRunStatus
    started_at: datetime
    completed_at: datetime | None
    error: dict[str, Any] | None = Field(
        default=None,
        description="error_json when status=FAILED. None otherwise.",
    )
    metrics: BacktestMetricsOut | None = Field(
        default=None,
        description="None until status=SUCCEEDED.",
    )


__all__ = [
    "BacktestEnqueueRequest",
    "BacktestEnqueueResponse",
    "BacktestMetricsOut",
    "BacktestRunOut",
    "BacktestRunStatus",
    "BacktestTradeOut",
    "BacktestTradesResponse",
]
