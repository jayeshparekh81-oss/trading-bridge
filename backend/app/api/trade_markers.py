"""HTTP routes for the Phase A trade-markers stack.

Two endpoints, both authenticated + ownership-gated:

    GET /api/markers
        ?strategy_id=<uuid> (required)
        &mode=BACKTEST|PAPER|LIVE (required)
        &from=<iso8601>     (optional, tz-aware)
        &to=<iso8601>       (optional, tz-aware)
        &symbol=<str>       (optional)
        &side=<MarkerSide>  (optional)
        &limit=<1..500>     (default 100)
        &offset=<int>       (default 0)
        → 200 :class:`TradeMarkerListResponse`

    GET /api/markers/strategy/{strategy_id}/summary
        ?mode=BACKTEST|PAPER|LIVE (required)
        → 200 :class:`TradeMarkerSummary`

The route lives at ``/api/markers`` deliberately — the existing
``/api/chart/markers`` route (legacy paper-trade derivation) stays
mounted in parallel. Phase B+ migrates the read path here; until
then, both coexist.

Auth + authorisation
    * JWT via ``get_current_active_user`` — same dep every other
      authenticated route uses.
    * Strategy ownership: the user MUST own ``strategy_id``. We
      collapse "doesn't exist" + "not yours" into one 403 so
      existence cannot be probed.

Router registration
    This router is **not** registered in ``main.py`` yet — see
    ``backend/PATCH_INSTRUCTIONS_PHASE_A.md`` for the manual
    ``include_router`` line. New-files-only rule on parallel-CC
    branches forbids editing shared files; Jayesh applies the
    patch as part of the morning review.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.logging import bind_request_context, get_logger
from app.db.models.strategy import Strategy
from app.db.models.trade_marker import MarkerMode, MarkerSide
from app.db.models.user import User
from app.db.session import get_session
from app.schemas.trade_marker import (
    TradeMarkerListResponse,
    TradeMarkerRead,
    TradeMarkerSummary,
)
from app.services.marker_emitter import (
    get_markers_by_strategy,
    get_strategy_summary,
)


_logger = get_logger("api.trade_markers")


router = APIRouter(prefix="/api/markers", tags=["trade-markers"])


# ─── Helpers ───────────────────────────────────────────────────────────


async def _assert_strategy_owned_by_user(
    db: AsyncSession,
    *,
    strategy_id: uuid.UUID,
    user: User,
) -> Strategy:
    """Load the strategy + assert ownership.

    Existence and ownership are collapsed into a single 403 response
    so a sequence of guess-and-check requests can't probe whether a
    given strategy id exists.
    """
    stmt = select(Strategy).where(Strategy.id == strategy_id)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None or row.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Is strategy ke markers dekhne ka access nahi hai. "
                "Strategy ID confirm karo aur apni login session check karo."
            ),
        )
    return row


def _validate_time_window(
    from_ts: datetime | None,
    to_ts: datetime | None,
) -> None:
    """Reject naive timestamps and an inverted window. ``None`` is OK."""
    for label, ts in (("from", from_ts), ("to", to_ts)):
        if ts is not None and ts.tzinfo is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"{label} ISO 8601 timezone-aware hona chahiye "
                    "(e.g. 2026-05-14T09:15:00+05:30)."
                ),
            )
    if from_ts is not None and to_ts is not None and from_ts > to_ts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from is greater than to — invalid window.",
        )


# ─── Endpoints ─────────────────────────────────────────────────────────


@router.get("", response_model=TradeMarkerListResponse)
async def list_markers(
    strategy_id: Annotated[uuid.UUID, Query(...)],
    mode: Annotated[MarkerMode, Query(...)],
    from_ts: Annotated[datetime | None, Query(alias="from")] = None,
    to_ts: Annotated[datetime | None, Query(alias="to")] = None,
    symbol: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    side: Annotated[MarkerSide | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> TradeMarkerListResponse:
    """Paginated marker list for one strategy + mode."""
    bind_request_context(
        user_id=str(user.id),
        strategy_id=str(strategy_id),
        mode=mode.value,
    )
    _validate_time_window(from_ts, to_ts)
    await _assert_strategy_owned_by_user(
        db, strategy_id=strategy_id, user=user
    )

    rows, total = await get_markers_by_strategy(
        db,
        strategy_id=strategy_id,
        mode=mode,
        from_ts=from_ts,
        to_ts=to_ts,
        symbol=symbol,
        side=side,
        limit=limit,
        offset=offset,
    )
    return TradeMarkerListResponse(
        strategy_id=strategy_id,
        mode=mode,
        limit=limit,
        offset=offset,
        total=total,
        markers=[TradeMarkerRead.model_validate(r) for r in rows],
    )


@router.get(
    "/strategy/{strategy_id}/summary",
    response_model=TradeMarkerSummary,
)
async def strategy_summary(
    strategy_id: Annotated[uuid.UUID, Path(...)],
    mode: Annotated[MarkerMode, Query(...)],
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> TradeMarkerSummary:
    """Aggregate stats for one strategy + mode (EXIT rows only)."""
    bind_request_context(
        user_id=str(user.id),
        strategy_id=str(strategy_id),
        mode=mode.value,
    )
    await _assert_strategy_owned_by_user(
        db, strategy_id=strategy_id, user=user
    )
    return await get_strategy_summary(
        db, strategy_id=strategy_id, mode=mode
    )


__all__ = ["router"]
