"""``subscription_plan_prices`` — one row per (plan, tenor).

WHY A CHILD TABLE AND NOT MORE COLUMNS
--------------------------------------
Razorpay issues a plan id per (tier, billing interval). Four tenors across three
tiers is TWELVE ids, but ``subscription_plans.razorpay_plan_id`` holds exactly
one per tier. Adding ``price_quarterly_inr`` / ``price_halfyearly_inr`` columns
would have solved the prices and left that unsolved until checkout — the worst
moment to discover it. One row per sellable thing gives each tenor its own id,
and a fifth tenor later is a row rather than another migration.

``subscription_plans.price_monthly_inr`` / ``price_yearly_inr`` remain populated
for one release so nothing breaks mid-deploy; they are legacy once every reader
uses this list.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

#: The sellable billing periods, cheapest-per-month last.
TENORS: tuple[str, ...] = ("monthly", "quarterly", "halfyearly", "yearly")

#: Months billed up front per tenor — drives the "billed ₹X upfront" line.
TENOR_MONTHS: dict[str, int] = {
    "monthly": 1, "quarterly": 3, "halfyearly": 6, "yearly": 12,
}


class SubscriptionPlanPrice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One tier at one tenor, with its OWN Razorpay plan id."""

    __tablename__ = "subscription_plan_prices"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: monthly | quarterly | halfyearly | yearly. A DB CHECK pins the vocabulary
    #: and a UNIQUE (plan_id, tenor) makes a duplicate tenor impossible.
    tenor: Mapped[str] = mapped_column(String(16), nullable=False)

    #: PER-MONTH price at this tenor (not the amount charged). The charged
    #: amount is ``price_per_month_inr * months_billed``.
    price_per_month_inr: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0")
    )
    months_billed: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    #: One Razorpay plan id PER TENOR — the reason this table exists. NULL until
    #: the gateway is configured.
    razorpay_plan_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return (
            f"SubscriptionPlanPrice(plan_id={self.plan_id!r}, "
            f"tenor={self.tenor!r}, per_month={self.price_per_month_inr!r})"
        )


__all__ = ["TENORS", "TENOR_MONTHS", "SubscriptionPlanPrice"]
