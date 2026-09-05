"""Strategy-engine read API — signals + executions.

Authenticated; users only see their own rows.
"""

from __future__ import annotations

import csv
import io
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.auth.entitlements import require_active_plan
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
from app.services.owner_executions import (
    EXPORT_COLUMNS,
    EXPORT_MAX_ROWS,
    csv_cell,
    owner_executions_query,
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal not found.")
    return StrategySignalRead.model_validate(sig)


@router.get("/executions", response_model=StrategyExecutionListResponse)
async def list_executions(
    current_user: Annotated[User, Depends(require_active_plan)],
    db: Annotated[AsyncSession, Depends(get_session)],
    signal_id: UUID | None = Query(default=None),
    limit: int = Query(100, ge=1, le=500),
) -> StrategyExecutionListResponse:
    """List the current user's OWN executions — optionally scoped to one signal.

    Owner-scoped: ``subscription_id IS NULL`` excludes marketplace fan-out
    subscriber (paper) execution rows, which carry a non-NULL ``subscription_id``
    and link to the OWNER's signal. Without this they would surface under the
    owner's trades view once ``MARKETPLACE_FANOUT_ENABLED`` flips. This mirrors
    the internal owner lookups (entry-sum / exit / position-loop /
    reconciliation), which already filter ``subscription_id IS NULL``. Per-
    subscription subscriber views are a separate, additive endpoint (later).
    """
    stmt = _owner_executions_query(current_user.id, signal_id).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    items = [StrategyExecutionRead.model_validate(r) for r in rows]
    return StrategyExecutionListResponse(executions=items, count=len(items))


# The owner-scoped query, the CSV columns and the cell formatter live in ONE
# shared module so the /trades page, its export, and the analytics surfaces
# (app/api/users.py) can never disagree with each other.
_owner_executions_query = owner_executions_query
_EXPORT_COLUMNS = EXPORT_COLUMNS
_EXPORT_MAX_ROWS = EXPORT_MAX_ROWS
_csv_cell = csv_cell


@router.get("/executions/export")
async def export_executions(
    current_user: Annotated[User, Depends(require_active_plan)],
    db: Annotated[AsyncSession, Depends(get_session)],
    signal_id: UUID | None = Query(default=None),
) -> StreamingResponse:
    """Download the current user's OWN executions as CSV.

    WHY THIS EXISTS. ``GET /api/users/me/trades/export`` already streams CSV —
    of the legacy ``trades`` table, which the strategy engine never writes
    (0 rows on prod). The /trades page shows ``strategy_executions``. Wiring a
    button to the old endpoint would have shipped a control that downloads an
    empty file. This exports exactly what the page shows, through the SAME
    query (``_owner_executions_query``), gated the SAME way
    (``require_active_plan``, tier-blind like every other gate today).

    Same-request, in-memory: the file is fully built before the response
    starts, so a mid-stream DB error can never truncate a download silently.
    """
    stmt = _owner_executions_query(current_user.id, signal_id).limit(_EXPORT_MAX_ROWS)
    rows = (await db.execute(stmt)).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_EXPORT_COLUMNS)
    for r in rows:
        writer.writerow([_csv_cell(getattr(r, col)) for col in _EXPORT_COLUMNS])
    buf.seek(0)

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="tradetri-executions.csv"',
            "Cache-Control": "no-store",
        },
    )


__all__ = ["router"]
