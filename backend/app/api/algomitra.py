"""AlgoMitra — chat endpoint backed by Claude (Phase 1B).

Wire: rate-limit gate → load last N messages → build privacy-safe
context → call AlgoMitraAI → save user + assistant rows → return
``{message, suggestions, tone, usage}`` to the frontend.

If the AI call fails for any reason (API outage, key missing, rate
limit upstream) the endpoint returns a 503 with a fallback message —
the frontend then drops back to the static flow library so the chat
never feels broken.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.algomitra_message import AlgoMitraMessage, AlgoMitraRole
from app.db.models.user import User
from app.db.session import get_session
from app.services.algomitra_ai import AlgoMitraAI, AlgoMitraAIError
from app.services.rate_limiter import check_and_increment, peek
from app.services.user_context import build_user_context

router = APIRouter(prefix="/api/algomitra", tags=["algomitra"])

_logger = get_logger("api.algomitra")

#: Frontend uses this string when the API is unreachable to render a
#: graceful fallback bubble before flipping to the static flow library.
_FALLBACK_MESSAGE = (
    "Bhai, abhi technical issue hai. Static help options niche dikha "
    "raha hoon. Urgent ho toh founder ko WhatsApp kar."
)


# ─── Schemas ─────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    """Body for ``POST /api/algomitra/messages`` — AI chat call."""

    session_id: UUID
    message: str = Field(..., min_length=1, max_length=4000)
    current_page: str | None = Field(default=None, max_length=128)
    has_image: bool = False


class ChatUsage(BaseModel):
    """Per-message token + cost summary returned to the frontend."""

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    cost_inr: str
    daily_used: int
    daily_limit: int
    daily_remaining: int


class ChatResponse(BaseModel):
    """Body returned by ``POST /api/algomitra/messages``."""

    message: str
    suggestions: list[str]
    tone: str
    user_message_id: str
    assistant_message_id: str
    usage: ChatUsage


# ─── Routes ──────────────────────────────────────────────────────────────


@router.post("/messages", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_session),
) -> ChatResponse:
    """Send a user message to AlgoMitra (Claude) and return the response."""
    settings = get_settings()
    daily_limit = settings.algomitra_daily_message_limit

    # 1. Rate-limit gate (atomic INCR + EXPIRE).
    rate = await check_and_increment(user.id, daily_limit=daily_limit)
    if not rate.allowed:
        retry_after = max(int((rate.reset_at - datetime.now(UTC)).total_seconds()), 60)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Bhai, aaj ka chat limit hit ({daily_limit}). Kal milte hain! "
                "Urgent? WhatsApp pe message karo."
            ),
            headers={"Retry-After": str(retry_after)},
        )

    # 2. Persist the user turn first — even if the AI call fails we still
    #    have the question logged for analytics.
    user_msg = AlgoMitraMessage(
        user_id=user.id,
        session_id=body.session_id,
        role=AlgoMitraRole.USER,
        content=body.message,
        has_image=body.has_image,
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    # 3. Load the last N messages of this session (oldest → newest).
    history_stmt = (
        select(AlgoMitraMessage)
        .where(
            AlgoMitraMessage.user_id == user.id,
            AlgoMitraMessage.session_id == body.session_id,
            AlgoMitraMessage.id != user_msg.id,
        )
        .order_by(AlgoMitraMessage.created_at.desc())
        .limit(settings.algomitra_max_history)
    )
    rows = list((await db.execute(history_stmt)).scalars().all())
    rows.reverse()  # oldest → newest
    history = [
        {"role": r.role.value if hasattr(r.role, "value") else str(r.role), "content": r.content}
        for r in rows
    ]

    # 4. Build privacy-safe user context.
    context = await build_user_context(user, db, current_page=body.current_page)

    # 5. Call Claude.
    try:
        ai = AlgoMitraAI()
        result = await ai.chat(
            user_message=body.message,
            history=history,
            user_context=context,
        )
    except AlgoMitraAIError as exc:
        _logger.warning(
            "algomitra.chat_failed", user_id=str(user.id), error=str(exc)
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_FALLBACK_MESSAGE,
        ) from exc

    # 6. Persist the assistant turn (with token + cost stats).
    assistant_msg = AlgoMitraMessage(
        user_id=user.id,
        session_id=body.session_id,
        role=AlgoMitraRole.ASSISTANT,
        content=result.message,
        has_image=False,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cache_read_tokens=result.cache_read_tokens,
        cache_creation_tokens=result.cache_creation_tokens,
        cost_inr=result.cost_inr,
        tone=result.tone,
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)

    # 7. Return — include rate-limit headers for the frontend.
    return ChatResponse(
        message=result.message,
        suggestions=list(result.suggestions),
        tone=result.tone,
        user_message_id=str(user_msg.id),
        assistant_message_id=str(assistant_msg.id),
        usage=ChatUsage(
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cache_read_tokens=result.cache_read_tokens,
            cache_creation_tokens=result.cache_creation_tokens,
            cost_inr=str(result.cost_inr),
            daily_used=rate.used,
            daily_limit=rate.limit,
            daily_remaining=rate.remaining,
        ),
    )


@router.get("/quota")
async def quota(
    user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """Read-only quota check — useful for showing remaining count in the UI."""
    settings = get_settings()
    rate = await peek(user.id, daily_limit=settings.algomitra_daily_message_limit)
    return {
        "used": rate.used,
        "limit": rate.limit,
        "remaining": rate.remaining,
        "reset_at": rate.reset_at.isoformat(),
    }


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
            "tone": m.tone,
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
