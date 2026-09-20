"""Customer Support API.

Six endpoints under ``/api/support``:

    POST   /tickets             — create a ticket (any auth)
    GET    /tickets/me          — list caller's tickets
    GET    /tickets/{id}        — fetch one (must own OR be admin)
    GET    /tickets             — list all (admin-only, paginated)
    PUT    /tickets/{id}        — admin-only status / priority / assignee
    DELETE /tickets/{id}        — admin-only soft-delete (status=closed)

Notification routing (20 Sep 2026): a new ticket now reaches a human.

:func:`_notify_admin_stub` still emits the structured
``support.ticket.email_stub`` line — nothing that tails that log
loses it — and :func:`_notify_admin_telegram` additionally fires the
**existing, already-working** operator Telegram path
(:mod:`app.services.telegram_alerts`), the same route the
reconciliation loop, the truth check and the marketplace fan-out
already use. No second alerting route was invented, no SMTP client
and no new credential.

Before this change a new ticket notified NOBODY: the stub wrote a log
line and stopped, while the published help FAQ promised a *"human reply
in 24-48 hours"*. ``support_tickets`` was at 0 rows, so no real customer
had yet been burned — the first ticket ever filed would have sat unseen.

The send can never break ticket creation: ``send_alert`` swallows its own
errors by design, and the call here is additionally wrapped, so a Telegram
outage costs the alert and nothing else. Email (Phase 2) can still be
added later; it is not what makes the promise true.

Auto-priority by category lives in :func:`_priority_for_category`.
The mapping is part of the deploy-time contract, not env-driven —
flipping a category's default priority requires a code change +
test update.
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.auth.roles import require_admin
from app.core.logging import get_logger
from app.db.models.support_ticket import SupportTicket
from app.db.models.user import User
from app.db.session import get_session

logger = get_logger("app.strategy_engine.api.support")

router = APIRouter(prefix="/api/support", tags=["support"])


_VALID_CATEGORIES = (
    "bug",
    "billing",
    "broker_connection",
    "strategy_help",
    "account",
    "other",
)

_VALID_STATUSES = (
    "open",
    "in_progress",
    "awaiting_user",
    "resolved",
    "closed",
)

_VALID_PRIORITIES = ("low", "medium", "high", "critical")

#: Words that bump a ``bug`` ticket from ``high`` to ``critical``.
#: Match is case-insensitive on the description.
_CRITICAL_KEYWORDS = re.compile(
    r"\b(crash|crashing|data\s+loss|lost\s+money|cannot\s+log\s*in|"
    r"locked\s+out|broker\s+disconnect|critical|urgent)\b",
    re.IGNORECASE,
)


# ─── Boundary models ───────────────────────────────────────────────────


class SupportTicketCreate(BaseModel):
    """POST body — minimal: category + subject + description."""

    model_config = ConfigDict(extra="forbid")

    category: Literal[
        "bug", "billing", "broker_connection", "strategy_help", "account", "other"
    ]
    subject: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=5_000)


class SupportTicketUpdate(BaseModel):
    """PUT body (admin-only) — partial. Each field optional; unset
    fields don't change the ticket."""

    model_config = ConfigDict(extra="forbid")

    status: (
        Literal[
            "open", "in_progress", "awaiting_user", "resolved", "closed"
        ]
        | None
    ) = None
    priority: (
        Literal["low", "medium", "high", "critical"] | None
    ) = None
    assigned_admin_id: uuid.UUID | None = None


class SupportTicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    category: str
    subject: str
    description: str
    status: str
    priority: str
    attachments: list[str]
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    assigned_admin_id: uuid.UUID | None


class SupportTicketListResponse(BaseModel):
    tickets: list[SupportTicketRead]
    count: int


# ─── Helpers ───────────────────────────────────────────────────────────


def _priority_for_category(category: str, description: str) -> str:
    """Auto-priority schedule from the spec.

    * ``billing`` and ``broker_connection`` — high (revenue + access).
    * ``bug`` — high by default; critical when the description
      contains a known severity keyword.
    * ``account`` and ``strategy_help`` — medium.
    * ``other`` — low.
    """
    if category == "billing" or category == "broker_connection":
        return "high"
    if category == "bug":
        return "critical" if _CRITICAL_KEYWORDS.search(description) else "high"
    if category in ("account", "strategy_help"):
        return "medium"
    return "low"


