"""Billing admin schemas — Phase 2 Billing B3.

Request models for admin-side billing operations. Kept separate from the
public auth schemas so the billing surface can grow (B3.2+/B4) without
crowding ``app/schemas/auth.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

#: Locked plan_status vocabulary — mirrors the CHECK constraint (migration 032,
#: widened by 036 to add ``past_due`` = dunning) + the ``User`` model. Keep in sync.
PlanStatus = Literal["none", "active", "expired", "cancelled", "past_due"]


class AdminSetPlanRequest(BaseModel):
    """Admin override of a user's account-entitlement triple (B3.1).

    PUT / replace semantics: the three billing fields are set exactly as
    given; omitted optional fields are CLEARED (set to ``None``). Touches
    **only** billing fields — never ``role`` / ``is_admin`` /
    ``live_trading_enabled`` (billing is orthogonal to RBAC).
    """

    model_config = ConfigDict(frozen=True)

    plan_status: PlanStatus
    active_plan_id: UUID | None = None
    plan_expires_at: datetime | None = None

    @model_validator(mode="after")
    def _active_requires_plan_and_future_expiry(self) -> AdminSetPlanRequest:
        """``plan_status='active'`` must carry a plan id AND a future expiry;
        every other status leaves ``active_plan_id`` / ``plan_expires_at``
        optional. FK *existence* is checked at the endpoint (404); this
        validator only enforces presence + future-dating → 422 otherwise.
        """
        if self.plan_status == "active":
            if self.active_plan_id is None:
                raise ValueError("plan_status='active' requires active_plan_id")
            if self.plan_expires_at is None:
                raise ValueError("plan_status='active' requires a future plan_expires_at")
            expires = self.plan_expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            if expires <= datetime.now(UTC):
                raise ValueError("plan_status='active' requires plan_expires_at in the future")
        return self


class SubscribeRequest(BaseModel):
    """Start a recurring Razorpay subscription for the caller on a plan."""

    model_config = ConfigDict(frozen=True)

    plan_id: UUID


class CancelRequest(BaseModel):
    """Cancel the caller's recurring subscription. Default = at period end
    (access retained until ``plan_expires_at``); ``at_cycle_end=False`` cancels
    immediately (explicit user action that revokes access now)."""

    model_config = ConfigDict(frozen=True)

    at_cycle_end: bool = True


class ChangePlanRequest(BaseModel):
    """Upgrade / downgrade the caller's platform plan. Takes effect next cycle
    (no proration, no double charge)."""

    model_config = ConfigDict(frozen=True)

    plan_id: UUID


class SubscribeResponse(BaseModel):
    """Handle the frontend Razorpay checkout needs. No secret is returned."""

    razorpay_subscription_id: str
    razorpay_key_id: str  # PUBLIC key id (used by checkout.js), never the secret
    status: str
    short_url: str | None = None
    plan_tier: str
    amount_inr: float


__all__ = [
    "AdminSetPlanRequest",
    "CancelRequest",
    "ChangePlanRequest",
    "PlanStatus",
    "SubscribeRequest",
    "SubscribeResponse",
]
