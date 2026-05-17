"""FastAPI router for the async backtest extension.

Three endpoints:

    POST /api/backtest                  enqueue + cache-lookup
    GET  /api/backtest/{id}             run summary + metrics
    GET  /api/backtest/{id}/trades      paginated trades

**Router is NOT registered in app.main on this skeleton branch.** Day 4
of the Week 2 sprint flips the registration on after a green test pass.

All handlers raise NotImplementedError until Day 4. The route shapes,
response models, error contracts, and OpenAPI metadata are wired now
so the supervised work is purely "fill the bodies."
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.backtest_extension.schemas import (
    BacktestEnqueueRequest,
    BacktestEnqueueResponse,
    BacktestRunOut,
    BacktestTradesResponse,
)
from app.db.models.user import User
from app.db.session import get_session


router = APIRouter(prefix="/api/backtest", tags=["backtest-extension"])


@router.post(
    "",
    response_model=BacktestEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue an async backtest (cache-aware)",
    responses={
        202: {"description": "New run accepted (cached=false)"},
        200: {"description": "Cached SUCCEEDED run reused (cached=true)"},
        422: {"description": "Invalid request (e.g. neither strategy_id nor strategy_config)"},
        429: {"description": "Rate limit — too many concurrent backtests"},
    },
)
async def enqueue_backtest_endpoint(
    body: BacktestEnqueueRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> BacktestEnqueueResponse:
    """Enqueue a backtest. Returns a 202 with run_id + cached flag.

    Flow (Day 4 Week 2 impl):
        1. Validate ``(strategy_id XOR strategy_config)`` — 422 else
        2. ``compute_request_hash(body)``
        3. ``fetch_cached_run(user, hash)`` — if hit, return 200 + cached=True
        4. ``persist_pending_run(...)`` → new run id
        5. ``run_backtest_task.apply_async(args=[run_id, body.model_dump(mode="json")], queue=BACKTEST_QUEUE)``
        6. Return 202 + cached=False
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "POST /api/backtest is a Week-2 Day-4 deliverable. See "
            "docs/BACKTEST_ENGINE_EXTENSION_PLAN.md."
        ),
    )


@router.get(
    "/{run_id}",
    response_model=BacktestRunOut,
    summary="Fetch one backtest run (metadata + metrics)",
    responses={
        200: {"description": "Run found (any status)"},
        404: {"description": "Unknown run id or not owned by caller"},
    },
)
async def get_backtest_run(
    run_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> BacktestRunOut:
    """Owner-scoped fetch of a single backtest_runs row joined with
    backtest_metrics (LEFT JOIN — metrics is None until SUCCEEDED).
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "GET /api/backtest/{id} is a Week-2 Day-4 deliverable. See "
            "docs/BACKTEST_ENGINE_EXTENSION_PLAN.md."
        ),
    )


@router.get(
    "/{run_id}/trades",
    response_model=BacktestTradesResponse,
    summary="Fetch paginated trades for a backtest run",
    responses={
        200: {"description": "Trades returned"},
        404: {"description": "Unknown run id or not owned by caller"},
        409: {"description": "Run not yet SUCCEEDED (trades not available)"},
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
            description="Last seen trade_index from the prior page. Omit for first page.",
        ),
    ] = None,
    page_size: Annotated[
        int,
        Query(ge=1, le=1000, description="Default 200 per page"),
    ] = 200,
) -> BacktestTradesResponse:
    """Owner-scoped paginated trades list.

    409 when the run exists but status is not SUCCEEDED — trades don't
    materialise into ``backtest_trades`` until SUCCEEDED.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "GET /api/backtest/{id}/trades is a Week-2 Day-4 deliverable. "
            "See docs/BACKTEST_ENGINE_EXTENSION_PLAN.md."
        ),
    )


__all__ = ["router"]
