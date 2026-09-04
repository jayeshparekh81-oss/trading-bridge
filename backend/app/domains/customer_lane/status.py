"""The status surface: what the founder sees, and what one customer sees.

READ-ONLY. Nothing here writes, arms, or sends. It asks ``is_connected()`` and
formats the answer; it never recomputes connectedness from raw fields.

THE MID-DAY JOIN RULE IS A MONEY DECISION AND IS STATED, NOT ASSUMED. A customer
who connects after the market is open does NOT get dropped into a position that is
already running. They start at the next fresh entry signal. Joining an open position
late would fill them at a price the signal never saw, and their stop distance would
be wrong. This is the conservative choice and it needs the founder's explicit
sign-off before any customer money depends on it.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.customer_lane import CustomerNotificationLog, LadderStep
from app.domains.customer_lane import config as lane_config
from app.domains.customer_lane.connection import ConnectionStatus, is_connected

IST = timezone(timedelta(hours=5, minutes=30))


class JoinEligibility(str, enum.Enum):
    FULL_DAY = "FULL_DAY"
    NEXT_SIGNAL_ONLY = "NEXT_SIGNAL_ONLY"
    NOT_TODAY = "NOT_TODAY"


MID_DAY_JOIN_RULE = (
    "If you connect after the market opens, you are not placed into a trade that is "
    "already running. You start from the next fresh entry signal. This protects you "
    "from entering at a price the signal never saw."
)

CUSTOMER_COPY: dict[JoinEligibility, str] = {
    JoinEligibility.FULL_DAY:
        "You are connected. Your account will follow today's signals from the open.",
    JoinEligibility.NEXT_SIGNAL_ONLY:
        "You are connected. " + MID_DAY_JOIN_RULE,
    JoinEligibility.NOT_TODAY:
        "You are NOT connected. No trades will be placed for you today. "
        "Tap your connect link to fix this.",
}


@dataclass(frozen=True)
class CustomerStatusLine:
    customer_id: uuid.UUID
    connected: bool
    reason: str
    eligibility: JoinEligibility
    message: str
    token_expires_at: datetime | None
    reminders_sent: list[str]


def _cutoff_utc(trading_date: date) -> datetime:
    cfg = lane_config.load()
    return datetime.combine(trading_date, cfg.link_cutoff_at,
                            tzinfo=IST).astimezone(timezone.utc)


def join_eligibility(status: ConnectionStatus, trading_date: date) -> JoinEligibility:
    """The rule, in one place. See MID_DAY_JOIN_RULE."""
    if not status.connected:
        return JoinEligibility.NOT_TODAY
    connected_at = status.connected_at
    if connected_at is None:
        return JoinEligibility.NEXT_SIGNAL_ONLY  # unknown join time -> the safe side
    if connected_at.tzinfo is None:
        connected_at = connected_at.replace(tzinfo=timezone.utc)
    return (JoinEligibility.FULL_DAY
            if connected_at <= _cutoff_utc(trading_date)
            else JoinEligibility.NEXT_SIGNAL_ONLY)


async def _reminders(session: AsyncSession, customer_ids: list[uuid.UUID],
                     trading_date: date) -> dict[uuid.UUID, list[str]]:
    rows = (await session.execute(
        select(CustomerNotificationLog.customer_id, CustomerNotificationLog.step,
               CustomerNotificationLog.sent_at)
        .where(CustomerNotificationLog.customer_id.in_(customer_ids),
               CustomerNotificationLog.trading_date == trading_date)
        .order_by(CustomerNotificationLog.sent_at))).all()
    out: dict[uuid.UUID, list[str]] = {c: [] for c in customer_ids}
    for cid, step, _ in rows:
        out[cid].append(step.value if isinstance(step, LadderStep) else str(step))
    return out


async def customer_line(session: AsyncSession, customer_id: uuid.UUID, *,
                        trading_date: date,
                        now: datetime | None = None) -> CustomerStatusLine:
    status = await is_connected(session, customer_id, at=now)
    elig = join_eligibility(status, trading_date)
    sent = (await _reminders(session, [customer_id], trading_date))[customer_id]
    return CustomerStatusLine(customer_id, status.connected, status.reason, elig,
                              CUSTOMER_COPY[elig], status.expires_at, sent)


async def founder_board(session: AsyncSession, customer_ids: list[uuid.UUID], *,
                        trading_date: date,
                        now: datetime | None = None) -> list[CustomerStatusLine]:
    """One row per customer. Disconnected customers sort FIRST — the board exists to
    show what is broken, not to be a pleasant green wall."""
    lines = [await customer_line(session, cid, trading_date=trading_date, now=now)
             for cid in customer_ids]
    order = {JoinEligibility.NOT_TODAY: 0, JoinEligibility.NEXT_SIGNAL_ONLY: 1,
             JoinEligibility.FULL_DAY: 2}
    return sorted(lines, key=lambda l: (order[l.eligibility], str(l.customer_id)))


def board_summary(lines: list[CustomerStatusLine]) -> dict[str, int]:
    out = {e.value: 0 for e in JoinEligibility}
    for l in lines:
        out[l.eligibility.value] += 1
    out["total"] = len(lines)
    return out


__all__ = ["JoinEligibility", "MID_DAY_JOIN_RULE", "CUSTOMER_COPY", "CustomerStatusLine",
           "join_eligibility", "customer_line", "founder_board", "board_summary"]
