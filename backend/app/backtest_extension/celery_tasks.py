"""Celery task that wraps the synchronous ``run_backtest()`` engine.

A single ``@shared_task`` ``run_backtest_task`` drives the state
machine on ``backtest_runs``: PENDING → RUNNING → SUCCEEDED|FAILED.
The task is **idempotent on dispatch** — a second call for the same
run_id while status != PENDING is a no-op (logged + returned).

Worker queue: the task is bound to the ``backtest`` queue (see Day 5
of ``docs/BACKTEST_ENGINE_EXTENSION_PLAN.md``) so a flood of preview
backtests doesn't starve the ``notifications`` / ``kill_switch``
queues that already share the default worker.

**Skeleton stage:** function body raises NotImplementedError. Day 3
of the Week 2 sprint fills this in; see
``docs/BACKTEST_ENGINE_EXTENSION_PLAN.md``.
"""

from __future__ import annotations

import uuid
from typing import Any

# NOTE: import gated behind TYPE_CHECKING in the actual Day-3 impl to
# keep startup-time fast. Skeleton imports celery lazily so this module
# can be imported in environments where celery isn't installed
# (unit-test environments that don't exercise the task).


# Sentinel used by the Day-3 implementation to bind the task to the
# dedicated "backtest" queue. The actual ``@shared_task`` decorator
# uses ``queue=BACKTEST_QUEUE`` to route messages.
BACKTEST_QUEUE = "backtest"


def run_backtest_task(
    run_id: str | uuid.UUID,
    request_payload: dict[str, Any],
) -> None:
    """Background worker entrypoint — wraps ``run_backtest()``.

    State machine (driven through :mod:`persistence`):

        1. Load BacktestRun by id. If status != PENDING, log a duplicate-
           dispatch warning and return (no error — duplicate dispatch is
           a benign race, not a bug).
        2. update_run_status → RUNNING
        3. Materialise candles from the request:
              ``app.strategy_engine.data_provider.fetch_historical_candles``
           Fall back to deterministic synthetic candles when the Dhan
           fetch fails (the existing Phase D Strategy Tester does the
           same — keeps preview workflow alive in dev/staging).
        4. Resolve the StrategyJSON payload:
              * request.strategy_id → ``select Strategy.strategy_json``
              * request.strategy_config → validate directly
        5. ``result = run_backtest(BacktestInput(...))`` — synchronous;
           this is where the engine's ~5-15 s CPU lives.
        6. ``persist_succeeded_result(...)`` → status=SUCCEEDED
        7. Structured log ``backtest.run.completed`` per
           ``docs/BACKTEST_ENGINE_EXTENSION_PLAN.md`` Day 7 spec.

    Exception path:
        Any uncaught exception during 3-6 → update_run_status with
        ``status=FAILED`` + ``error={"type": ..., "message": ..., "traceback_first_line": ...}``.
        Do NOT retry (Celery ``max_retries=0`` once the task starts
        running). The user can re-submit which gets a different run_id.

    Raises:
        NotImplementedError: skeleton — implement Day 3 Week 2.
    """
    raise NotImplementedError(
        "Day 3 Week 2 deliverable; see docs/BACKTEST_ENGINE_EXTENSION_PLAN.md"
    )


__all__ = ["BACKTEST_QUEUE", "run_backtest_task"]
