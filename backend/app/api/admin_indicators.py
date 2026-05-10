"""Admin-only indicator approval endpoints.

Sits next to ``app.api.admin`` (which handles user / audit-log
admin) — keeps each admin surface in its own module so the file
sizes stay reasonable as the admin tooling expands.

Every endpoint here gates on :func:`require_admin`. Approvals
write to the audit log via the queue-decision path, so a third-
party reviewer reading audit_logs sees the full chain (request →
decision → resulting override).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.roles import require_admin
from app.core.logging import get_logger
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.indicator_admin import (
    create_direct_override,
    decide_request,
    get_indicator_history,
    list_active_overrides,
    list_pending_queue,
    resolve_effective_status,
)
from app.strategy_engine.indicator_admin.approval import (
    QueueStateError,
)
from app.strategy_engine.indicators.registry import get_indicator_by_id

logger = get_logger("app.api.admin_indicators")

router = APIRouter(prefix="/api/admin/indicators", tags=["admin-indicators"])


# ─── Wire shapes ──────────────────────────────────────────────────────


class QueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    indicator_id: str
    requested_status: str
    request_reason: str
    requester_id: uuid.UUID
    request_metadata: dict[str, Any]
    status: str
    decision_by_user_id: uuid.UUID | None = None
    decision_at: datetime | None = None
    decision_notes: str | None = None
    resulting_override_id: uuid.UUID | None = None
    created_at: datetime


class QueueListResponse(BaseModel):
    queue: list[QueueItem]
    count: int


class OverrideRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    indicator_id: str
    override_status: str
    override_reason: str
    approved_by_user_id: uuid.UUID
    approved_at: datetime
    effective_from: datetime
    effective_until: datetime | None = None
    prior_status: str | None = None
    prior_status_source: str | None = None
    decision_metadata: dict[str, Any]


class OverrideListResponse(BaseModel):
    overrides: list[OverrideRow]
    count: int


class HistoryResponse(BaseModel):
    indicator_id: str
    current_status: str
    history: list[OverrideRow]


class DecisionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    notes: str = Field(..., min_length=1, max_length=2048)


class DirectOverridePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_status: Literal[
        "active", "coming_soon", "experimental", "deprecated"
    ]
    reason: str = Field(..., min_length=1, max_length=2048)
    effective_until: datetime | None = None


# ─── Endpoints ────────────────────────────────────────────────────────


@router.get("/queue", response_model=QueueListResponse)
async def list_queue(
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> QueueListResponse:
    """Pending requests in newest-first order. Closed requests
    show up in indicator-specific history, not here."""
    rows = await list_pending_queue(db, limit=limit, offset=offset)
    return QueueListResponse(
        queue=[QueueItem.model_validate(r) for r in rows],
        count=len(rows),
    )


@router.get("/queue/{queue_id}", response_model=QueueItem)
async def queue_detail(
    queue_id: uuid.UUID,
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> QueueItem:
    from app.db.models.indicator_approval_queue import (
        IndicatorApprovalQueue,
    )

    row = await db.get(IndicatorApprovalQueue, queue_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue item not found.",
        )
    return QueueItem.model_validate(row)


@router.post(
    "/queue/{queue_id}/decide", response_model=QueueItem
)
async def decide_queue_item(
    queue_id: uuid.UUID,
    body: DecisionPayload,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> QueueItem:
    """Approve or reject a pending queue item."""
    try:
        row = await decide_request(
            db,
            queue_id=queue_id,
            decision=body.decision,
            decision_by_user_id=admin.id,
            notes=body.notes,
        )
    except QueueStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    await db.commit()
    await db.refresh(row)
    logger.info(
        "indicator_admin.queue_decided",
        queue_id=str(queue_id),
        decision=body.decision,
        admin_id=str(admin.id),
    )
    return QueueItem.model_validate(row)


@router.post(
    "/{indicator_id}/override", response_model=OverrideRow
)
async def direct_override(
    indicator_id: str,
    body: DirectOverridePayload,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> OverrideRow:
    """Skip the queue: admin sets a status directly. Used for
    emergency promotions / deprecations.

    Returns 404 when the indicator id is not in the registry —
    overrides target known ids only (preventing typo-creation
    of phantom overrides)."""
    if get_indicator_by_id(indicator_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Indicator {indicator_id!r} not in registry.",
        )
    row = await create_direct_override(
        db,
        indicator_id=indicator_id,
        new_status=body.new_status,
        reason=body.reason,
        approved_by_user_id=admin.id,
        effective_until=body.effective_until,
        decision_metadata={"path": "direct_override"},
    )
    await db.commit()
    await db.refresh(row)
    logger.info(
        "indicator_admin.direct_override",
        indicator_id=indicator_id,
        new_status=body.new_status,
        admin_id=str(admin.id),
    )
    return OverrideRow.model_validate(row)


@router.get("/overrides", response_model=OverrideListResponse)
async def list_overrides(
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> OverrideListResponse:
    """Currently-effective overrides across all indicators."""
    rows = await list_active_overrides(db)
    return OverrideListResponse(
        overrides=[OverrideRow.model_validate(r) for r in rows],
        count=len(rows),
    )


@router.get(
    "/{indicator_id}/history", response_model=HistoryResponse
)
async def indicator_history(
    indicator_id: str,
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> HistoryResponse:
    """All historical override rows for one indicator + the
    current effective status. The "registry default" never
    appears as a history row — it's the implicit baseline."""
    rows = await get_indicator_history(db, indicator_id)
    effective = await resolve_effective_status(db, indicator_id)
    return HistoryResponse(
        indicator_id=indicator_id,
        current_status=effective.status,
        history=[OverrideRow.model_validate(r) for r in rows],
    )


__all__ = ["router"]
