"""Approval-queue lifecycle: enqueue → decide / withdraw.

Service-layer enforcement of the "one pending request per
indicator" invariant — a 409 with a Hinglish detail beats a raw
IntegrityError. The migration deliberately *doesn't* enforce this
via partial unique index (SQLite doesn't support it cleanly).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.indicator_approval_queue import IndicatorApprovalQueue
from app.strategy_engine.indicator_admin.overrides import (
    create_direct_override,
)

#: Allowed values for ``IndicatorApprovalQueue.requested_status``.
_ALLOWED_REQUESTED: frozenset[str] = frozenset({"active", "deprecated"})


class QueueConflictError(Exception):
    """A pending request already exists for this indicator —
    second simultaneous request is rejected."""


class QueueStateError(Exception):
    """Tried to decide a request that's not pending (already
    approved / rejected / withdrawn)."""


async def enqueue_request(
    db: AsyncSession,
    *,
    indicator_id: str,
    requested_status: str,
    reason: str,
    requester_id: uuid.UUID,
    metadata: dict[str, Any] | None = None,
) -> IndicatorApprovalQueue:
    """File a request for an indicator status change.

    Raises :class:`QueueConflictError` if a pending request
    already exists for this indicator (first-writer-wins to
    avoid duplicate work for the admin reviewer).
    """
    if requested_status not in _ALLOWED_REQUESTED:
        raise ValueError(
            f"requested_status must be one of {sorted(_ALLOWED_REQUESTED)!r}; "
            f"got {requested_status!r}"
        )

    existing = (
        await db.execute(
            select(IndicatorApprovalQueue).where(
                IndicatorApprovalQueue.indicator_id == indicator_id,
                IndicatorApprovalQueue.status == "pending",
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise QueueConflictError(
            f"A pending request already exists for {indicator_id!r} "
            f"(queue id {existing.id})."
        )

    row = IndicatorApprovalQueue(
        indicator_id=indicator_id,
        requested_status=requested_status,
        request_reason=reason,
        requester_id=requester_id,
        request_metadata=metadata or {},
        status="pending",
    )
    db.add(row)
    await db.flush()
    return row


async def decide_request(
    db: AsyncSession,
    *,
    queue_id: uuid.UUID,
    decision: Literal["approve", "reject"],
    decision_by_user_id: uuid.UUID,
    notes: str,
) -> IndicatorApprovalQueue:
    """Approve or reject a pending request.

    Approving creates a corresponding override row + links it
    back via ``resulting_override_id``. Rejecting just stamps the
    decision fields. Either way the queue row's ``status`` flips
    out of ``pending`` (idempotent decision attempts get a
    :class:`QueueStateError`).
    """
    row = await db.get(IndicatorApprovalQueue, queue_id)
    if row is None:
        raise QueueStateError(f"Queue item {queue_id} not found.")
    if row.status != "pending":
        raise QueueStateError(
            f"Queue item {queue_id} is {row.status!r}, not pending — "
            "cannot decide."
        )

    now = datetime.now(UTC)
    if decision == "approve":
        override = await create_direct_override(
            db,
            indicator_id=row.indicator_id,
            new_status=row.requested_status,
            reason=f"Queue decision: {notes}",
            approved_by_user_id=decision_by_user_id,
            decision_metadata={
                "queue_id": str(queue_id),
                "request_metadata": row.request_metadata,
            },
        )
        row.resulting_override_id = override.id
        row.status = "approved"
    else:
        row.status = "rejected"

    row.decision_by_user_id = decision_by_user_id
    row.decision_at = now
    row.decision_notes = notes
    await db.flush()
    return row


async def withdraw_request(
    db: AsyncSession,
    *,
    queue_id: uuid.UUID,
    requester_id: uuid.UUID,
) -> IndicatorApprovalQueue:
    """Requester pulls back their own pending request.

    Only the original requester can withdraw — admins should
    reject (with a note) rather than withdraw, so the audit trail
    captures the reason.
    """
    row = await db.get(IndicatorApprovalQueue, queue_id)
    if row is None:
        raise QueueStateError(f"Queue item {queue_id} not found.")
    if row.requester_id != requester_id:
        raise QueueStateError(
            f"Queue item {queue_id} owned by a different user — "
            "only the requester can withdraw."
        )
    if row.status != "pending":
        raise QueueStateError(
            f"Queue item {queue_id} is {row.status!r}, not pending — "
            "cannot withdraw."
        )
    row.status = "withdrawn"
    row.decision_at = datetime.now(UTC)
    await db.flush()
    return row


async def list_pending_queue(
    db: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[IndicatorApprovalQueue]:
    """Pending requests in newest-first order — feeds the admin
    review queue."""
    rows = (
        (
            await db.execute(
                select(IndicatorApprovalQueue)
                .where(IndicatorApprovalQueue.status == "pending")
                .order_by(IndicatorApprovalQueue.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def list_my_requests(
    db: AsyncSession,
    *,
    requester_id: uuid.UUID,
) -> list[IndicatorApprovalQueue]:
    """Every request the calling user has filed — pending +
    closed. Drives the creator's "My Requests" view."""
    rows = (
        (
            await db.execute(
                select(IndicatorApprovalQueue)
                .where(IndicatorApprovalQueue.requester_id == requester_id)
                .order_by(IndicatorApprovalQueue.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


__all__ = [
    "QueueConflictError",
    "QueueStateError",
    "decide_request",
    "enqueue_request",
    "list_my_requests",
    "list_pending_queue",
    "withdraw_request",
]
