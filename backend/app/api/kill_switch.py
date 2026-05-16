"""Kill-switch HTTP API.

Auth: JWT only via ``Depends(get_current_active_user)`` — the same
dependency every other authenticated route uses. The acting user is
derived from the validated JWT's ``sub`` claim; the request body and
headers are never trusted for caller identity.

Safety fix #4 (2026-05-16): the previous ``_current_user`` dependency
also accepted an unauthenticated ``X-User-Id`` header as a fallback,
which let any caller impersonate any user on all 9 kill-switch
endpoints. That fallback has been removed entirely.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.models.user import User
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
from app.strategy_engine.audit.loggers import log_kill_switch_event

router = APIRouter(prefix="/api/kill-switch", tags=["kill-switch"])


# ═══════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════


@router.get("/status", response_model=KillSwitchStatus)
async def get_status(
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> KillSwitchStatus:
    return await kill_switch_service.get_status(user.id, session)


@router.get("/config", response_model=KillSwitchConfigResponse)
async def get_config(
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> KillSwitchConfigResponse:
    row = await kill_switch_service.get_config(user.id, session)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kill-switch not configured.",
        )
    return KillSwitchConfigResponse.model_validate(row)


@router.put("/config", response_model=KillSwitchConfigResponse)
async def update_config(
    payload: KillSwitchConfigCreate,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> KillSwitchConfigResponse:
    row = await kill_switch_service.update_config(user.id, payload, session)
    await session.commit()
    return KillSwitchConfigResponse.model_validate(row)


@router.post("/reset-token")
async def request_reset_token(
    user: User = Depends(get_current_active_user),
) -> dict[str, str]:
    token = await kill_switch_service.create_reset_token(user.id)
    return {"confirmation_token": token}


@router.post("/reset")
async def manual_reset(
    payload: KillSwitchResetRequest,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    try:
        await kill_switch_service.manual_reset(
            user.id,
            reset_by=user.id,
            confirmation_token=payload.confirmation_token,
            session=session,
        )
        await session.commit()
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    log_kill_switch_event(
        strategy_id=None,
        user_id=user.id,
        action="reset",
        reason="manual_reset",
    )
    return {"status": "reset"}


@router.get("/history", response_model=list[KillSwitchEventSchema])
async def history(
    limit: int = Query(default=50, ge=1, le=500),
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> list[KillSwitchEventSchema]:
    rows = await kill_switch_service.get_trip_history(
        user.id, session, limit=limit
    )
    return [KillSwitchEventSchema.model_validate(r) for r in rows]


@router.post("/test", response_model=KillSwitchTestResult)
async def test_trip(
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> KillSwitchTestResult:
    return await kill_switch_service.test_trip(user.id, session)


@router.post("/trip")
async def manual_trip(
    payload: KillSwitchResetRequest,
    user: User = Depends(get_current_active_user),
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
    expected = await client.get(_reset_token_key(user.id))
    if not expected or not hmac.compare_digest(
        expected, payload.confirmation_token
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation token invalid or expired.",
        )
    await client.delete(_reset_token_key(user.id))

    result = await kill_switch_service.check_and_trigger(
        user.id, session, force_reason=TripReason.MANUAL
    )
    await session.commit()
    log_kill_switch_event(
        strategy_id=None,
        user_id=user.id,
        action="triggered",
        reason="manual_trip",
    )
    return {
        "status": "tripped" if result.triggered else "not_tripped",
        "event_id": str(result.event_id) if result.event_id else "",
    }


@router.get("/daily-summary", response_model=KillSwitchDailySummary)
async def daily_summary(
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> KillSwitchDailySummary:
    return await kill_switch_service.get_daily_summary(user.id, session)


__all__ = ["router"]
