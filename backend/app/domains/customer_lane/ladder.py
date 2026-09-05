"""The reminder ladder.

THE CANCEL RULE (founder's spec, and the whole point of this module):
the logic NEVER branches on "which step did he connect at". For each customer, at
that customer's turn, it asks exactly ONE question — *is this customer connected
right now?* — and goes silent on yes. That is why ``run_step`` has no notion of
prior rungs and no per-step special cases.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.customer_lane import CustomerBrokerLink, LadderStep
from app.domains.customer_lane import config as lane_config
from app.domains.customer_lane.channels import send
from app.domains.customer_lane.connection import is_connected
from app.domains.customer_lane.calendar import is_trading_day as calendar_is_trading_day

MESSAGES: dict[LadderStep, str] = {
    LadderStep.R1: ("Good morning. Please connect your Dhan account for today's trading. "
                    "Tap the link to log in."),
    LadderStep.R2: ("Reminder: your Dhan account is still not connected. "
                    "Tap the link to log in before the market opens."),
    # NOT a promise of a phone call. The CALL rung is deliberately UNWIRED (run J):
    # there is no voice transport in the estate and none is being built. This string
    # is never delivered — the rung's channel refuses — but it must not say "calling
    # you" even so, or the lie ships the moment someone re-points the rung at a
    # message channel. test_c11 asserts no customer-facing string promises a call.
    LadderStep.CALL: ("Urgent: your Dhan account is still not connected and the market "
                      "opens shortly."),
    LadderStep.RED: ("YOUR ACCOUNT IS NOT CONNECTED. NO TRADES WILL BE PLACED FOR YOU "
                     "TODAY. Nothing will run on your behalf until you connect. "
                     "This is not a warning — it is today's status."),
    LadderStep.CONFIRM: ("Connected — nothing more is needed from you today."),
}


@dataclass(frozen=True)
class StepOutcome:
    customer_id: uuid.UUID
    step: LadderStep
    sent: bool
    reason: str


def is_ladder_trading_day(day: date, cfg=None) -> bool:
    """True iff the exchange trades on ``day``.

    Uses the estate's ONE holiday list via
    :mod:`app.domains.customer_lane.calendar`, which reads the same git-tracked
    ``orderflow_engine/holidays.yaml`` the recorders already run on. It RAISES
    rather than guessing when the list cannot be read or does not reach ``day`` -
    a silent "assume it trades" would phone customers on Diwali.

    (An earlier run of this build asserted no holiday source existed and skipped
    weekends only. That was wrong; this is the correction.)"""
    return calendar_is_trading_day(day)


async def run_step(session: AsyncSession, step: LadderStep, *,
                   trading_date: date, now: datetime | None = None) -> list[StepOutcome]:
    """Execute one rung for every customer with a broker link.

    Rule 1 — the connection check is made PER CUSTOMER, AT THAT CUSTOMER'S TURN.
    No 'unconnected' list is built up front, so a customer who connects between job
    start and their turn is never messaged.
    """
    cfg = lane_config.load()
    now = now or datetime.now(timezone.utc)

    if not cfg.ladder_enabled:
        return []
    if not is_ladder_trading_day(trading_date, cfg):
        return []

    customer_ids = list((await session.execute(
        select(CustomerBrokerLink.customer_id).order_by(CustomerBrokerLink.customer_id)
    )).scalars())

    out: list[StepOutcome] = []
    for cid in customer_ids:
        # THE ONE QUESTION. Asked here, now, for this customer.
        status = await is_connected(session, cid, at=now)
        if status.connected:
            out.append(StepOutcome(cid, step, False, "cancelled_connected"))
            continue
        res = await send(session, cid, step, MESSAGES[step],
                         trading_date=trading_date, sent_at=now)
        out.append(StepOutcome(cid, step, res.sent,
                               "sent" if res.sent else res.outcome.lower()))
    return out


async def confirm_connection(session: AsyncSession, customer_id: uuid.UUID, *,
                             trading_date: date,
                             now: datetime | None = None) -> StepOutcome:
    """Idempotent CONFIRM on transition to CONNECTED."""
    res = await send(session, customer_id, LadderStep.CONFIRM,
                     MESSAGES[LadderStep.CONFIRM], trading_date=trading_date,
                     sent_at=now)
    return StepOutcome(customer_id, LadderStep.CONFIRM, res.sent,
                       "sent" if res.sent else res.outcome.lower())


__all__ = ["run_step", "confirm_connection", "StepOutcome", "MESSAGES",
           "is_ladder_trading_day"]
