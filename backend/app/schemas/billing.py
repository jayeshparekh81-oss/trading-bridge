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

#: Locked plan_status vocabulary — mirrors the B2 CHECK constraint
#: (migration 032 + the ``User`` model). Keep the two in sync.
PlanStatus = Literal["none", "active", "expired", "cancelled"]


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


__all__ = ["AdminSetPlanRequest", "PlanStatus"]
