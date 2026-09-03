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
from sqlalchemy.sql import Select

from app.api.deps import get_current_active_user
from app.auth.entitlements import require_active_plan
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


def _owner_executions_query(user_id: UUID, signal_id: UUID | None) -> Select:
    """The ONE owner-scoped executions query, shared by the list and the CSV
    export so the file a customer downloads can never disagree with the page
    they downloaded it from. Executions are user-scoped via their signal —
    join through — and ``subscription_id IS NULL`` excludes fan-out subscriber
    rows (see ``list_executions``)."""
    stmt = (
        select(StrategyExecution)
        .join(
            StrategySignal,
            StrategySignal.id == StrategyExecution.signal_id,
        )
        .where(
            StrategySignal.user_id == user_id,
            StrategyExecution.subscription_id.is_(None),
        )
        .order_by(StrategyExecution.placed_at.desc())
    )
    if signal_id is not None:
        stmt = stmt.where(StrategyExecution.signal_id == signal_id)
    return stmt


#: Columns in the CSV, in order. These are the fields the /trades page shows
#: plus the ids needed to reconcile against a broker statement. Deliberately
#: NOT ``broker_response`` (a raw JSON blob per row) and NOT
#: ``broker_credential_id`` (an internal key that means nothing to a customer).
_EXPORT_COLUMNS: tuple[str, ...] = (
    "id",
    "signal_id",
    "leg_number",
    "leg_role",
    "symbol",
    "side",
    "quantity",
    "order_type",
    "price",
    "broker_order_id",
    "broker_status",
    "error_code",
    "error_message",
    "placed_at",
    "completed_at",
)

#: Hard ceiling on rows per export. Well above any real account today (107
#: owner rows on prod at the time of writing) and low enough that the whole
#: file is built in memory without thought. Raise deliberately, not silently.
_EXPORT_MAX_ROWS = 10_000


def _csv_cell(value: object) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[no-any-return]
    return str(value)


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
