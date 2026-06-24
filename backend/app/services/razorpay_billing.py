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
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.db.models.razorpay_payment import RazorpayPayment
from app.db.models.razorpay_webhook_event import RazorpayWebhookEvent
from app.db.models.subscription_plan import SubscriptionPlan
from app.db.models.user import User
from app.services.razorpay_client import get_razorpay_client

logger = get_logger("app.services.razorpay_billing")

#: ``razorpay_payments.kind`` discriminator values — which entity a payment
#: funds, so the ONE webhook routes each ``sub_…`` correctly.
KIND_PLATFORM_PLAN = "platform_plan"
KIND_MARKETPLACE = "marketplace"


class RazorpayBillingError(RuntimeError):
    """Billing operation failed (config, plan lookup, or Razorpay API)."""


#: Razorpay subscription event -> entitlement ``plan_status`` transition.
#: Events not listed leave the plan unchanged.
_EVENT_STATUS: dict[str, str] = {
    "subscription.activated": "active",
    "subscription.charged": "active",      # also the dunning RECOVERY path
    "subscription.pending": "past_due",    # a renewal charge failed; retrying
    "subscription.halted": "expired",      # retries exhausted -> access stops
    "subscription.cancelled": "cancelled",
    "subscription.completed": "expired",   # all cycles done -> ended
}

