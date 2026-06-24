"""Razorpay billing endpoints — Phase 2, Module 1.

    POST /api/billing/subscribe          (auth)   — start a recurring subscription
    POST /api/billing/webhook/razorpay   (public) — Razorpay events, signature-verified
    POST /api/billing/admin/sync-plans   (admin)  — map plan tiers -> Razorpay plans

Webhook security: EVERY event's ``X-Razorpay-Signature`` HMAC is verified against
``RAZORPAY_WEBHOOK_SECRET`` before any action; an unverified/spoofed webhook can
NEVER grant a plan. Idempotent. Drives the EXISTING entitlement fields. Does NOT
flip ``paywall_enforced``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_current_admin
from app.auth.entitlements import plan_is_active
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.subscription_plan import SubscriptionPlan
from app.db.models.user import User
from app.db.session import get_session
from app.schemas.billing import SubscribeRequest, SubscribeResponse
from app.services import razorpay_billing
from app.services.razorpay_client import (
    RazorpayConfigError,
    verify_webhook_signature,
)

logger = get_logger("app.api.billing")

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/me")
async def billing_me(
    user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Current user's plan entitlement — read-only, for post-checkout polling.

    Reflects ONLY the existing B2 entitlement fields (driven by the verified
    webhook). The frontend polls this after opening checkout until
    ``is_active`` flips true (or the user gives up). Never flips paywall.
    """
    tier: str | None = None
    if user.active_plan_id is not None:
        plan = await db.get(SubscriptionPlan, user.active_plan_id)
        tier = plan.tier if plan is not None else None
    return {
        "plan_status": user.plan_status,
        "is_active": plan_is_active(user),
        "plan_tier": tier,
        "plan_expires_at": (
            user.plan_expires_at.isoformat() if user.plan_expires_at else None
        ),
    }


@router.post("/subscribe", response_model=SubscribeResponse)
async def subscribe(
    body: SubscribeRequest,
    user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> SubscribeResponse:
    """Create a Razorpay recurring subscription for the caller on a plan."""
    plan = await db.scalar(
        select(SubscriptionPlan).where(
            SubscriptionPlan.id == body.plan_id,
            SubscriptionPlan.is_active.is_(True),
        )
    )
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription plan not found."
        )
    try:
        result = await razorpay_billing.create_subscription_for_user(
            db, user=user, plan=plan
        )
    except RazorpayConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not configured.",
        ) from exc
    return SubscribeResponse(**result)


@router.post("/admin/sync-plans")
async def sync_plans(
    _admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Map every active platform plan tier to a Razorpay Plan (create-if-absent)."""
    plans = list(
        (
            await db.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.is_active.is_(True))
            )
        ).scalars()
    )
    try:
        out = {
            plan.tier: await razorpay_billing.sync_plan_to_razorpay(db, plan)
            for plan in plans
        }
    except RazorpayConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not configured.",
        ) from exc
    return {"synced": out}


def _derive_event_id(headers_event_id: str | None, parsed: dict[str, Any]) -> str:
    """Razorpay's ``X-Razorpay-Event-Id`` when present, else a stable derived key
    ``{event}:{entity_id}:{created_at}`` (payment id preferred, else subscription
    id) so duplicates dedupe even on older Razorpay deliveries."""
    if headers_event_id:
        return headers_event_id
    event = parsed.get("event", "unknown")
    payload = parsed.get("payload") or {}
    entity_id = (
        ((payload.get("payment") or {}).get("entity") or {}).get("id")
        or ((payload.get("subscription") or {}).get("entity") or {}).get("id")
        or ""
    )
    created = parsed.get("created_at", "")
    raw = f"{event}:{entity_id}:{created}"
    # Hash to bound length (event_id column is VARCHAR(128)).
    return hashlib.sha256(raw.encode()).hexdigest()


@router.post("/webhook/razorpay")
async def razorpay_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Razorpay webhook — verify signature FIRST, then idempotently apply.

    Public endpoint (Razorpay calls it). Returns 200 once accepted so Razorpay
    stops retrying; an invalid signature is rejected with 400 and grants nothing.
    """
    raw = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")
    secret = get_settings().razorpay_webhook_secret.get_secret_value()

    # CRITICAL: verify before doing ANYTHING with the body.
    if not verify_webhook_signature(raw, signature, secret):
        logger.warning("razorpay.webhook.bad_signature")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature.",
        )

    try:
        parsed = json.loads(raw or b"{}")
        if not isinstance(parsed, dict):
            raise ValueError("body is not a JSON object")
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed webhook body."
        ) from exc

    event_type = parsed.get("event", "unknown")
    payload = parsed.get("payload") or {}
    event_id = _derive_event_id(request.headers.get("X-Razorpay-Event-Id"), parsed)

    result = await razorpay_billing.handle_webhook_event(
        db, event_id=event_id, event_type=event_type, payload=payload
    )
    return {"received": True, **result}


__all__ = ["router"]
