"""Persistence helpers for the backtest extension layer.

Maps the Pydantic boundary types in :mod:`schemas` onto the three
migration-028 tables (``backtest_runs`` + ``backtest_trades`` +
``backtest_metrics``). Centralises every SQL access so the Celery
worker and the API router both go through the same code path.

Module-level invariant: every public function is **session-managed by
the caller** — these helpers do not commit or close. The caller (API
handler or Celery task) owns the unit of work.

**Skeleton stage:** function bodies raise NotImplementedError. Day 1
of the Week 2 sprint fills these in; see
``docs/BACKTEST_ENGINE_EXTENSION_PLAN.md``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.backtest_extension.schemas import (
    BacktestEnqueueRequest,
    BacktestRunStatus,
)
from app.strategy_engine.backtest import BacktestResult


async def persist_pending_run(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    strategy_id: uuid.UUID | None,
    request: BacktestEnqueueRequest,
    request_hash: str,
    engine_version: str,
) -> uuid.UUID:
    """Insert a row in ``backtest_runs`` with status=PENDING.

    Returns the new ``backtest_runs.id``. Caller commits.

    Raises:
        NotImplementedError: skeleton — implement Day 1 Week 2.
    """
    raise NotImplementedError("Day 1 Week 2 deliverable.")


async def fetch_cached_run(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    request_hash: str,
) -> dict[str, Any] | None:
    """Look up a SUCCEEDED run by ``(user_id, request_hash)``.

    Returns ``None`` when no cached row exists.

    The return shape is the joined ``backtest_runs`` + ``backtest_metrics``
    payload ready to hand to :class:`BacktestRunOut.model_validate`.

    Raises:
        NotImplementedError: skeleton — implement Day 1 Week 2.
    """
    raise NotImplementedError("Day 1 Week 2 deliverable.")


async def update_run_status(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    status: BacktestRunStatus,
    completed_at: datetime | None = None,
    error: dict[str, Any] | None = None,
) -> None:
    """Update ``backtest_runs.status`` + matching consistency columns.

    Enforces:
        - ``completed_at`` MUST be non-None for SUCCEEDED / FAILED
        - ``error`` MUST be non-None for FAILED
        - both MUST be None for PENDING / RUNNING

    Raises:
        ValueError: input violates the consistency rules.
        NotImplementedError: skeleton — implement Day 1 Week 2.
    """
    raise NotImplementedError("Day 1 Week 2 deliverable.")


async def persist_succeeded_result(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    result: BacktestResult,
    completed_at: datetime,
) -> None:
    """Write the SUCCEEDED outcome: trade rows + metrics row + status flip.

    Single transaction:
        1. INSERT each ``Trade`` into ``backtest_trades`` (preserving order via ``trade_index``)
        2. INSERT one summary row into ``backtest_metrics``
        3. UPDATE ``backtest_runs`` SET status=SUCCEEDED, completed_at=now

    Caller commits.

    Raises:
        NotImplementedError: skeleton — implement Day 1 Week 2.
    """
    raise NotImplementedError("Day 1 Week 2 deliverable.")


async def fetch_run(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Return ``backtest_runs`` row joined with ``backtest_metrics`` (LEFT JOIN).

    Owner-scoped — returns None when the run exists but belongs to a
    different user (the API layer translates None → 404, never 403, to
    avoid id-enumeration probes).

    Raises:
        NotImplementedError: skeleton — implement Day 1 Week 2.
    """
    raise NotImplementedError("Day 1 Week 2 deliverable.")


async def fetch_trades_page(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
    cursor: int | None,
    page_size: int,
) -> tuple[list[dict[str, Any]], bool, int | None]:
    """Return one page of ``backtest_trades`` ordered by ``trade_index ASC``.

    Returns:
        ``(rows, has_more, next_cursor)`` — rows ready to hand to
        ``BacktestTradeOut.model_validate``. ``next_cursor`` is the
        last seen ``trade_index`` when ``has_more`` else None.

    Raises:
        NotImplementedError: skeleton — implement Day 1 Week 2.
    """
    raise NotImplementedError("Day 1 Week 2 deliverable.")


__all__ = [
    "fetch_cached_run",
    "fetch_run",
    "fetch_trades_page",
    "persist_pending_run",
    "persist_succeeded_result",
    "update_run_status",
]