def _notify_admin_stub(ticket: SupportTicket) -> None:
    """Phase 1 email stub. Logs a structured line in the format the
    Phase 2 SMTP client will mirror — preserves the same payload
    shape so downstream tooling (log aggregator searches, alerting
    rules) doesn't need to change when real email lands."""
    to_address = os.environ.get(
        "SUPPORT_EMAIL_TO", "support@tradetri.com"
    )
    description_preview = (
        ticket.description[:200] + ("…" if len(ticket.description) > 200 else "")
    )
    logger.info(
        "support.ticket.email_stub",
        to=to_address,
        ticket_id=str(ticket.id),
        user_id=str(ticket.user_id),
        category=ticket.category,
        priority=ticket.priority,
        subject=ticket.subject,
        description_preview=description_preview,
    )


#: Ticket priority -> operator alert level.
#:
#: The keys are the REAL vocabulary and nothing else: ``_priority_for_category``
#: and both ``Literal`` schemas in this module agree on
#: ``low | medium | high | critical``. The first draft of this map used
#: ``urgent``, a value this codebase has never produced, so a genuinely
#: ``critical`` bug would have fallen through to the default and arrived at the
#: same volume as a billing question — a SILENT DOWNGRADE, which is the one
#: failure mode an alert map must never have. Caught by reading
#: ``_priority_for_category`` instead of trusting the draft.
#:
#: The default is deliberately WARNING, not INFO: if a new priority value is ever
#: added and nobody updates this map, the ticket must still be loud.
_ALERT_LEVEL_FOR_PRIORITY = {
    "critical": "CRITICAL",
    "high": "WARNING",
    "medium": "WARNING",
    "low": "INFO",
}


async def _notify_admin_telegram(ticket: SupportTicket) -> None:
    """Send ONE operator Telegram line for a newly created ticket.

    Reuses the existing operator alert path rather than inventing a second
    one. Deliberately carries NO customer email or name: the founder's chat
    is not the right place for customer PII, and everything he needs to
    reply is one click away in the admin ticket view. The line says what to
    DO, not merely what happened.

    Never raises. Ticket creation must not depend on Telegram being up.
    """
    try:
        from app.services.telegram_alerts import AlertLevel, send_alert

        level = AlertLevel(
            _ALERT_LEVEL_FOR_PRIORITY.get(str(ticket.priority), "WARNING")
        )
        preview = ticket.description[:200] + (
            "…" if len(ticket.description) > 200 else ""
        )
        await send_alert(
            level,
            "NAYA SUPPORT TICKET\n"
            f"category: {ticket.category} | priority: {ticket.priority}\n"
            f"subject: {ticket.subject}\n"
            f"{preview}\n"
            f"ticket: {ticket.id}\n"
            f"user: {ticket.user_id}\n"
            "Kya karna hai: admin > Support me kholo aur jawab do. "
            "Site par 24-48 ghante ka vaada likha hai.",
        )
    except Exception:  # noqa: BLE001 - an alert must never break ticket creation
        logger.warning(
            "support.ticket.telegram_failed",
            ticket_id=str(ticket.id),
            exc_info=True,
        )


def _to_read(ticket: SupportTicket) -> SupportTicketRead:
    return SupportTicketRead(
        id=ticket.id,
        user_id=ticket.user_id,
        category=ticket.category,
        subject=ticket.subject,
        description=ticket.description,
        status=ticket.status,
        priority=ticket.priority,
        attachments=list(ticket.attachments or []),
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        resolved_at=ticket.resolved_at,
        assigned_admin_id=ticket.assigned_admin_id,
    )


async def _load_owned_or_admin(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    user: User,
) -> SupportTicket:
    """Fetch + visibility check. Owners + admins see; everyone else
    gets 404 (not 403) — same enumeration-guard reasoning as the
    rest of the engine."""
    stmt = select(SupportTicket).where(SupportTicket.id == ticket_id)
    ticket = (await db.execute(stmt)).scalar_one_or_none()
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found.",
        )
    is_admin = user.role in ("admin", "super_admin") or getattr(user, "is_admin", False)
    if ticket.user_id != user.id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found.",
        )
    return ticket


# ─── User endpoints ────────────────────────────────────────────────────


