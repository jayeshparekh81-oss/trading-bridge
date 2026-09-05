"""Notification channels for the reminder ladder.

DELEGATION, NOT A SECOND TRANSPORT. ``app/services/notification_service.py`` is the
estate's notification service: AWS SES email, Telegram, per-user preferences,
urgency handling and a Jinja template tree. The ladder reuses it. An earlier draft
of this module said a real provider "must be a NEW class", implying nothing existed
to reuse; the G3 absence-claim audit proved that wrong. See
``docs/CUSTOMER_LANE_LESSONS.md``.

WHAT EXISTS, AND WHAT DOES NOT (H1 audit, verified whole-machine):

    email     REAL - NotificationService.send_email, AWS SES via boto3
    telegram  REAL - NotificationService.send_telegram
    SMS       DOES NOT EXIST anywhere in the estate
    voice     DOES NOT EXIST anywhere in the estate
    push      in-app websocket/toast only; cannot reach an absent customer

THE CALL RUNG IS UNWIRED BY DECISION, NOT BY ACCIDENT (founder, run J). No voice
transport exists in the estate and none is being built now: a vendor plus Indian
DLT registration is its own project, not worth blocking on while there is no
partner credential, no egress IP and no customer. The ladder therefore runs THREE
rungs — R1, R2, RED.

CALL is wired to :class:`UnavailableChannel`, which REFUSES. It must never quietly
degrade to a message: the customer would be told a call is coming and no call would
come. Its refusal is still RECORDED as ``outcome="UNAVAILABLE"`` so the gap stays
visible in the notification log rather than disappearing because it is "expected".

Preflight accepts CALL as unwired via ``CUSTOMER_LANE_UNWIRED_RUNGS`` (default
``CALL``). Any OTHER rung losing its transport is NOT covered and still refuses to
arm — nobody decided about that one.

TO ADD VOICE LATER: write a NEW class implementing :class:`Channel` (a
``VoiceProviderChannel``), register it in ``CHANNELS["voice"]``, and drop CALL from
``CUSTOMER_LANE_UNWIRED_RUNGS``. That is the whole seam. Do not refactor
:class:`UnavailableChannel` into a real sender — leaving it intact keeps the
refusal available for the next rung that loses a transport.

TWO INDEPENDENT GATES stand between this module and a person:
  * ``ladder_enabled``  - whether the ladder runs at all
  * ``channels_live``   - whether a channel may actually deliver
Both default FALSE. With ``channels_live`` false every channel logs and returns
``"STUBBED"`` without importing or calling NotificationService.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.customer_lane import CustomerNotificationLog, LadderStep
from app.domains.customer_lane import config as lane_config

logger = logging.getLogger("customer_lane.channels")

#: Ladder step -> notification_service event type.
#: R1/R2 reuse the EXISTING broker_session_expired event (it is in _URGENT_EVENTS, so
#: it ignores per-user opt-outs, which is right for "you are about to miss the day").
#: RED needs its own wording and has its own template pair.
STEP_EVENT: dict[LadderStep, str] = {
    LadderStep.R1: "broker_session_expired",
    LadderStep.R2: "broker_session_expired",
    LadderStep.CALL: "broker_session_expired",
    LadderStep.RED: "customer_lane_no_trades_today",
    LadderStep.CONFIRM: "customer_lane_connected",
}


class ChannelUnavailable(RuntimeError):
    """The rung's intended transport does not exist. Never degrade to another."""


@dataclass(frozen=True)
class NotificationResult:
    sent: bool
    channel: str
    step: LadderStep
    outcome: str
    detail: str | None = None


class Channel(Protocol):
    name: str

    async def deliver(self, session: AsyncSession, customer_id: uuid.UUID,
                      step: LadderStep, payload: str) -> str: ...

    def available(self) -> bool: ...


