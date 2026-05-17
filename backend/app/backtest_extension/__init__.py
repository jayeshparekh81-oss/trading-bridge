"""Async + persisted + idempotent extension layer over the existing
deterministic backtest engine at :mod:`app.strategy_engine.backtest`.

**This package is a Week-2 skeleton.** Function bodies raise
``NotImplementedError``; supervised implementation begins on Day 1 of
the Week 2 sprint per ``docs/BACKTEST_ENGINE_EXTENSION_PLAN.md``.

Public boundary (forwarding):

The Phase 3 engine's public surface is re-exported so external callers
can import everything from one package once Week 2 ships. Existing
callers (Phase D Strategy Tester, reliability suite) continue to use
``app.strategy_engine.backtest`` directly — there's no migration burden.

Public boundary (new):

    enqueue_backtest               Celery dispatch, returns BacktestEnqueueResponse
    BacktestEnqueueRequest         Pydantic input shape
    BacktestEnqueueResponse        Pydantic output shape (carries run_id + cached flag)
    BacktestRunOut                 GET /api/backtest/{id} response
    BacktestTradesResponse         GET /api/backtest/{id}/trades response

Hard contract: this module DOES NOT import any router-registration
helper from ``app.main``. The supervised activation step on Day 4 of
Week 2 is the only place that wires ``router`` into the public app.
"""

from __future__ import annotations

# Re-export the engine surface untouched. Future callers can write
#     from app.backtest_extension import run_backtest
# without needing to know which sub-package owns the engine.
from app.strategy_engine.backtest import (
    AmbiguityMode,
    BacktestInput,
    BacktestResult,
    CostSettings,
    EquityPoint,
    Trade,
    run_backtest,
)

# New extension types — defined in schemas.py to keep this __init__ thin.
from app.backtest_extension.schemas import (
    BacktestEnqueueRequest,
    BacktestEnqueueResponse,
    BacktestMetricsOut,
    BacktestRunOut,
    BacktestRunStatus,
    BacktestTradeOut,
    BacktestTradesResponse,
)

__all__ = [
    # Forwarded
    "AmbiguityMode",
    "BacktestInput",
    "BacktestResult",
    "CostSettings",
    "EquityPoint",
    "Trade",
    "run_backtest",
    # New
    "BacktestEnqueueRequest",
    "BacktestEnqueueResponse",
    "BacktestMetricsOut",
    "BacktestRunOut",
    "BacktestRunStatus",
    "BacktestTradeOut",
    "BacktestTradesResponse",
]