@router.post(
    "/tickets",
    response_model=SupportTicketRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_ticket(
    body: SupportTicketCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> SupportTicketRead:
    """File a new support ticket. Auto-priority, the structured log line
    and the operator Telegram alert all fire inline. The Telegram send can
    never fail the request."""
    priority = _priority_for_category(body.category, body.description)
    ticket = SupportTicket(
        user_id=current_user.id,
        category=body.category,
        subject=body.subject,
        description=body.description,
        status="open",
        priority=priority,
        attachments=[],
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    _notify_admin_stub(ticket)
    await _notify_admin_telegram(ticket)
    logger.info(
        "support.ticket.created",
        ticket_id=str(ticket.id),
        user_id=str(current_user.id),
        category=body.category,
        priority=priority,
    )
    # Analytics — additive, safe-to-fail.
    from app.observability import track_event

    track_event(
        user_id=str(current_user.id),
        event_name="support_ticket_created",
        properties={"category": body.category, "priority": priority},
    )
    return _to_read(ticket)


@router.get("/tickets/me", response_model=SupportTicketListResponse)
async def list_my_tickets(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> SupportTicketListResponse:
    """Caller's tickets, newest first. All statuses included so
    the user's own dashboard surfaces resolved + closed tickets too."""
    rows = (
        await db.execute(
            select(SupportTicket)
            .where(SupportTicket.user_id == current_user.id)
            .order_by(SupportTicket.created_at.desc())
        )
    ).scalars().all()
    items = [_to_read(r) for r in rows]
    return SupportTicketListResponse(tickets=items, count=len(items))


@router.get("/tickets/{ticket_id}", response_model=SupportTicketRead)
async def get_ticket(
    ticket_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> SupportTicketRead:
    """Owner-or-admin only — anyone else gets 404."""
    ticket = await _load_owned_or_admin(db, ticket_id, current_user)
    return _to_read(ticket)


# ─── Admin endpoints ───────────────────────────────────────────────────


@router.get("/tickets", response_model=SupportTicketListResponse)
async def list_all_tickets(
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
    status_filter: (
        Literal["open", "in_progress", "awaiting_user", "resolved", "closed"]
        | None
    ) = Query(default=None, alias="status"),
    priority_filter: (
        Literal["low", "medium", "high", "critical"] | None
    ) = Query(default=None, alias="priority"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SupportTicketListResponse:
    """Admin queue. Filterable by status + priority, paginated.

    Default order: open + critical first, then by ``created_at``
    ascending so the oldest-but-still-open tickets surface at the
    top of the queue. The composite index
    ``(status, priority, created_at)`` makes this index-only."""
    stmt = select(SupportTicket)
    if status_filter is not None:
        stmt = stmt.where(SupportTicket.status == status_filter)
    if priority_filter is not None:
        stmt = stmt.where(SupportTicket.priority == priority_filter)
    stmt = (
        stmt.order_by(
            SupportTicket.status,
            SupportTicket.priority.desc(),
            SupportTicket.created_at.asc(),
        )
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).scalars().all()
    items = [_to_read(r) for r in rows]
    return SupportTicketListResponse(tickets=items, count=len(items))


@router.put("/tickets/{ticket_id}", response_model=SupportTicketRead)
async def update_ticket(
    ticket_id: uuid.UUID,
    body: SupportTicketUpdate,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> SupportTicketRead:
    """Admin updates: status, priority, assignee. Setting
    ``status='resolved'`` populates ``resolved_at`` automatically;
    flipping back out of ``resolved`` clears it."""
    ticket = (
        await db.execute(
            select(SupportTicket).where(SupportTicket.id == ticket_id)
        )
    ).scalar_one_or_none()
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found.",
        )

    now = datetime.now(UTC)
    if body.status is not None:
        ticket.status = body.status
        if body.status == "resolved" and ticket.resolved_at is None:
            ticket.resolved_at = now
        elif body.status != "resolved" and ticket.resolved_at is not None:
            ticket.resolved_at = None
    if body.priority is not None:
        ticket.priority = body.priority
    if body.assigned_admin_id is not None:
        ticket.assigned_admin_id = body.assigned_admin_id

    await db.commit()
    await db.refresh(ticket)
    logger.info(
        "support.ticket.updated",
        ticket_id=str(ticket.id),
        admin_id=str(admin.id),
        status=ticket.status,
        priority=ticket.priority,
    )
    return _to_read(ticket)


@router.delete(
    "/tickets/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def soft_delete_ticket(
    ticket_id: uuid.UUID,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Soft-delete: flips status to ``closed`` rather than dropping
    the row. Keeps the audit trail intact."""
    ticket = (
        await db.execute(
            select(SupportTicket).where(SupportTicket.id == ticket_id)
        )
    ).scalar_one_or_none()
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found.",
        )
    ticket.status = "closed"
    await db.commit()
    logger.info(
        "support.ticket.soft_deleted",
        ticket_id=str(ticket.id),
        admin_id=str(admin.id),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
