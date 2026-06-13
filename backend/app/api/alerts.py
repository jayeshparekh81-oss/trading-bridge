"""Per-user price alert CRUD — Queue HHH M10.

**STORAGE ONLY.** Alerts are persisted but NOT evaluated. The
background tick consumer + notification fanout = separate sprint.
The frontend page flags this clearly to the user; this docstring
flags it for any future maintainer.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.models.alert import (
    ALL_CONDITION_KINDS,
    Alert,
)
from app.db.models.user import User
from app.db.session import get_session

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    symbol: str = Field(..., min_length=1, max_length=64)
    condition_kind: str = Field(...)
    threshold: Decimal = Field(..., gt=Decimal("0"))


class AlertRead(BaseModel):
    id: str
    name: str
    symbol: str
    condition_kind: str
    threshold: str
    is_active: bool
    last_triggered_at: str | None
    created_at: str | None


class AlertListResponse(BaseModel):
    alerts: list[AlertRead]
    count: int


def _serialise(alert: Alert) -> AlertRead:
    return AlertRead(
        id=str(alert.id),
        name=alert.name,
        symbol=alert.symbol,
        condition_kind=alert.condition_kind,
        threshold=str(alert.threshold),
        is_active=alert.is_active,
        last_triggered_at=(
            alert.last_triggered_at.isoformat() if alert.last_triggered_at else None
        ),
        created_at=alert.created_at.isoformat() if alert.created_at else None,
    )


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> AlertListResponse:
    """List the caller's alerts (active + inactive)."""
    stmt = select(Alert).where(Alert.user_id == user.id).order_by(Alert.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return AlertListResponse(
        alerts=[_serialise(r) for r in rows],
        count=len(rows),
    )


@router.post(
    "",
    response_model=AlertRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_alert(
    body: AlertCreate,
    user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> AlertRead:
    """Create a new alert. STORAGE ONLY — alert will NOT fire until the
    evaluation engine ships in a future sprint."""
    if body.condition_kind not in ALL_CONDITION_KINDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"condition_kind must be one of {list(ALL_CONDITION_KINDS)}, "
                f"got {body.condition_kind!r}."
            ),
        )
    alert = Alert(
        user_id=user.id,
        name=body.name.strip(),
        symbol=body.symbol.strip().upper(),
        condition_kind=body.condition_kind,
        threshold=body.threshold,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return _serialise(alert)


@router.delete(
    "/{alert_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_alert(
    alert_id: UUID,
    user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Delete an alert. 404 if not owned by caller."""
    stmt = select(Alert).where(Alert.id == alert_id, Alert.user_id == user.id)
    alert = (await db.execute(stmt)).scalar_one_or_none()
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found.",
        )
    await db.delete(alert)
    await db.commit()


__all__ = ["router"]
