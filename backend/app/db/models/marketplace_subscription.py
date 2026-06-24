"""``marketplace_subscriptions`` table — who's subscribed to which listing.

Phase 1 ships a "stub payment" flow: ``amount_paid_inr`` records
``listing.price_inr`` at subscribe time as if the payment succeeded.
Phase 4 wires a real gateway (Razorpay / similar) and adds the
escrow / refund / dispute path.

The migration ships a partial unique index on
``(listing_id, subscriber_id) WHERE status = 'active'`` so a user
can re-subscribe after cancelling without violating uniqueness.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MarketplaceSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A subscriber-to-listing link with the paid amount + lifecycle."""

    __tablename__ = "marketplace_subscriptions"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("marketplace_listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscriber_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    subscribed_at: Mapped[datetime] = mapped_column(nullable=False)
    access_until: Mapped[datetime | None] = mapped_column(nullable=True)

    #: Lifecycle — CHECK constraint pins the allowed values at the
    #: migration layer: ``pending`` (M2: Razorpay subscription created,
    #: awaiting first charge) → ``active`` (charge confirmed) →
    #: ``cancelled`` / ``expired``. The Phase-1 stub / free-listing path
    #: still creates rows directly ``active``.
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )

    #: Recurring Razorpay subscription handle (``sub_…``) when this row was
    #: created through the real gateway (M2). NULL for free / stub subs.
    razorpay_subscription_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )

    #: Amount actually paid by the subscriber (in INR). For free
    #: listings this is ``0``; for paid listings the API layer
    #: copies ``listing.price_inr`` here at subscribe time. A real
    #: gateway integration in Phase 4 will replace this with the
    #: confirmed-charge amount from the payment provider.
    amount_paid_inr: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0")
    )

    def __repr__(self) -> str:
        return (
            f"MarketplaceSubscription(id={self.id!r}, "
            f"listing_id={self.listing_id!r}, "
            f"subscriber_id={self.subscriber_id!r}, status={self.status!r})"
        )


__all__ = ["MarketplaceSubscription"]
