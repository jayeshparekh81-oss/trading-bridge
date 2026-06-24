"""Razorpay recurring billing — Phase 2, Module 1.

Maps platform ``subscription_plans`` tiers to Razorpay Plans (create-if-absent),
creates Razorpay Subscriptions (recurring/mandate) for a user+plan, and applies
(signature-verified, idempotent) webhook events onto the EXISTING entitlement
fields on ``users`` (``plan_status`` / ``active_plan_id`` / ``plan_expires_at``
— migration 032, read by :func:`app.auth.entitlements.plan_is_active`).

This module NEVER flips ``paywall_enforced`` and NEVER touches trading state.
All Razorpay API calls go through :mod:`app.services.razorpay_client` (mocked in
tests).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.audit_log import ActorType, AuditLog
from app.db.models.razorpay_payment import RazorpayPayment
from app.db.models.razorpay_webhook_event import RazorpayWebhookEvent
from app.db.models.subscription_plan import SubscriptionPlan
from app.db.models.user import User
from app.services.razorpay_client import get_razorpay_client

logger = get_logger("app.services.razorpay_billing")


class RazorpayBillingError(RuntimeError):
    """Billing operation failed (config, plan lookup, or Razorpay API)."""


#: Razorpay subscription event -> entitlement ``plan_status`` transition.
#: Events not listed (e.g. ``subscription.pending``) leave the plan unchanged.
_EVENT_STATUS: dict[str, str] = {
    "subscription.activated": "active",
    "subscription.charged": "active",
    "subscription.halted": "expired",     # retries exhausted -> access stops
    "subscription.cancelled": "cancelled",
    "subscription.completed": "expired",  # all cycles done -> ended
}


# ═══════════════════════════════════════════════════════════════════════
# Plans (create-if-absent, no duplicates)
# ═══════════════════════════════════════════════════════════════════════


async def sync_plan_to_razorpay(db: AsyncSession, plan: SubscriptionPlan) -> str:
    """Return the Razorpay Plan id for ``plan``, creating it once if absent.

    Idempotent: if ``plan.razorpay_plan_id`` is already set, returns it without
    calling Razorpay (so a tier never spawns duplicate Razorpay plans).
    """
    if plan.razorpay_plan_id:
        return plan.razorpay_plan_id

    amount_paise = int((plan.price_monthly_inr or Decimal("0")) * 100)
    client = get_razorpay_client()
    created = client.plan.create(
        {
            "period": "monthly",
            "interval": 1,
            "item": {
                "name": plan.name,
                "amount": amount_paise,
                "currency": "INR",
            },
            "notes": {"tier": plan.tier},
        }
    )
    rzp_plan_id = created["id"]
    plan.razorpay_plan_id = rzp_plan_id
    await db.commit()
    logger.info("razorpay.plan.synced", tier=plan.tier, razorpay_plan_id=rzp_plan_id)
    return rzp_plan_id


# ═══════════════════════════════════════════════════════════════════════
# Subscribe (create a recurring subscription for a user+plan)
# ═══════════════════════════════════════════════════════════════════════


async def create_subscription_for_user(
    db: AsyncSession,
    *,
    user: User,
    plan: SubscriptionPlan,
    total_count: int = 12,
) -> dict[str, Any]:
    """Create a Razorpay Subscription for ``user`` on ``plan`` and persist it.

    Returns the handle the frontend checkout needs:
    ``{razorpay_subscription_id, razorpay_key_id (public), status, short_url,
    plan_tier, amount_inr}``. The key SECRET is never returned.
    """
    rzp_plan_id = await sync_plan_to_razorpay(db, plan)
    client = get_razorpay_client()
    sub = client.subscription.create(
        {
            "plan_id": rzp_plan_id,
            "total_count": total_count,
            "customer_notify": 1,
            "notes": {"user_id": str(user.id), "tier": plan.tier},
        }
    )
    sub_id = sub["id"]
    short_url = sub.get("short_url")

    row = RazorpayPayment(
        user_id=user.id,
        plan_id=plan.id,
        razorpay_subscription_id=sub_id,
        status=sub.get("status") or "created",
        amount_inr=plan.price_monthly_inr,
        notes={"short_url": short_url, "tier": plan.tier},
    )
    db.add(row)
    # The user's active recurring handle (for manage/cancel). NOT the paywall.
    user.razorpay_subscription_id = sub_id
    await db.commit()

    logger.info(
        "razorpay.subscription.created",
        user_id=str(user.id), tier=plan.tier, razorpay_subscription_id=sub_id,
    )
    return {
        "razorpay_subscription_id": sub_id,
        "razorpay_key_id": get_settings().razorpay_key_id.get_secret_value(),
        "status": row.status,
        "short_url": short_url,
        "plan_tier": plan.tier,
        "amount_inr": float(plan.price_monthly_inr or 0),
    }


# ═══════════════════════════════════════════════════════════════════════
# Webhook (verified upstream; idempotent here; drives entitlement)
# ═══════════════════════════════════════════════════════════════════════


def _sub_entity(payload: dict[str, Any]) -> dict[str, Any]:
    return (payload.get("subscription") or {}).get("entity") or {}


def _payment_entity(payload: dict[str, Any]) -> dict[str, Any]:
    return (payload.get("payment") or {}).get("entity") or {}


def _expires_at(sub_entity: dict[str, Any]) -> datetime | None:
    """``current_end`` (epoch seconds) -> tz-aware datetime, or None."""
    end = sub_entity.get("current_end")
    if not end:
        return None
    try:
        return datetime.fromtimestamp(int(end), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


async def _apply_entitlement(
    db: AsyncSession,
    user: User,
    *,
    plan_id: uuid.UUID | None,
    plan_status: str,
    plan_expires_at: datetime | None,
    event_type: str,
) -> None:
    """Write the EXISTING B2 entitlement triple (mirrors admin.set_user_plan).

    Reuses ``users.plan_status`` / ``active_plan_id`` / ``plan_expires_at`` —
    the same fields :func:`app.auth.entitlements.plan_is_active` reads. Never
    touches role / live_trading / paywall_enforced.
    """
    before = {
        "plan_status": user.plan_status,
        "active_plan_id": str(user.active_plan_id) if user.active_plan_id else None,
    }
    user.plan_status = plan_status
    if plan_status == "active":
        if plan_id is not None:
            user.active_plan_id = plan_id
        user.plan_expires_at = plan_expires_at
    # For cancelled/expired we keep active_plan_id for history but flip status;
    # plan_is_active() already returns False for any non-"active" status.

    db.add(
        AuditLog(
            user_id=user.id,
            actor=ActorType.SYSTEM,
            action=f"razorpay.{event_type}",
            resource_type="user",
            resource_id=str(user.id),
            audit_metadata={
                "before": before,
                "after": {
                    "plan_status": user.plan_status,
                    "active_plan_id": str(user.active_plan_id)
                    if user.active_plan_id else None,
                },
            },
        )
    )


async def handle_webhook_event(
    db: AsyncSession,
    *,
    event_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Apply a Razorpay subscription event idempotently.

    The caller MUST have already verified the signature. Returns
    ``{"applied": bool, "status": "applied"|"duplicate"|"ignored", ...}``.
    A duplicate ``event_id`` (durable unique ledger) produces a SINGLE effect.
    """
    # Idempotency — durable ledger keyed by the unique event_id.
    existing = await db.scalar(
        select(RazorpayWebhookEvent).where(RazorpayWebhookEvent.event_id == event_id)
    )
    if existing is not None:
        logger.info("razorpay.webhook.duplicate", event_id=event_id, event_type=event_type)
        return {"applied": False, "status": "duplicate", "event_type": event_type}

    sub_entity = _sub_entity(payload)
    pay_entity = _payment_entity(payload)
    sub_id = sub_entity.get("id")
    pay_id = pay_entity.get("id")

    db.add(
        RazorpayWebhookEvent(
            event_id=event_id,
            event_type=event_type,
            razorpay_subscription_id=sub_id,
            razorpay_payment_id=pay_id,
        )
    )

    new_status = _EVENT_STATUS.get(event_type)
    applied = False
    if new_status is not None and sub_id:
        row = await db.scalar(
            select(RazorpayPayment).where(
                RazorpayPayment.razorpay_subscription_id == sub_id
            )
        )
        if row is not None:
            row.status = event_type.split(".")[-1]
            if pay_id:
                row.razorpay_payment_id = pay_id
            user = await db.get(User, row.user_id)
            if user is not None:
                await _apply_entitlement(
                    db, user,
                    plan_id=row.plan_id,
                    plan_status=new_status,
                    plan_expires_at=_expires_at(sub_entity),
                    event_type=event_type,
                )
                applied = True
        else:
            logger.warning(
                "razorpay.webhook.no_payment_row", event_type=event_type, sub_id=sub_id
            )

    try:
        await db.commit()
    except IntegrityError:
        # Race: a concurrent delivery inserted the same event_id first.
        await db.rollback()
        logger.info("razorpay.webhook.duplicate_race", event_id=event_id)
        return {"applied": False, "status": "duplicate", "event_type": event_type}

    logger.info(
        "razorpay.webhook.processed",
        event_id=event_id, event_type=event_type, applied=applied,
        new_status=new_status,
    )
    return {
        "applied": applied,
        "status": "applied" if applied else "ignored",
        "event_type": event_type,
        "plan_status": new_status,
    }


__all__ = [
    "RazorpayBillingError",
    "create_subscription_for_user",
    "handle_webhook_event",
    "sync_plan_to_razorpay",
]
