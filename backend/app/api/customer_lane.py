"""Customer-lane status surface. READ-ONLY — no endpoint here writes or arms anything.

Mounted only when CUSTOMER_LANE_STATUS_API_ENABLED is true. That flag defaults FALSE,
so a deploy of this branch changes no existing route.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_admin
from app.db.models.customer_lane import CustomerBrokerLink
from app.db.session import get_session
from app.domains.customer_lane.status import (MID_DAY_JOIN_RULE, board_summary,
                                              customer_line, founder_board)

router = APIRouter(prefix="/api/customer-lane", tags=["customer-lane"])

IST = timezone(timedelta(hours=5, minutes=30))


def _today() -> "datetime.date":
    return datetime.now(IST).date()


class StatusLineOut(BaseModel):
    customer_id: uuid.UUID
    connected: bool
    reason: str
    eligibility: str
    message: str
    token_expires_at: datetime | None
    reminders_sent: list[str]


class BoardOut(BaseModel):
    trading_date: str
    summary: dict[str, int]
    rows: list[StatusLineOut]
    mid_day_join_rule: str


def _out(line) -> StatusLineOut:
    return StatusLineOut(customer_id=line.customer_id, connected=line.connected,
                         reason=line.reason, eligibility=line.eligibility.value,
                         message=line.message, token_expires_at=line.token_expires_at,
                         reminders_sent=line.reminders_sent)


@router.get("/me/status", response_model=StatusLineOut)
async def my_status(user=Depends(get_current_active_user),
                    session: AsyncSession = Depends(get_session)) -> StatusLineOut:
    """A customer may read ONLY their own line. The id comes from the token, never
    from the request, so one customer cannot address another's status."""
    line = await customer_line(session, user.id, trading_date=_today())
    return _out(line)


@router.get("/board", response_model=BoardOut)
async def board(user=Depends(get_current_admin),
                session: AsyncSession = Depends(get_session)) -> BoardOut:
    ids = list((await session.execute(
        select(CustomerBrokerLink.customer_id))).scalars().all())
    today = _today()
    lines = await founder_board(session, ids, trading_date=today)
    return BoardOut(trading_date=today.isoformat(),
                    summary=board_summary(lines), rows=[_out(l) for l in lines],
                    mid_day_join_rule=MID_DAY_JOIN_RULE)


__all__ = ["router"]
