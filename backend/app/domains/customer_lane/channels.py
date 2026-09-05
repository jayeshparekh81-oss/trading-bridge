"""Notification channels. ALL log-only stubs in this run — nothing leaves the box.

DO NOT WRITE A NEW TRANSPORT WHEN THESE ARE ARMED. An earlier draft of this
docstring said a real provider "must be a NEW class", which implied there was
nothing to reuse. That was wrong, and the G3 absence-claim audit caught it:
``app/services/notification_service.py`` is a working unified service with real
email + Telegram transports, per-user preferences, urgency handling and a
template tree under ``app/templates/notifications/``. It already registers the
event type ``broker_session_expired`` ("Please re-login to continue trading"),
which is very nearly this ladder's use case.

So the real implementation is a thin ``Channel`` that DELEGATES:

    NotificationService().send(user_id, "broker_session_expired", ctx, db)

not a second HTTP client. Reuse the transport, the templates and the preference
logic; keep only the ladder's own idempotency and cancel rule here. Arming it is
a separate, founder-gated step — this run sends nothing.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.customer_lane import CustomerNotificationLog, LadderStep

logger = logging.getLogger("customer_lane.channels")


@dataclass(frozen=True)
class NotificationResult:
    sent: bool
    channel: str
    step: LadderStep
    outcome: str
    detail: str | None = None


class Channel(Protocol):
    name: str

    async def deliver(self, customer_id: uuid.UUID, step: LadderStep, payload: str) -> str: ...


class _LogOnlyChannel:
    """Writes a structured log line and sends NOTHING outward."""

    name = "base"

    async def deliver(self, customer_id: uuid.UUID, step: LadderStep, payload: str) -> str:
        logger.info("customer_lane.stub_send channel=%s step=%s customer=%s payload=%r",
                    self.name, step.value, customer_id, payload)
        return "STUBBED"


class MessageChannel(_LogOnlyChannel):
    name = "message"


class VoiceChannel(_LogOnlyChannel):
    name = "voice"


class PushChannel(_LogOnlyChannel):
    name = "push"


CHANNELS: dict[str, Channel] = {
    "message": MessageChannel(),
    "voice": VoiceChannel(),
    "push": PushChannel(),
}

STEP_CHANNEL: dict[LadderStep, str] = {
    LadderStep.R1: "message",
    LadderStep.R2: "message",
    LadderStep.CALL: "voice",
    LadderStep.RED: "message",
    LadderStep.CONFIRM: "message",
}


async def send(session: AsyncSession, customer_id: uuid.UUID, step: LadderStep,
               payload: str, *, trading_date: date,
               sent_at: datetime | None = None) -> NotificationResult:
    """Idempotent send. The UNIQUE(customer_id, step, trading_date) is the structural
    guarantee; this pre-check makes the no-op explicit and cheap."""
    channel_name = STEP_CHANNEL[step]
    existing = (await session.execute(
        select(CustomerNotificationLog.id).where(
            CustomerNotificationLog.customer_id == customer_id,
            CustomerNotificationLog.step == step,
            CustomerNotificationLog.trading_date == trading_date,
        )
    )).first()
    if existing is not None:
        return NotificationResult(False, channel_name, step, "ALREADY_SENT",
                                  "idempotent no-op")

    outcome = await CHANNELS[channel_name].deliver(customer_id, step, payload)
    session.add(CustomerNotificationLog(
        customer_id=customer_id, channel=channel_name, step=step,
        trading_date=trading_date, outcome=outcome, detail=payload[:1024],
        sent_at=sent_at or datetime.now(timezone.utc)))
    await session.flush()
    return NotificationResult(True, channel_name, step, outcome)


__all__ = ["send", "NotificationResult", "Channel", "CHANNELS", "STEP_CHANNEL",
           "MessageChannel", "VoiceChannel", "PushChannel"]
