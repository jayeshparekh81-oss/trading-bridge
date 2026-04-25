"""AlgoMitra — chat transcript logging endpoint.

Phase 1A: clients post each user/assistant message; we persist them for
analytics and Phase 1B retriever bootstrap. The endpoint is intentionally
write-light — no AI response is generated server-side yet; the chat
content comes from pre-defined flows in the frontend.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.models.algomitra_message import AlgoMitraMessage, AlgoMitraRole
from app.db.models.user import User
from app.db.session import get_session

router = APIRouter(prefix="/api/algomitra", tags=["algomitra"])


# ─── Schemas ─────────────────────────────────────────────────────────────


class LogMessageRequest(BaseModel):
    """Body for POST /api/algomitra/messages."""

    session_id: UUID
    role: AlgoMitraRole
    content: str = Field(..., min_length=1, max_length=8000)
    flow_id: str | None = Field(default=None, max_length=64)
    flow_step: str | None = Field(default=None, max_length=64)
    has_image: bool = False


# ─── Routes ──────────────────────────────────────────────────────────────


@router.post("/messages", status_code=status.HTTP_201_CREATED)
async def log_message(
    body: LogMessageRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Append one message to the user's chat transcript."""
    msg = AlgoMitraMessage(
        user_id=user.id,
        session_id=body.session_id,
        role=body.role,
        content=body.content,
        flow_id=body.flow_id,
        flow_step=body.flow_step,
        has_image=body.has_image,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return {"id": str(msg.id), "created_at": msg.created_at.isoformat()}


@router.get("/sessions/{session_id}/messages")
async def list_session_messages(
    session_id: UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
    limit: int = Query(200, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Fetch messages for a session (owner-scoped)."""
    stmt = (
        select(AlgoMitraMessage)
        .where(
            AlgoMitraMessage.user_id == user.id,
            AlgoMitraMessage.session_id == session_id,
        )
        .order_by(AlgoMitraMessage.created_at.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "session_id": str(m.session_id),
            "role": m.role.value if hasattr(m.role, "value") else m.role,
            "content": m.content,
            "flow_id": m.flow_id,
            "flow_step": m.flow_step,
            "has_image": m.has_image,
            "created_at": m.created_at.isoformat(),
        }
        for m in rows
    ]


@router.get("/sessions")
async def list_user_sessions(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Recent session ids for this user, newest first."""
    stmt = (
        select(
            AlgoMitraMessage.session_id,
            AlgoMitraMessage.created_at,
        )
        .where(AlgoMitraMessage.user_id == user.id)
        .order_by(AlgoMitraMessage.created_at.desc())
        .limit(limit * 10)
    )
    result = await db.execute(stmt)
    rows = result.all()

    seen: dict[UUID, str] = {}
    for session_id, created_at in rows:
        if session_id in seen:
            continue
        seen[session_id] = created_at.isoformat()
        if len(seen) >= limit:
            break

    return [
        {"session_id": str(sid), "started_at": started}
        for sid, started in seen.items()
    ]


__all__ = ["router"]
