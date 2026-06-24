"""``subscription_plans`` table — TRADETRI platform subscription tiers (B1).

Phase 2 Billing, module B1: moves the previously hardcoded + duplicated
pricing (the Starter / Pro / Premium tiers rendered on ``/pricing`` and the
home page) into one DB source of truth, killing the two-copy drift.

Read-only catalog for now — NO payment integration here (that is B4+).
``feature_limits`` is an opaque JSON blob carrying everything BOTH pricing
surfaces need to render unchanged:

    * the structured comparison-table flags used by ``/pricing`` (brokers,
      strategies, killSwitch, analytics, telegram, csv, ai, shadowSl,
      support),
    * ``bullets`` — the home page's per-card feature bullet list, and
    * ``popular`` — the "Most Popular" highlight flag.

Additive only — touches no existing table; no FK to strategies/sacred tables.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SubscriptionPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One platform subscription tier (Starter / Pro / Premium)."""

    __tablename__ = "subscription_plans"

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Stable machine key (``starter`` / ``pro`` / ``premium``). Unique so
    #: future entitlement logic can reference a tier without depending on the
    #: display ``name``.
    tier: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)

    #: Stored as Decimal for paise-precision (mirrors marketplace price_inr);
    #: serialised as a plain number at the API boundary.
    price_monthly_inr: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0")
    )
    price_yearly_inr: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0")
    )

    #: Opaque render blob — see module docstring. The API returns it as-is.
    feature_limits: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: The Razorpay Plan id (``plan_…``) this tier maps to (Phase 2, migration
    #: 034_razorpay_billing). Additive/nullable; set once by the create-if-absent
    #: sync so the same tier never spawns duplicate Razorpay plans.
    razorpay_plan_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    def __repr__(self) -> str:
        return (
            f"SubscriptionPlan(id={self.id!r}, tier={self.tier!r}, "
            f"name={self.name!r}, is_active={self.is_active!r})"
        )


__all__ = ["SubscriptionPlan"]