#: Razorpay subscription ``status`` -> the local status it SHOULD map to, for
#: reconciliation (gateway truth vs our DB). ``None`` = we hold no opinion
#: (``created`` / ``authenticated`` — mandate set but not yet charged).
_RZP_STATUS_TO_LOCAL: dict[str, str | None] = {
    "created": None,
    "authenticated": None,
    "active": "active",
    "charged": "active",
    "pending": "past_due",
    "paused": "past_due",
    "halted": "expired",
    "completed": "expired",
    "expired": "expired",
    "cancelled": "cancelled",
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
    rzp_plan_id: str = created["id"]
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
# Marketplace per-listing subscriptions (M2) — same Razorpay plumbing
# ═══════════════════════════════════════════════════════════════════════


async def sync_listing_plan_to_razorpay(
    db: AsyncSession, listing: MarketplaceListing
) -> str:
    """Return the Razorpay Plan id for ``listing``'s price, creating it once.

    Idempotent: a listing keeps ONE Razorpay plan (``listing.razorpay_plan_id``)
    so repeat / concurrent subscribes never spawn duplicate plans. Free listings
    have no plan — the caller routes those to the no-gateway active path instead.
    """
    if listing.razorpay_plan_id:
        return listing.razorpay_plan_id

    amount_paise = int((listing.price_inr or Decimal("0")) * 100)
    client = get_razorpay_client()
    created = client.plan.create(
        {
            "period": "monthly",
            "interval": 1,
            "item": {
                "name": f"Marketplace: {listing.title}"[:255],
                "amount": amount_paise,
                "currency": "INR",
            },
            "notes": {"listing_id": str(listing.id), "kind": KIND_MARKETPLACE},
        }
    )
    rzp_plan_id: str = created["id"]
    listing.razorpay_plan_id = rzp_plan_id
    await db.commit()
    logger.info(
        "razorpay.marketplace.plan.synced",
        listing_id=str(listing.id), razorpay_plan_id=rzp_plan_id,
    )
    return rzp_plan_id


async def create_subscription_for_listing(
    db: AsyncSession,
    *,
    user: User,
    listing: MarketplaceListing,
    total_count: int = 12,
) -> dict[str, Any]:
    """Create a Razorpay Subscription for ``user`` on ``listing`` and persist it.

    Writes a PENDING ``marketplace_subscription`` (NOT active — no access until
    the first charge lands) PLUS a ``razorpay_payments`` row (``kind=marketplace``)
    that the verified webhook later flips to ``active``. ``subscriber_count`` is
    NOT bumped here — only on activation. Returns the checkout handle. The key
    SECRET is never returned.
    """
    rzp_plan_id = await sync_listing_plan_to_razorpay(db, listing)
    client = get_razorpay_client()
    sub = client.subscription.create(
        {
            "plan_id": rzp_plan_id,
            "total_count": total_count,
            "customer_notify": 1,
            "notes": {
                "user_id": str(user.id),
                "listing_id": str(listing.id),
                "kind": KIND_MARKETPLACE,
            },
        }
    )
    sub_id = sub["id"]
    short_url = sub.get("short_url")

    msub = MarketplaceSubscription(
        listing_id=listing.id,
        subscriber_id=user.id,
        subscribed_at=datetime.now(UTC),
        status="pending",                 # NOT active until the webhook confirms
        amount_paid_inr=Decimal("0"),     # nothing captured yet
        razorpay_subscription_id=sub_id,
    )
    db.add(msub)
    await db.flush()  # materialise msub.id for the payment FK

    row = RazorpayPayment(
        user_id=user.id,
        kind=KIND_MARKETPLACE,
        marketplace_subscription_id=msub.id,
        razorpay_subscription_id=sub_id,
        status=sub.get("status") or "created",
        amount_inr=listing.price_inr,
        notes={"short_url": short_url, "listing_id": str(listing.id)},
    )
    db.add(row)
    await db.commit()
    await db.refresh(msub)

    logger.info(
        "razorpay.marketplace.subscription.created",
        user_id=str(user.id), listing_id=str(listing.id),
        razorpay_subscription_id=sub_id, marketplace_subscription_id=str(msub.id),
    )
    return {
        "marketplace_subscription": msub,
        "razorpay_subscription_id": sub_id,
        "razorpay_key_id": get_settings().razorpay_key_id.get_secret_value(),
        "razorpay_plan_id": rzp_plan_id,
        "status": row.status,
        "short_url": short_url,
        "amount_inr": float(listing.price_inr or 0),
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
    actor: ActorType = ActorType.SYSTEM,
) -> None:
    """Write the EXISTING B2 entitlement triple (mirrors admin.set_user_plan).

    Reuses ``users.plan_status`` / ``active_plan_id`` / ``plan_expires_at`` —
    the same fields :func:`app.auth.entitlements.plan_is_active` reads. Never
    touches role / live_trading / paywall_enforced. ``past_due`` (dunning) is a
    non-active status, so ``plan_is_active`` already denies access for it.
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
    # For cancelled/expired/past_due we keep active_plan_id for history but flip
    # status; plan_is_active() already returns False for any non-"active" status.

    db.add(
        AuditLog(
            user_id=user.id,
            actor=actor,
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


async def _apply_marketplace_subscription(
    db: AsyncSession,
    payment_row: RazorpayPayment,
    *,
    new_status: str,
    access_until: datetime | None,
    event_type: str,
    actor: ActorType = ActorType.SYSTEM,
) -> bool:
    """Flip the linked ``marketplace_subscription`` status (M2 webhook path).

    Mirrors :func:`_apply_entitlement` but for the marketplace side: it ONLY
    touches the subscription's status / access window / paid-amount and the
    listing's ``subscriber_count`` denormaliser. It NEVER touches trading state,
    fan-out, or ``paywall_enforced`` — a paid subscription is access-only.
    Returns True if a subscription row was updated.
    """
    msub_id = payment_row.marketplace_subscription_id
    sub: MarketplaceSubscription | None = None
    if msub_id is not None:
        sub = await db.get(MarketplaceSubscription, msub_id)
    if sub is None and payment_row.razorpay_subscription_id:
        sub = await db.scalar(
            select(MarketplaceSubscription).where(
                MarketplaceSubscription.razorpay_subscription_id
                == payment_row.razorpay_subscription_id
            )
        )
    if sub is None:
        logger.warning(
            "razorpay.webhook.no_marketplace_sub",
            event_type=event_type, sub_id=payment_row.razorpay_subscription_id,
        )
        return False

    listing = await db.get(MarketplaceListing, sub.listing_id)
    before = {"status": sub.status, "access_until": str(sub.access_until)}
    was_active = sub.status == "active"
    now_active = new_status == "active"

    sub.status = new_status
    # subscriber_count tracks ACTIVE seats only. Count the active<->inactive
    # edge exactly once in each direction (covers pending/past_due/expired/
    # cancelled -> active and active -> any of them, incl. dunning).
    if now_active:
        sub.access_until = access_until
        if listing is not None:
            sub.amount_paid_inr = listing.price_inr
            if not was_active:
                listing.subscriber_count = listing.subscriber_count + 1
    elif was_active and listing is not None:
        listing.subscriber_count = max(0, listing.subscriber_count - 1)

    db.add(
        AuditLog(
            user_id=sub.subscriber_id,
            actor=actor,
            action=f"razorpay.marketplace.{event_type}",
            resource_type="marketplace_subscription",
            resource_id=str(sub.id),
            audit_metadata={
                "before": before,
                "after": {"status": sub.status, "access_until": str(sub.access_until)},
                "listing_id": str(sub.listing_id),
            },
        )
    )
    return True


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
            # Route by which entity this payment funds (ONE webhook, two kinds).
            if row.kind == KIND_MARKETPLACE:
                applied = await _apply_marketplace_subscription(
                    db, row,
                    new_status=new_status,
                    access_until=_expires_at(sub_entity),
                    event_type=event_type,
                )
            else:
                user = await db.get(User, row.user_id)
                if user is not None:
                    # Plan-change safety: a SUPERSEDED sub's lifecycle events
                    # (e.g. the old sub's cancel at cycle-end after an
                    # upgrade) must NOT clobber the user's CURRENT plan. Apply
                    # entitlement only when this event is for the user's active
                    # handle — or when no handle is recorded (legacy/admin).
                    superseded = (
                        user.razorpay_subscription_id is not None
                        and user.razorpay_subscription_id != sub_id
                    )
                    if superseded:
                        logger.info(
                            "razorpay.webhook.superseded_sub",
                            event_type=event_type, sub_id=sub_id,
                            current=user.razorpay_subscription_id,
                        )
                    else:
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


# ═══════════════════════════════════════════════════════════════════════
# Lifecycle (M4) — cancel / plan-change / reconcile.  Access REVOCATION is
# driven by the verified webhook (cycle-end) or an explicit user/admin call.
# ═══════════════════════════════════════════════════════════════════════


def _public_key() -> str:
    return get_settings().razorpay_key_id.get_secret_value()


async def _payment_by_sub(db: AsyncSession, sub_id: str) -> RazorpayPayment | None:
    row: RazorpayPayment | None = await db.scalar(
        select(RazorpayPayment).where(RazorpayPayment.razorpay_subscription_id == sub_id)
    )
    return row


def _mark_note(row: RazorpayPayment | None, **kv: Any) -> None:
    """Merge keys into a RazorpayPayment.notes JSON (reassign so SA sees it)."""
    if row is None:
        return
    notes = dict(row.notes or {})
    notes.update(kv)
    row.notes = notes


async def cancel_subscription_for_user(
    db: AsyncSession, *, user: User, at_cycle_end: bool = True
) -> dict[str, Any]:
    """Cancel the caller's PLATFORM-plan recurring subscription.

    Default (``at_cycle_end=True``) is the standard **cancel-at-period-end**:
    Razorpay keeps the subscription live until the current cycle ends, then
    fires ``subscription.cancelled`` -> the webhook flips ``plan_status``.
    Access naturally lapses at ``plan_expires_at`` (``plan_is_active`` already
    enforces the expiry). ``at_cycle_end=False`` cancels immediately and — as an
    explicit authenticated user action — revokes access now (no webhook wait).
    """
    sub_id = user.razorpay_subscription_id
    if not sub_id:
        raise RazorpayBillingError("No active subscription to cancel.")
    client = get_razorpay_client()
    client.subscription.cancel(sub_id, {"cancel_at_cycle_end": 1 if at_cycle_end else 0})

    row = await _payment_by_sub(db, sub_id)
    _mark_note(row, cancel_requested=True, cancel_at_cycle_end=at_cycle_end)

    if not at_cycle_end:
        await _apply_entitlement(
            db, user,
            plan_id=user.active_plan_id,
            plan_status="cancelled",
            plan_expires_at=user.plan_expires_at,
            event_type="user.cancel_immediate",
            actor=ActorType.USER,
        )
    await db.commit()
    logger.info(
        "razorpay.subscription.cancel_requested",
        user_id=str(user.id), sub_id=sub_id, at_cycle_end=at_cycle_end,
    )
    return {
        "razorpay_subscription_id": sub_id,
        "at_cycle_end": at_cycle_end,
        "plan_status": user.plan_status,
        "access_until": (
            user.plan_expires_at.isoformat() if user.plan_expires_at else None
        ),
    }


async def cancel_marketplace_subscription(
    db: AsyncSession, *, sub: MarketplaceSubscription, at_cycle_end: bool = True
) -> dict[str, Any]:
    """Cancel a PAID marketplace subscription at the gateway.

    Cycle-end: request Razorpay cancel-at-cycle-end and KEEP the row active so
    the subscriber retains the access they paid for until period end; the
    webhook flips the status (and releases the seat) at cycle end. Immediate:
    cancel now + release the seat (explicit user action).
    """
    sub_id = sub.razorpay_subscription_id
    if sub_id:
        client = get_razorpay_client()
        client.subscription.cancel(sub_id, {"cancel_at_cycle_end": 1 if at_cycle_end else 0})
        row = await db.scalar(
            select(RazorpayPayment).where(
                RazorpayPayment.marketplace_subscription_id == sub.id
            )
        )
        _mark_note(row, cancel_requested=True, cancel_at_cycle_end=at_cycle_end)

    scheduled = bool(sub_id) and at_cycle_end
    if not scheduled:
        # Free sub OR explicit immediate cancel -> flip now + release the seat.
        was_active = sub.status == "active"
        sub.status = "cancelled"
        if was_active:
            listing = await db.get(MarketplaceListing, sub.listing_id)
            if listing is not None:
                listing.subscriber_count = max(0, listing.subscriber_count - 1)
    await db.commit()
    logger.info(
        "razorpay.marketplace.cancel_requested",
        subscription_id=str(sub.id), sub_id=sub_id, scheduled=scheduled,
    )
    return {
        "scheduled_cancel": scheduled,
        "status": sub.status,
        "access_until": sub.access_until.isoformat() if sub.access_until else None,
    }


async def change_plan_for_user(
    db: AsyncSession, *, user: User, plan: SubscriptionPlan, total_count: int = 12
) -> dict[str, Any]:
    """Change the caller's PLATFORM plan (upgrade/downgrade), **next-cycle model**.

    No mid-cycle proration and NO double charge: a NEW subscription is created
    to start when the current period ends (``start_at = plan_expires_at``), and
    the OLD subscription is cancelled at cycle-end (its paid period is honoured).
    The user's active handle flips to the new sub immediately, so the OLD sub's
    lifecycle events are treated as superseded (see the webhook guard) and never
    clobber the new plan. The new plan's entitlement lands when its first charge
    webhook arrives. With no current sub, this is just a fresh subscribe.
    """
    current_sub_id = user.razorpay_subscription_id
    if not current_sub_id:
        return await create_subscription_for_user(
            db, user=user, plan=plan, total_count=total_count
        )

    rzp_plan_id = await sync_plan_to_razorpay(db, plan)
    client = get_razorpay_client()
    payload: dict[str, Any] = {
        "plan_id": rzp_plan_id,
        "total_count": total_count,
        "customer_notify": 1,
        "notes": {
            "user_id": str(user.id),
            "tier": plan.tier,
            "plan_change_from": current_sub_id,
        },
    }
    if user.plan_expires_at is not None:
        # Start the new sub at the old period's end -> no overlap, no double charge.
        payload["start_at"] = int(user.plan_expires_at.timestamp())
    new_sub = client.subscription.create(payload)
    new_sub_id = new_sub["id"]

    # Cancel the OLD sub at cycle-end (remaining paid period honoured).
    client.subscription.cancel(current_sub_id, {"cancel_at_cycle_end": 1})

    db.add(
        RazorpayPayment(
            user_id=user.id,
            plan_id=plan.id,
            kind=KIND_PLATFORM_PLAN,
            razorpay_subscription_id=new_sub_id,
            status=new_sub.get("status") or "created",
            amount_inr=plan.price_monthly_inr,
            notes={
                "tier": plan.tier,
                "plan_change_from": current_sub_id,
                "short_url": new_sub.get("short_url"),
            },
        )
    )
    old_row = await _payment_by_sub(db, current_sub_id)
    _mark_note(old_row, superseded_by=new_sub_id)
    # Flip the active handle so old-sub events become superseded immediately.
    user.razorpay_subscription_id = new_sub_id
    await db.commit()

    logger.info(
        "razorpay.plan.changed",
        user_id=str(user.id), tier=plan.tier,
        new_sub=new_sub_id, old_sub=current_sub_id,
    )
    return {
        "razorpay_subscription_id": new_sub_id,
        "razorpay_key_id": _public_key(),
        "status": new_sub.get("status") or "created",
        "short_url": new_sub.get("short_url"),
        "plan_tier": plan.tier,
        "amount_inr": float(plan.price_monthly_inr or 0),
        "previous_subscription_id": current_sub_id,
        "scheduled_at_period_end": True,
    }


async def reconcile_subscription(
    db: AsyncSession, *, razorpay_subscription_id: str
) -> dict[str, Any]:
    """READ-ONLY drift check: gateway truth vs our stored status.

    Fetches the live Razorpay subscription status and compares it to the local
    status (``users.plan_status`` for a platform plan, ``marketplace_subscriptions
    .status`` for a marketplace sub). NEVER mutates — log/report only; the
    explicit fix is :func:`apply_reconciliation`.
    """
    row = await _payment_by_sub(db, razorpay_subscription_id)
    if row is None:
        return {
            "razorpay_subscription_id": razorpay_subscription_id,
            "found": False, "drift": False,
        }
    client = get_razorpay_client()
    entity = client.subscription.fetch(razorpay_subscription_id)
    gateway_status = entity.get("status")
    expected = _RZP_STATUS_TO_LOCAL.get(gateway_status)

    if row.kind == KIND_MARKETPLACE:
        sub = (
            await db.get(MarketplaceSubscription, row.marketplace_subscription_id)
            if row.marketplace_subscription_id else None
        )
        local_status = sub.status if sub is not None else None
    else:
        user = await db.get(User, row.user_id)
        local_status = user.plan_status if user is not None else None

    drift = (
        expected is not None
        and local_status is not None
        and expected != local_status
    )
    return {
        "razorpay_subscription_id": razorpay_subscription_id,
        "found": True,
        "kind": row.kind,
        "gateway_status": gateway_status,
        "local_status": local_status,
        "expected_local_status": expected,
        "drift": drift,
    }


async def apply_reconciliation(
    db: AsyncSession, *, razorpay_subscription_id: str, admin_user_id: uuid.UUID
) -> dict[str, Any]:
    """EXPLICIT admin fix: apply the gateway's truth onto our DB.

    Only runs on an authenticated admin call (never automatically). Reuses the
    same appliers the webhook uses, attributed to ``ActorType.ADMIN``. Returns
    the before/after so the admin sees exactly what changed.
    """
    row = await _payment_by_sub(db, razorpay_subscription_id)
    if row is None:
        return {"applied": False, "reason": "no_local_payment_row"}
    client = get_razorpay_client()
    entity = client.subscription.fetch(razorpay_subscription_id)
    gateway_status = entity.get("status")
    expected = _RZP_STATUS_TO_LOCAL.get(gateway_status)
    if expected is None:
        return {
            "applied": False, "reason": "gateway_status_unmapped",
            "gateway_status": gateway_status,
        }

    row.status = gateway_status or row.status
    if row.kind == KIND_MARKETPLACE:
        applied = await _apply_marketplace_subscription(
            db, row, new_status=expected, access_until=_expires_at(entity),
            event_type="admin.reconcile", actor=ActorType.ADMIN,
        )
    else:
        user = await db.get(User, row.user_id)
        applied = False
        if user is not None:
            await _apply_entitlement(
                db, user, plan_id=row.plan_id, plan_status=expected,
                plan_expires_at=_expires_at(entity),
                event_type="admin.reconcile", actor=ActorType.ADMIN,
            )
            applied = True

    db.add(
        AuditLog(
            user_id=admin_user_id,
            actor=ActorType.ADMIN,
            action="razorpay.admin.reconcile_apply",
            resource_type="razorpay_subscription",
            resource_id=razorpay_subscription_id,
            audit_metadata={
                "gateway_status": gateway_status,
                "applied_local_status": expected,
                "kind": row.kind,
            },
        )
    )
    await db.commit()
    logger.info(
        "razorpay.admin.reconcile_apply",
        sub_id=razorpay_subscription_id, gateway_status=gateway_status,
        applied_local_status=expected, applied=applied,
    )
    return {
        "applied": applied,
        "gateway_status": gateway_status,
        "local_status": expected,
        "kind": row.kind,
    }


__all__ = [
    "KIND_MARKETPLACE",
    "KIND_PLATFORM_PLAN",
    "RazorpayBillingError",
    "apply_reconciliation",
    "cancel_marketplace_subscription",
    "cancel_subscription_for_user",
    "change_plan_for_user",
    "create_subscription_for_listing",
    "create_subscription_for_user",
    "handle_webhook_event",
    "reconcile_subscription",
    "sync_listing_plan_to_razorpay",
    "sync_plan_to_razorpay",
]
