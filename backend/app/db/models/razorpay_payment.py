"""``razorpay_payments`` — Razorpay order / subscription / payment records.

Phase 2 (Razorpay), Module 1. One row per Razorpay Subscription created for a
user+plan (recurring/mandate flow), updated as webhook events arrive. The
``status`` mirrors the Razorpay subscription lifecycle. This table is the
durable link from a Razorpay ``sub_…`` back to the platform ``user_id`` +
``plan_id`` so the (separately verified, idempotent) webhook can drive the
EXISTING entitlement fields on ``users``.

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
    #: The platform plan being purchased (nullable so an orphaned/odd webhook
    #: can still persist without an FK violation).
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="SET NULL"),
        nullable=True,
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
