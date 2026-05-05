"""User-built strategy CRUD — Phase 5 backend.

Endpoints (all require an authenticated, active user; rows are scoped
to ``current_user.id``):

    GET    /api/strategies            list user's strategies, newest first
    POST   /api/strategies            create from a validated StrategyJSON
    GET    /api/strategies/{id}       fetch one
    PUT    /api/strategies/{id}       replace (full StrategyJSON)
    DELETE /api/strategies/{id}       hard-delete

The router mounts under ``/api/strategies`` — the same prefix used by
:mod:`app.api.strategy_positions` (``/positions``, ``/kill-switch``)
and :mod:`app.api.strategy_signals` (``/signals``, ``/executions``).
Coexistence relies on FastAPI's first-match-wins routing: those literal
paths must be registered *before* this router so they win over
``/{strategy_id}``. ``app.main._register_routers`` enforces the order.

The ``Strategy.name`` column is denormalised from
``strategy_json.name`` on every write so list pages can order by name
without parsing JSONB. ``Strategy.updated_at`` updates server-side via
``TimestampMixin``'s ``onupdate=func.now()`` — the handler does not set
it explicitly.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.logging import get_logger
from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.api.schemas import (
    StrategyCreateRequest,
    StrategyListResponse,
    StrategyResponse,
)

logger = get_logger("app.strategy_engine.api.strategies")

router = APIRouter(prefix="/api/strategies", tags=["strategy-engine"])


@router.get("", response_model=StrategyListResponse)
async def list_strategies(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> StrategyListResponse:
    """Return every strategy owned by the calling user, newest first."""
    stmt = (
        select(Strategy)
        .where(Strategy.user_id == current_user.id)
        .order_by(Strategy.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    items = [StrategyResponse.model_validate(r) for r in rows]
    return StrategyListResponse(strategies=items, count=len(items))


@router.post(
    "", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED
)
async def create_strategy(
    body: StrategyCreateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> StrategyResponse:
    """Persist a new StrategyJSON for the calling user."""
    payload = body.strategy_json.model_dump(by_alias=True, mode="json")
    strategy = Strategy(
        user_id=current_user.id,
        name=body.strategy_json.name,
        strategy_json=payload,
        is_active=True,
    )
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)
    logger.info(
        "strategy.created",
        user_id=str(current_user.id),
        strategy_id=str(strategy.id),
    )
    return StrategyResponse.model_validate(strategy)


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> StrategyResponse:
    """Fetch one strategy by id, scoped to the calling user."""
    strategy = await _load_owned_strategy(db, current_user, strategy_id)
    return StrategyResponse.model_validate(strategy)


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: uuid.UUID,
    body: StrategyCreateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> StrategyResponse:
    """Replace the StrategyJSON for an owned strategy."""
    strategy = await _load_owned_strategy(db, current_user, strategy_id)
    strategy.name = body.strategy_json.name
    strategy.strategy_json = body.strategy_json.model_dump(
        by_alias=True, mode="json"
    )
    await db.commit()
    await db.refresh(strategy)
    logger.info(
        "strategy.updated",
        user_id=str(current_user.id),
        strategy_id=str(strategy_id),
    )
    return StrategyResponse.model_validate(strategy)


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(
    strategy_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Hard-delete an owned strategy."""
    strategy = await _load_owned_strategy(db, current_user, strategy_id)
    await db.delete(strategy)
    await db.commit()
    logger.info(
        "strategy.deleted",
        user_id=str(current_user.id),
        strategy_id=str(strategy_id),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _load_owned_strategy(
    db: AsyncSession, user: User, strategy_id: uuid.UUID
) -> Strategy:
    """Fetch a strategy scoped to ``user``; 404 covers both 'not found'
    and 'not yours' so cross-user probes can't distinguish them."""
    stmt = select(Strategy).where(
        Strategy.id == strategy_id, Strategy.user_id == user.id
    )
    strategy = (await db.execute(stmt)).scalar_one_or_none()
    if strategy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found.",
        )
    return strategy


__all__ = ["router"]