class NotificationServiceChannel:
    """Delegates to the estate's notification service. Sends nothing while disarmed."""

    name = "message"

    def available(self) -> bool:
        return True

    async def deliver(self, session: AsyncSession, customer_id: uuid.UUID,
                      step: LadderStep, payload: str) -> str:
        cfg = lane_config.load()
        if not cfg.channels_live:
            logger.info("customer_lane.stub_send channel=%s step=%s customer=%s",
                        self.name, step.value, customer_id)
            return "STUBBED"

        # Imported HERE, not at module scope: while disarmed this module must not even
        # pull in a transport.
        from app.services.notification_service import notification_service

        event = STEP_EVENT[step]
        ctx: dict[str, Any] = {"message": payload, "broker_name": "Dhan"}
        result = await notification_service.send(customer_id, event, ctx, session)
        delivered = [k for k, v in result.items() if v == "sent"]
        if not delivered:
            logger.warning("customer_lane.no_channel_delivered step=%s customer=%s "
                           "result=%s", step.value, customer_id, result)
            return "FAILED:" + ",".join(f"{k}={v}" for k, v in sorted(result.items()))
        return "SENT:" + ",".join(sorted(delivered))


class UnavailableChannel:
    """A rung whose transport does not exist. Refuses; never falls back."""

    def __init__(self, name: str, why: str) -> None:
        self.name = name
        self.why = why

    def available(self) -> bool:
        return False

    async def deliver(self, session: AsyncSession, customer_id: uuid.UUID,
                      step: LadderStep, payload: str) -> str:
        raise ChannelUnavailable(
            f"customer-lane rung {step.value} needs the {self.name!r} channel and "
            f"{self.why}. Refusing rather than delivering it another way — the "
            "customer would be told a call is coming and no call would come.")


MESSAGE_CHANNEL = NotificationServiceChannel()

VOICE_CHANNEL = UnavailableChannel(
    "voice",
    "no voice/telephony transport exists anywhere in this estate (H1 audit: no "
    "twilio/exotel/knowlarity/plivo/ozonetel, no TTS, and users.phone is stored but "
    "read by no sender)")

PUSH_CHANNEL = UnavailableChannel(
    "push",
    "the only in-app machinery is a chart websocket and toast components, which "
    "cannot reach a customer who is not looking at the app")

CHANNELS: dict[str, Channel] = {
    "message": MESSAGE_CHANNEL,
    "voice": VOICE_CHANNEL,
    "push": PUSH_CHANNEL,
}

STEP_CHANNEL: dict[LadderStep, str] = {
    LadderStep.R1: "message",
    LadderStep.R2: "message",
    LadderStep.CALL: "voice",
    LadderStep.RED: "message",
    LadderStep.CONFIRM: "message",
}


def unavailable_steps() -> dict[LadderStep, str]:
    """Rungs whose intended transport does not exist. Used by preflight."""
    return {step: STEP_CHANNEL[step] for step in STEP_CHANNEL
            if not CHANNELS[STEP_CHANNEL[step]].available()}


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

    channel = CHANNELS[channel_name]
    try:
        outcome = await channel.deliver(session, customer_id, step, payload)
    except ChannelUnavailable as exc:
        # Record the refusal so the founder board shows a rung that could not run,
        # rather than a silent gap. Nothing was delivered.
        logger.error("customer_lane.channel_unavailable step=%s customer=%s: %s",
                     step.value, customer_id, exc)
        session.add(CustomerNotificationLog(
            customer_id=customer_id, channel=channel_name, step=step,
            trading_date=trading_date, outcome="UNAVAILABLE",
            detail=str(exc)[:1024],
            sent_at=sent_at or datetime.now(timezone.utc)))
        await session.flush()
        return NotificationResult(False, channel_name, step, "UNAVAILABLE", str(exc))

    session.add(CustomerNotificationLog(
        customer_id=customer_id, channel=channel_name, step=step,
        trading_date=trading_date, outcome=outcome, detail=payload[:1024],
        sent_at=sent_at or datetime.now(timezone.utc)))
    await session.flush()
    return NotificationResult(True, channel_name, step, outcome)


__all__ = ["send", "NotificationResult", "Channel", "CHANNELS", "STEP_CHANNEL",
           "STEP_EVENT", "NotificationServiceChannel", "UnavailableChannel",
           "ChannelUnavailable", "unavailable_steps",
           "MESSAGE_CHANNEL", "VOICE_CHANNEL", "PUSH_CHANNEL"]
