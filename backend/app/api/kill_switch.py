"""Kill-switch HTTP API.

All endpoints require ``X-User-Id`` — stand-in for authenticated identity
until the JWT layer lands. The header is validated as a UUID so callers
cannot pass arbitrary strings and confuse downstream queries.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

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
# Auth stub
# ═══════════════════════════════════════════════════════════════════════


async def _current_user(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> UUID:
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Id header required.",
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


@router.get("/daily-summary", response_model=KillSwitchDailySummary)
async def daily_summary(
    user_id: UUID = Depends(_current_user),
    session: AsyncSession = Depends(get_session),
) -> KillSwitchDailySummary:
    return await kill_switch_service.get_daily_summary(user_id, session)


__all__ = ["router"]
