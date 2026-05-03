"""Kill-switch HTTP API.

Auth: prefers JWT (``Authorization: Bearer ...``). Falls back to the
legacy ``X-User-Id`` header for the existing test suite + ops scripts
that haven't migrated yet. JWT is checked first; absent or invalid
JWT triggers the X-User-Id fallback; absent/invalid both → 401.

Migration to JWT-only is deferred until all callers (tests, scripts)
move over — tracked in docs/FRONTEND_NEXT_SPRINT.md.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security_ext import (
    generate_session_fingerprint,
    validate_session_token,
)
from app.db.session import get_session
from app.schemas.kill_switch import (
    KillSwitchConfigCreate,
    KillSwitchConfigResponse,
    KillSwitchDailySummary,
    KillSwitchEventSchema,
    KillSwitchResetRequest,
    KillSwitchStatus,
    KillSwitchTestResult,
)
from app.services.kill_switch_service import kill_switch_service

router = APIRouter(prefix="/api/kill-switch", tags=["kill-switch"])


# ═══════════════════════════════════════════════════════════════════════
# Auth — JWT preferred, X-User-Id fallback
# ═══════════════════════════════════════════════════════════════════════


async def _current_user(
    request: Request,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> UUID:
    """Resolve the acting user.

    Path A (JWT): ``Authorization: Bearer <token>`` validates the
    session token directly and returns the ``sub`` claim as a UUID.
    Path B (legacy): ``X-User-Id: <uuid>`` header — kept for the
    existing test suite + ops curl scripts that haven't migrated yet.
    Raises 401 if neither is usable.
    """
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:]
        fingerprint = generate_session_fingerprint(
            user_agent=request.headers.get("User-Agent", ""),
            ip=request.client.host if request.client else "",
        )
        claims = await validate_session_token(
            token, current_fingerprint=fingerprint
        )
        sub = (claims or {}).get("sub")
        if sub:
            try:
                return UUID(sub)
            except ValueError:
                pass  # fall through to X-User-Id

    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization (Bearer) or X-User-Id header required.",
        )
    try:
        return UUID(x_user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-User-Id.",
        ) from exc


# ═══════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════


@router.get("/status", response_model=KillSwitchStatus)
async def get_status(
    user_id: UUID = Depends(_current_user),
    session: AsyncSession = Depends(get_session),
) -> KillSwitchStatus:
    return await kill_switch_service.get_status(user_id, session)


@router.get("/config", response_model=KillSwitchConfigResponse)
async def get_config(
    user_id: UUID = Depends(_current_user),
    session: AsyncSession = Depends(get_session),
) -> KillSwitchConfigResponse:
    row = await kill_switch_service.get_config(user_id, session)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kill-switch not configured.",
        )
    return KillSwitchConfigResponse.model_validate(row)


@router.put("/config", response_model=KillSwitchConfigResponse)
async def update_config(
    payload: KillSwitchConfigCreate,
    user_id: UUID = Depends(_current_user),
    session: AsyncSession = Depends(get_session),
) -> KillSwitchConfigResponse:
    row = await kill_switch_service.update_config(user_id, payload, session)
    await session.commit()
    return KillSwitchConfigResponse.model_validate(row)


@router.post("/reset-token")
async def request_reset_token(
    user_id: UUID = Depends(_current_user),
) -> dict[str, str]:
    token = await kill_switch_service.create_reset_token(user_id)
    return {"confirmation_token": token}


@router.post("/reset")
async def manual_reset(
    payload: KillSwitchResetRequest,
    user_id: UUID = Depends(_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    try:
        await kill_switch_service.manual_reset(
            user_id,
            reset_by=user_id,
            confirmation_token=payload.confirmation_token,
            session=session,
        )
        await session.commit()
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return {"status": "reset"}


@router.get("/history", response_model=list[KillSwitchEventSchema])
async def history(
    limit: int = Query(default=50, ge=1, le=500),
    user_id: UUID = Depends(_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[KillSwitchEventSchema]:
    rows = await kill_switch_service.get_trip_history(
        user_id, session, limit=limit
    )
    return [KillSwitchEventSchema.model_validate(r) for r in rows]


@router.post("/test", response_model=KillSwitchTestResult)
async def test_trip(
    user_id: UUID = Depends(_current_user),
    session: AsyncSession = Depends(get_session),
) -> KillSwitchTestResult:
    return await kill_switch_service.test_trip(user_id, session)


@router.post("/trip")
async def manual_trip(
    payload: KillSwitchResetRequest,
    user_id: UUID = Depends(_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Operator-initiated kill-switch trip.

    Mirrors :func:`manual_reset` — requires a ``confirmation_token``
    from ``POST /reset-token`` so a stray dashboard click can't fire
    the full square-off chain. ``force_reason=MANUAL`` so the
    threshold logic doesn't second-guess the operator's intent.
    """
    import hmac

    from app.core import redis_client
    from app.schemas.kill_switch import TripReason
    from app.services.kill_switch_service import _reset_token_key

    client = redis_client.get_redis()
    expected = await client.get(_reset_token_key(user_id))
    if not expected or not hmac.compare_digest(
        expected, payload.confirmation_token
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation token invalid or expired.",
        )
    await client.delete(_reset_token_key(user_id))

    result = await kill_switch_service.check_and_trigger(
        user_id, session, force_reason=TripReason.MANUAL
    )
    await session.commit()
    return {
        "status": "tripped" if result.triggered else "not_tripped",
        "event_id": str(result.event_id) if result.event_id else "",
    }


@router.get("/daily-summary", response_model=KillSwitchDailySummary)
async def daily_summary(
    user_id: UUID = Depends(_current_user),
    session: AsyncSession = Depends(get_session),
) -> KillSwitchDailySummary:
    return await kill_switch_service.get_daily_summary(user_id, session)


__all__ = ["router"]
