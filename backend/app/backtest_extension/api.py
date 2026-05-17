"""FastAPI router for the async backtest extension.

Three endpoints:

    POST /api/backtest                  enqueue + idempotency cache lookup
    GET  /api/backtest/{run_id}         run summary + metrics
    GET  /api/backtest/{run_id}/trades  paginated trades

**Router is NOT registered in `app/main.py` on this branch** (hard
guardrail #4). Founder mounts after review.

Day-1-3 contract:
    * ``strategy_id`` is REQUIRED (anonymous-config preview rejected
      with 422 per decision D8 — Phase 7 work).
    * Owner-scoping: 404 (not 403) on cross-user reads (decision D15).
    * Trades on non-SUCCEEDED runs: 409 (decision D16).
    * Idempotency: cache hit returns 200 with ``cached=True`` +
      existing run id. Miss creates new PENDING row + dispatches
      Celery + returns 202.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.backtest_extension import idempotency, persistence
from app.backtest_extension.rate_limit import enforce_backtest_rate_limit
from app.backtest_extension.schemas import (
    BacktestEnqueueRequest,
    BacktestEnqueueResponse,
    BacktestMetricsOut,
    BacktestRunOut,
    BacktestRunStatus,
    BacktestTradeOut,
    BacktestTradesResponse,
)
from app.core.logging import get_logger
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.db.session import get_session

logger = get_logger("app.backtest_extension.api")

router = APIRouter(prefix="/api/backtest", tags=["backtest-extension"])


# ─── Helpers ────────────────────────────────────────────────────────────


async def _verify_owned_strategy(
    db: AsyncSession, *, strategy_id: uuid.UUID, user_id: uuid.UUID
) -> Strategy:
    """Load + own-check a Strategy row. 422 on miss (the request
    referenced an unknown / unowned strategy)."""
    stmt = (
        select(Strategy)
        .where(Strategy.id == strategy_id)
        .where(Strategy.user_id == user_id)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Strategy {strategy_id} not found or not owned by caller.",
        )
    if not row.strategy_json:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Strategy has no DSL configured (legacy or cloned-from-"
                "template). Recreate via Phase 5 builder to make it "
                "backtest-ready."
            ),
        )
    return row


def _to_metrics_out(metrics) -> BacktestMetricsOut | None:  # type: ignore[no-untyped-def]
    """Convert a BacktestMetrics ORM row to the Pydantic boundary type."""
    if metrics is None:
        return None
    return BacktestMetricsOut(
        total_pnl=float(metrics.total_pnl),
        total_return_percent=float(metrics.total_return_percent),
        win_rate=float(metrics.win_rate),
        loss_rate=float(metrics.loss_rate),
        total_trades=metrics.total_trades,
        average_win=float(metrics.average_win),
        average_loss=float(metrics.average_loss),
        largest_win=float(metrics.largest_win),
        largest_loss=float(metrics.largest_loss),
        max_drawdown=float(metrics.max_drawdown),
        profit_factor=(
            float(metrics.profit_factor) if metrics.profit_factor is not None else None
        ),
        expectancy=float(metrics.expectancy),
        warnings=list(metrics.warnings or []),
    )


def _to_run_out(run) -> BacktestRunOut:  # type: ignore[no-untyped-def]
    """Convert a BacktestRun ORM row (with eager-loaded metrics) to the
    Pydantic response."""
    return BacktestRunOut(
        id=run.id,
        user_id=run.user_id,
        strategy_id=run.strategy_id,
        request_hash=run.request_hash,
        engine_version=run.engine_version,
        status=BacktestRunStatus(run.status),
        started_at=run.started_at,
        completed_at=run.completed_at,
        error=run.error_json,
        metrics=_to_metrics_out(run.metrics),
    )


def _to_trade_out(row) -> BacktestTradeOut:  # type: ignore[no-untyped-def]
    return BacktestTradeOut(
        id=row.id,
        trade_index=row.trade_index,
        entry_time=row.entry_time,
        exit_time=row.exit_time,
        side=row.side,
        entry_price=float(row.entry_price),
        exit_price=float(row.exit_price),
        quantity=float(row.quantity),
        pnl=float(row.pnl),
        exit_reason=row.exit_reason,
        entry_reasons=list(row.entry_reasons or []),
    )


# ─── POST /api/backtest ────────────────────────────────────────────────


@router.post(
    "",
    response_model=BacktestEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue an async backtest (cache-aware)",
    responses={
        202: {"description": "New run accepted (cached=false)"},
        200: {"description": "Cached SUCCEEDED run reused (cached=true)"},
        422: {
            "description": (
                "Invalid request — anonymous-config preview is Day-1-3 rejected; "
                "strategy_id required and must be owned."
            )
        },
        429: {
            "description": (
                "Rate limit exceeded. Either per-hour cap "
                "(BACKTEST_RATE_LIMIT_PER_HOUR, default 30) OR concurrent "
                "cap (BACKTEST_RATE_LIMIT_CONCURRENT, default 5). "
                "Response includes Retry-After header."
            )
        },
    },
)
async def enqueue_backtest(
    body: BacktestEnqueueRequest,
    response: Response,
    current_user: Annotated[User, Depends(enforce_backtest_rate_limit)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> BacktestEnqueueResponse:
    """Enqueue a backtest. Returns 202 on cache miss, 200 on cache hit.

    Day-1-3 contract:
        * ``strategy_id`` REQUIRED. ``strategy_config`` returns 422.
        * Strategy ownership verified before any Celery dispatch.
        * Cache lookup is ``(user_id, request_hash) WHERE status='SUCCEEDED'``.

    Future Day-5 work adds rate-limit middleware here (decision D7).
    """
    # Day-1-3 anonymous-config rejection (decision D8)
    if body.strategy_config is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Anonymous-config preview is not yet supported. Pass "
                "strategy_id pointing to an owned Strategy. Anonymous-config "
                "is Phase 7 work."
            ),
        )
    if body.strategy_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="strategy_id is required.",
        )

    # Verify ownership BEFORE any hash/cache operation
    strategy = await _verify_owned_strategy(
        db, strategy_id=body.strategy_id, user_id=current_user.id
    )

    # Build the idempotency hash
    request_hash = idempotency.compute_hash_from_request(
        strategy_id=strategy.id,
        strategy_config=None,
        symbol=body.symbol,
        timeframe=body.timeframe,
        start=body.start,
        end=body.end,
        initial_capital=body.initial_capital,
        quantity=body.quantity,
        cost_settings=body.cost_settings,
        ambiguity_mode=body.ambiguity_mode,
    )
    engine_ver = idempotency.engine_version()

    # Cache lookup
    cached = await persistence.get_cached_run_by_hash(
        db, user_id=current_user.id, request_hash=request_hash
    )
    if cached is not None:
        response.status_code = status.HTTP_200_OK
        logger.info(
            "backtest.enqueue.cache_hit",
            user_id=str(current_user.id),
            run_id=str(cached.id),
            request_hash=request_hash,
        )
        return BacktestEnqueueResponse(
            run_id=cached.id,
            status=BacktestRunStatus.SUCCEEDED,
            cached=True,
            request_hash=request_hash,
            engine_version=engine_ver,
        )

    # Cache miss → persist new PENDING run + dispatch Celery task
    payload = body.model_dump(mode="json", exclude_none=True)
    new_run = await persistence.save_run(
        db,
        user_id=current_user.id,
        strategy_id=strategy.id,
        request_payload=payload,
        request_hash=request_hash,
        engine_version=engine_ver,
    )
    await db.commit()

    # Dispatch Celery — lazy import so unit tests can mock at module level
    # without importing celery at FastAPI app boot.
    from app.backtest_extension.celery_tasks import run_backtest_task

    run_backtest_task.apply_async(args=[str(new_run.id)])

    logger.info(
        "backtest.enqueue.dispatched",
        user_id=str(current_user.id),
        run_id=str(new_run.id),
        request_hash=request_hash,
    )
    return BacktestEnqueueResponse(
        run_id=new_run.id,
        status=BacktestRunStatus.PENDING,
        cached=False,
        request_hash=request_hash,
        engine_version=engine_ver,
    )


# ─── GET /api/backtest/{run_id} ────────────────────────────────────────


@router.get(
    "/{run_id}",
    response_model=BacktestRunOut,
    summary="Fetch one backtest run (metadata + metrics)",
    responses={
        200: {"description": "Run found"},
        404: {"description": "Unknown run id or not owned by caller"},
    },
)
async def get_backtest_run(
    run_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> BacktestRunOut:
    """Owner-scoped fetch of a backtest_runs row + joined metrics."""
    run = await persistence.get_run_by_id(
        db, run_id=run_id, user_id=current_user.id, with_metrics=True
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found.",
        )
    return _to_run_out(run)


# ─── GET /api/backtest/{run_id}/trades ─────────────────────────────────


@router.get(
    "/{run_id}/trades",
    response_model=BacktestTradesResponse,
    summary="Paginated trades for a SUCCEEDED backtest",
    responses={
        200: {"description": "Trades returned"},
        404: {"description": "Unknown run id or not owned by caller"},
        409: {"description": "Run exists but is not SUCCEEDED"},
    },
)
async def get_backtest_trades(
    run_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    cursor: Annotated[
        int | None,
        Query(
            ge=0,
            description="Last seen trade_index from prior page. Omit for first page.",
        ),
    ] = None,
    page_size: Annotated[
        int,
        Query(ge=1, le=1000, description="Default 200 per page; max 1000"),
    ] = 200,
) -> BacktestTradesResponse:
    """Owner-scoped paginated trades list (keyset by trade_index ASC).

    409 when the run exists but status != SUCCEEDED (trades don't
    materialise until SUCCEEDED — decision D16).
    """
    run = await persistence.get_run_by_id(
        db, run_id=run_id, user_id=current_user.id, with_metrics=False
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found.",
        )
    if run.status != BacktestRunStatus.SUCCEEDED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run status is {run.status}; trades available only on SUCCEEDED.",
        )

    rows, has_more, next_cursor = await persistence.get_trades_page(
        db, run_id=run_id, cursor=cursor, page_size=page_size
    )
    return BacktestTradesResponse(
        run_id=run_id,
        trades=[_to_trade_out(r) for r in rows],
        page_size=page_size,
        has_more=has_more,
        next_cursor=next_cursor,
    )


__all__ = ["router"]
