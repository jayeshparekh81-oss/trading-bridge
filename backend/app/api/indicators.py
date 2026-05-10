"""User-facing indicator endpoints.

Two surfaces:

* **Creator** (``require_creator_or_above``): file + view their
  own promotion / deprecation requests.
* **Public** (any authenticated user): resolve the effective status
  for an indicator id — useful for UIs that render an indicator
  picker and want to label statuses correctly without going through
  the registry default.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.auth.roles import require_creator_or_above
from app.core.logging import get_logger
from app.db.models.user import User
from app.db.session import get_session
from app.strategy_engine.indicator_admin import (
    enqueue_request,
    list_my_requests,
    resolve_effective_status,
    withdraw_request,
)
from app.strategy_engine.indicator_admin.approval import (
    QueueConflictError,
    QueueStateError,
)
from app.strategy_engine.indicators.registry import get_indicator_by_id

logger = get_logger("app.api.indicators")

router = APIRouter(prefix="/api/indicators", tags=["indicators"])


# ─── Wire shapes ──────────────────────────────────────────────────────


class StatusResponse(BaseModel):
    indicator_id: str
    status: str
    source: str = Field(
        ..., description="``registry_default`` or ``override``."
    )
    override_reason: str | None = None
    approved_at: datetime | None = None


class CreatorRequestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    indicator_id: str = Field(..., min_length=1, max_length=64)
    requested_status: Literal["active", "deprecated"]
    reason: str = Field(..., min_length=1, max_length=2048)
    metadata: dict[str, Any] | None = None


class QueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    indicator_id: str
    requested_status: str
    request_reason: str
    requester_id: uuid.UUID
    request_metadata: dict[str, Any]
    status: str
    decision_at: datetime | None = None
    decision_notes: str | None = None
    created_at: datetime


class MyRequestsResponse(BaseModel):
    requests: list[QueueItem]
    count: int


# ─── Public ──────────────────────────────────────────────────────────


@router.get("/{indicator_id}/status", response_model=StatusResponse)
async def public_status(
    indicator_id: str,
    _user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> StatusResponse:
    """Resolve the effective status for an indicator id.

    Returns the registry default when no override exists. Returns
    404 when the id is in neither the registry nor any override —
    callers who get 404 should treat the id as "unknown" rather
    than rendering it.
    """
    effective = await resolve_effective_status(db, indicator_id)
    if effective.status == "unknown":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Indicator {indicator_id!r} not found.",
        )
    return StatusResponse(
        indicator_id=indicator_id,
        status=effective.status,
        source=effective.source,
        override_reason=effective.override_reason,
        approved_at=effective.approved_at,
    )


# ─── Creator ─────────────────────────────────────────────────────────


@router.post(
    "/queue",
    response_model=QueueItem,
    status_code=status.HTTP_201_CREATED,
)
async def file_request(
    body: CreatorRequestPayload,
    user: Annotated[User, Depends(require_creator_or_above)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> QueueItem:
    """File a promotion / deprecation request for an indicator.

    Returns 404 if the indicator id isn't in the registry — the
    queue is for known indicators only.
    Returns 409 if a pending request already exists for the same
    id (one queue item at a time per indicator).
    """
    if get_indicator_by_id(body.indicator_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Indicator {body.indicator_id!r} not in registry.",
        )
    try:
        row = await enqueue_request(
            db,
            indicator_id=body.indicator_id,
            requested_status=body.requested_status,
            reason=body.reason,
            requester_id=user.id,
            metadata=body.metadata,
        )
    except QueueConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    await db.commit()
    await db.refresh(row)
    logger.info(
        "indicator.request_filed",
        indicator_id=body.indicator_id,
        requester_id=str(user.id),
        requested_status=body.requested_status,
    )
    return QueueItem.model_validate(row)


@router.get("/queue/me", response_model=MyRequestsResponse)
async def my_requests(
    user: Annotated[User, Depends(require_creator_or_above)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> MyRequestsResponse:
    """Every request the calling creator has filed — pending +
    closed."""
    rows = await list_my_requests(db, requester_id=user.id)
    return MyRequestsResponse(
        requests=[QueueItem.model_validate(r) for r in rows],
        count=len(rows),
    )


@router.post("/queue/{queue_id}/withdraw", response_model=QueueItem)
async def withdraw(
    queue_id: uuid.UUID,
    user: Annotated[User, Depends(require_creator_or_above)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> QueueItem:
    """Pull back your own pending request. Only the original
    requester can withdraw — admins should reject (with notes)
    instead so the audit trail captures the reason."""
    try:
        row = await withdraw_request(
            db, queue_id=queue_id, requester_id=user.id
        )
    except QueueStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    await db.commit()
    await db.refresh(row)
    return QueueItem.model_validate(row)


__all__ = ["router"]
