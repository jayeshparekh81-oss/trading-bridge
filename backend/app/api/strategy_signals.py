"""Strategy-engine read API — signals + executions.

Authenticated; users only see their own rows.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.db.session import get_session
from app.schemas.strategy_execution import (
    StrategyExecutionListResponse,
    StrategyExecutionRead,
)
from app.schemas.strategy_signal import (
    StrategySignalListResponse,
    StrategySignalRead,
)

router = APIRouter(prefix="/api/strategies", tags=["strategy-engine"])


@router.get("/signals", response_model=StrategySignalListResponse)
async def list_signals(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(50, ge=1, le=500),
    status_filter: str | None = Query(default=None, alias="status"),
) -> StrategySignalListResponse:
    """List the current user's strategy signals, newest first."""
    stmt = (
        select(StrategySignal)
        .where(StrategySignal.user_id == current_user.id)
        .order_by(StrategySignal.received_at.desc())
        .limit(limit)
    )
    if status_filter:
        stmt = stmt.where(StrategySignal.status == status_filter)

    rows = (await db.execute(stmt)).scalars().all()
    items = [StrategySignalRead.model_validate(r) for r in rows]
    return StrategySignalListResponse(signals=items, count=len(items))


@router.get("/signals/{signal_id}", response_model=StrategySignalRead)
async def get_signal(
    signal_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> StrategySignalRead:
    """Return a single signal, including AI decision + execution metadata."""
    sig = await db.get(StrategySignal, signal_id)
    if sig is None or sig.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Signal not found."
        )
    return StrategySignalRead.model_validate(sig)


@router.get("/executions", response_model=StrategyExecutionListResponse)
async def list_executions(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    signal_id: UUID | None = Query(default=None),
    limit: int = Query(100, ge=1, le=500),
) -> StrategyExecutionListResponse:
    """List the current user's executions — optionally scoped to one signal."""
    # Executions are user-scoped via their signal — join through.
    stmt = (
        select(StrategyExecution)
        .join(
            StrategySignal,
            StrategySignal.id == StrategyExecution.signal_id,
        )
        .where(StrategySignal.user_id == current_user.id)
        .order_by(StrategyExecution.placed_at.desc())
        .limit(limit)
    )
    if signal_id is not None:
        stmt = stmt.where(StrategyExecution.signal_id == signal_id)

    rows = (await db.execute(stmt)).scalars().all()
    items = [StrategyExecutionRead.model_validate(r) for r in rows]
    return StrategyExecutionListResponse(executions=items, count=len(items))


__all__ = ["router"]
