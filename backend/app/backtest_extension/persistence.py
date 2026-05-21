"""Persistence helpers for the backtest extension layer.

Maps the Pydantic boundary types in :mod:`schemas` + the engine's
:class:`BacktestResult` onto the three migration-028 tables.
Centralises every SQL access so the Celery worker and the API router
both go through the same code path.

**Caller owns the unit of work.** None of these helpers commits or
closes — the caller (API handler or Celery task) decides transaction
boundaries.

State-machine invariants enforced here (in addition to DB CHECK
constraints):

    PENDING  → RUNNING        ok
    PENDING  → FAILED         ok (early-fail path)
    RUNNING  → SUCCEEDED      ok
    RUNNING  → FAILED         ok

Other transitions raise :class:`ValueError` so a buggy caller can't
quietly produce inconsistent rows.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.backtest_extension.models import (
    BacktestMetrics,
    BacktestRun,
    BacktestTrade,
)
from app.backtest_extension.schemas import BacktestRunStatus
from app.strategy_engine.backtest import BacktestResult, Trade


# ─── Allowed transitions ────────────────────────────────────────────────


_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    BacktestRunStatus.PENDING.value: frozenset(
        {BacktestRunStatus.RUNNING.value, BacktestRunStatus.FAILED.value}
    ),
    BacktestRunStatus.RUNNING.value: frozenset(
        {BacktestRunStatus.SUCCEEDED.value, BacktestRunStatus.FAILED.value}
    ),
    BacktestRunStatus.SUCCEEDED.value: frozenset(),
    BacktestRunStatus.FAILED.value: frozenset(),
}


class InvalidStatusTransitionError(ValueError):
    """Raised when caller asks for a state-machine transition we forbid."""


def _validate_transition(*, current: str, target: str) -> None:
    allowed = _ALLOWED_TRANSITIONS.get(current)
    if allowed is None:
        raise InvalidStatusTransitionError(
            f"Unknown source status {current!r} (expected one of "
            f"{list(_ALLOWED_TRANSITIONS)!r})."
        )
    if target not in allowed:
        raise InvalidStatusTransitionError(
            f"Cannot transition {current} → {target}. Allowed from {current}: "
            f"{sorted(allowed)!r}."
        )


# ─── Save / lookup helpers ──────────────────────────────────────────────


async def save_run(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    strategy_id: uuid.UUID | None,
    request_payload: dict[str, Any],
    request_hash: str,
    engine_version: str,
) -> BacktestRun:
    """Insert a new ``backtest_runs`` row with status=PENDING.

    Caller is responsible for committing. Returns the populated
    BacktestRun (including a generated id).
    """
    run = BacktestRun(
        user_id=user_id,
        strategy_id=strategy_id,
        request_hash=request_hash,
        engine_version=engine_version,
        status=BacktestRunStatus.PENDING.value,
        request_payload=request_payload,
        error_json=None,
        completed_at=None,
    )
    db.add(run)
    await db.flush()
    return run


async def update_status(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    status: BacktestRunStatus,
    completed_at: datetime | None = None,
    error: dict[str, Any] | None = None,
) -> BacktestRun:
    """Transition a run's status with consistency invariants enforced.

    Invariants (mirror the DB CHECK constraints):
        * SUCCEEDED / FAILED → completed_at MUST be non-None
        * PENDING / RUNNING → completed_at MUST be None
        * FAILED → error MUST be non-None
        * SUCCEEDED / PENDING / RUNNING → error MUST be None

    Raises :class:`ValueError` on rule violation; raises
    :class:`InvalidStatusTransitionError` on illegal transition.
    Caller commits.
    """
    target = status.value
    terminal = target in (
        BacktestRunStatus.SUCCEEDED.value,
        BacktestRunStatus.FAILED.value,
    )

    if terminal and completed_at is None:
        raise ValueError(
            f"completed_at must be set when transitioning to {target}."
        )
    if not terminal and completed_at is not None:
        raise ValueError(
            f"completed_at must be None when transitioning to {target}."
        )
    if target == BacktestRunStatus.FAILED.value and error is None:
        raise ValueError("error must be set when transitioning to FAILED.")
    if target != BacktestRunStatus.FAILED.value and error is not None:
        raise ValueError(
            f"error must be None when transitioning to {target}."
        )

    run = (
        await db.execute(select(BacktestRun).where(BacktestRun.id == run_id))
    ).scalar_one_or_none()
    if run is None:
        raise ValueError(f"BacktestRun {run_id} not found.")

    _validate_transition(current=run.status, target=target)
    run.status = target
    run.completed_at = completed_at
    run.error_json = error
    await db.flush()
    return run


def _trade_to_orm(*, run_id: uuid.UUID, trade_index: int, trade: Trade) -> BacktestTrade:
    return BacktestTrade(
        run_id=run_id,
        trade_index=trade_index,
        entry_time=trade.entry_time,
        exit_time=trade.exit_time,
        side=trade.side.value,
        entry_price=Decimal(str(trade.entry_price)),
        exit_price=Decimal(str(trade.exit_price)),
        quantity=Decimal(str(trade.quantity)),
        pnl=Decimal(str(trade.pnl)),
        exit_reason=trade.exit_reason,
        entry_reasons=list(trade.entry_reasons),
    )


async def save_trades(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    trades: list[Trade],
) -> int:
    """Bulk-insert one ``backtest_trades`` row per Trade.

    Returns the count of rows inserted. Preserves order via the
    ``trade_index`` column (0-based monotonic). Caller commits.
    """
    if not trades:
        return 0
    orm_rows = [
        _trade_to_orm(run_id=run_id, trade_index=i, trade=t)
        for i, t in enumerate(trades)
    ]
    db.add_all(orm_rows)
    await db.flush()
    return len(orm_rows)


def _coerce_profit_factor(value: float) -> Decimal | None:
    """Engine emits math.inf for wins-only deck → DB stores NULL."""
    if math.isinf(value) or math.isnan(value):
        return None
    return Decimal(str(value))


async def save_metrics(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    result: BacktestResult,
) -> BacktestMetrics:
    """UPSERT the ``backtest_metrics`` row for a SUCCEEDED run.

    UPSERT semantics: if a row already exists for ``run_id`` (e.g. a
    re-persist after a transient mid-write crash), overwrite. Caller
    commits.
    """
    existing = (
        await db.execute(
            select(BacktestMetrics).where(BacktestMetrics.run_id == run_id)
        )
    ).scalar_one_or_none()

    if existing is None:
        metrics = BacktestMetrics(
            run_id=run_id,
            total_pnl=Decimal(str(result.total_pnl)),
            total_return_percent=Decimal(str(result.total_return_percent)),
            win_rate=Decimal(str(result.win_rate)),
            loss_rate=Decimal(str(result.loss_rate)),
            total_trades=result.total_trades,
            average_win=Decimal(str(result.average_win)),
            average_loss=Decimal(str(result.average_loss)),
            largest_win=Decimal(str(result.largest_win)),
            largest_loss=Decimal(str(result.largest_loss)),
            max_drawdown=Decimal(str(result.max_drawdown)),
            profit_factor=_coerce_profit_factor(result.profit_factor),
            expectancy=Decimal(str(result.expectancy)),
            warnings=list(result.warnings),
        )
        db.add(metrics)
    else:
        metrics = existing
        metrics.total_pnl = Decimal(str(result.total_pnl))
        metrics.total_return_percent = Decimal(str(result.total_return_percent))
        metrics.win_rate = Decimal(str(result.win_rate))
        metrics.loss_rate = Decimal(str(result.loss_rate))
        metrics.total_trades = result.total_trades
        metrics.average_win = Decimal(str(result.average_win))
        metrics.average_loss = Decimal(str(result.average_loss))
        metrics.largest_win = Decimal(str(result.largest_win))
        metrics.largest_loss = Decimal(str(result.largest_loss))
        metrics.max_drawdown = Decimal(str(result.max_drawdown))
        metrics.profit_factor = _coerce_profit_factor(result.profit_factor)
        metrics.expectancy = Decimal(str(result.expectancy))
        metrics.warnings = list(result.warnings)

    await db.flush()
    return metrics


async def get_run_by_id(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    with_metrics: bool = True,
) -> BacktestRun | None:
    """Fetch a single run by id, optionally owner-scoped.

    Owner scoping: when ``user_id`` is provided, the query adds
    ``WHERE user_id = :user_id``. A row that exists but belongs to a
    different user returns ``None`` (caller translates to 404 — see
    decision D15 anti-enumeration).

    ``with_metrics=True`` eager-loads the 1-to-1 metrics relationship
    via ``selectinload``.
    """
    stmt = select(BacktestRun).where(BacktestRun.id == run_id)
    if user_id is not None:
        stmt = stmt.where(BacktestRun.user_id == user_id)
    if with_metrics:
        stmt = stmt.options(selectinload(BacktestRun.metrics))
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_cached_run_by_hash(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    request_hash: str,
) -> BacktestRun | None:
    """Cache lookup: latest SUCCEEDED run for ``(user_id, request_hash)``.

    The DB's partial-unique index on the same columns guarantees at
    most one row matches. Returns ``None`` on cache miss.
    """
    stmt = (
        select(BacktestRun)
        .where(BacktestRun.user_id == user_id)
        .where(BacktestRun.request_hash == request_hash)
        .where(BacktestRun.status == BacktestRunStatus.SUCCEEDED.value)
        .options(selectinload(BacktestRun.metrics))
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_trades_page(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    cursor: int | None,
    page_size: int,
) -> tuple[list[BacktestTrade], bool, int | None]:
    """Return one page of trades ordered by ``trade_index ASC``.

    Keyset pagination on ``trade_index`` — ``cursor`` is the last
    seen index from the previous page (None = first page).

    Returns ``(rows, has_more, next_cursor)``:
        - ``rows`` — list of BacktestTrade ORM objects (≤ page_size)
        - ``has_more`` — True iff a page after this exists
        - ``next_cursor`` — the last ``trade_index`` in ``rows``,
          to be passed as ``cursor`` on the next call. None when
          ``has_more`` is False.
    """
    if page_size <= 0:
        raise ValueError(f"page_size must be > 0; got {page_size}.")

    stmt = (
        select(BacktestTrade)
        .where(BacktestTrade.run_id == run_id)
        .order_by(BacktestTrade.trade_index.asc())
        .limit(page_size + 1)
    )
    if cursor is not None:
        stmt = stmt.where(BacktestTrade.trade_index > cursor)

    rows = list((await db.execute(stmt)).scalars().all())
    has_more = len(rows) > page_size
    if has_more:
        rows = rows[:page_size]
    next_cursor = rows[-1].trade_index if (has_more and rows) else None
    return rows, has_more, next_cursor


__all__ = [
    "InvalidStatusTransitionError",
    "get_cached_run_by_hash",
    "get_run_by_id",
    "get_trades_page",
    "save_metrics",
    "save_run",
    "save_trades",
    "update_status",
]
