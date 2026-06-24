"""``razorpay_payments`` — Razorpay order / subscription / payment records.

Phase 2 (Razorpay), Module 1 + 2. One row per Razorpay Subscription, updated as
webhook events arrive. The ``status`` mirrors the Razorpay subscription
lifecycle. This table is the durable link from a Razorpay ``sub_…`` back to the
platform entity so the (separately verified, idempotent) webhook can apply the
right effect:

    * ``kind == 'platform_plan'`` (M1) — links ``user_id`` + ``plan_id``; the
      webhook drives the EXISTING entitlement fields on ``users``.
    * ``kind == 'marketplace'``   (M2) — links ``user_id`` +
      ``marketplace_subscription_id``; the webhook flips the
      ``marketplace_subscriptions`` row's status. The ONE webhook routes by
      ``kind``.

Payment-only: this model never touches trading state.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RazorpayPayment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A Razorpay subscription/order record for one user+plan."""

    __tablename__ = "razorpay_payments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    #: Which entity this payment funds: ``platform_plan`` (M1) or
    #: ``marketplace`` (M2). Discriminates webhook routing in ONE handler.
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default="platform_plan"
    )

    #: The platform plan being purchased (nullable so an orphaned/odd webhook
    #: can still persist without an FK violation). Set for ``platform_plan``.
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    #: The marketplace subscription being funded. Set for ``marketplace``
    #: (nullable so a platform-plan row leaves it empty; SET NULL on delete).
    marketplace_subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("marketplace_subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    #: One-time order id (``order_…``) — unused by the recurring flow but kept
    #: per the data contract for a future one-time-purchase path.
    razorpay_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Recurring subscription id (``sub_…``) — the primary handle.
    razorpay_subscription_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    #: Latest captured payment id (``pay_…``) — set on ``subscription.charged``.
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    #: created | authenticated | active | charged | halted | cancelled |
    #: completed | failed — the Razorpay subscription lifecycle (free-form so a
    #: new Razorpay status never breaks the webhook).
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")

    amount_inr: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    #: Opaque context (Razorpay short_url, notes, last event, etc.).
    notes: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return (
            f"RazorpayPayment(id={self.id!r}, user_id={self.user_id!r}, "
            f"sub={self.razorpay_subscription_id!r}, status={self.status!r})"
        )


__all__ = ["RazorpayPayment"]
