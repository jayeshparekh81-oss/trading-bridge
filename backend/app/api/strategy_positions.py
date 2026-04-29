"""Strategy-engine positions API — list + kill switch.

The kill-switch endpoint here is the strategy-engine variant: it closes
every open ``StrategyPosition`` for the calling user and marks any
``received`` / ``validating`` signals as rejected so an in-flight AI
call cannot turn into an order after the user has hit the brake.

This is distinct from :mod:`app.api.kill_switch` which is the platform-
wide circuit breaker — both can coexist.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.logging import get_logger
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.db.session import get_session
from app.schemas.strategy_position import (
    KillSwitchResponse,
    StrategyPositionListResponse,
    StrategyPositionRead,
)
from app.services.position_manager import close_position_now

logger = get_logger("app.api.strategy_positions")

router = APIRouter(prefix="/api/strategies", tags=["strategy-engine"])


@router.get("/positions", response_model=StrategyPositionListResponse)
async def list_positions(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
) -> StrategyPositionListResponse:
    """List the current user's positions, newest first."""
    stmt = (
        select(StrategyPosition)
        .where(StrategyPosition.user_id == current_user.id)
        .order_by(StrategyPosition.opened_at.desc())
        .limit(limit)
    )
    if status_filter:
        stmt = stmt.where(StrategyPosition.status == status_filter)

    rows = (await db.execute(stmt)).scalars().all()
    items = [StrategyPositionRead.model_validate(r) for r in rows]
    return StrategyPositionListResponse(positions=items, count=len(items))


@router.post("/kill-switch", response_model=KillSwitchResponse)
async def trigger_kill_switch(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> KillSwitchResponse:
    """Close all open strategy-engine positions for the user.

    Side effects:
        * Every ``open`` / ``partial`` :class:`StrategyPosition` row gets
          a closing ``StrategyExecution`` and is marked ``closed``.
        * Every ``received`` / ``validating`` :class:`StrategySignal` is
          flipped to ``rejected`` with a kill-switch note.

    Idempotent — re-calling on a clean state returns 0/0.
    """
    # 1. Close open positions
    pos_stmt = select(StrategyPosition).where(
        StrategyPosition.user_id == current_user.id,
        StrategyPosition.status.in_(("open", "partial")),
    )
    positions = (await db.execute(pos_stmt)).scalars().all()
    for pos in positions:
        await close_position_now(
            db, position=pos, reason="kill_switch", ltp=None
        )

    # 2. Reject in-flight signals
    sig_stmt = (
        update(StrategySignal)
        .where(
            StrategySignal.user_id == current_user.id,
            StrategySignal.status.in_(("received", "validating")),
        )
        .values(
            status="rejected",
            notes="kill switch invoked",
            processed_at=datetime.now(UTC),
        )
        .execution_options(synchronize_session=False)
    )
    sig_result = await db.execute(sig_stmt)
    rejected_count = sig_result.rowcount or 0

    await db.commit()

    logger.info(
        "strategy_positions.kill_switch_triggered",
        user_id=str(current_user.id),
        positions_closed=len(positions),
        signals_rejected=rejected_count,
    )

    return KillSwitchResponse(
        positions_closed=len(positions),
        signals_rejected=rejected_count,
        message=(
            f"Closed {len(positions)} position(s); rejected "
            f"{rejected_count} pending signal(s)."
        ),
    )


__all__ = ["router"]
