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

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Uuid, true
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

    # ── Module 4: per-subscriber execution config (migration 035, additive) ──
    # The OWNER 1->1 path has no rows in this table, so none of these affect it.
    #: Per-subscriber position size in LOTS. NULL => use the strategy default.
    lots_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: How the subscriber takes signals: 'auto' | 'one_click' | 'offline'.
    #: CARRIED but NOT yet branched on (Module 4). CHECK at the migration layer.
    execution_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="auto", default="auto"
    )
    #: PAPER vs real for THIS subscriber. Default paper. Real money is gated to
    #: a later, separately-empanelled phase; the fan-out forces paper today and
    #: does NOT branch on this flag.
    is_paper: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=true(), default=True
    )
    #: 'all' | 'long' | 'short' — directions this subscriber takes. CARRIED but
    #: NOT yet branched on (Module 4). CHECK at the migration layer.
    direction_filter: Mapped[str] = mapped_column(
        String(8), nullable=False, server_default="all", default="all"
    )
    #: The subscriber's chosen broker credential. The fan-out resolves/validates
    #: it, but in PAPER it is only RECORDED — never used to build/call a broker
    #: or place a real order. NULL => auto-resolve among the subscriber's active
    #: credentials.
    broker_credential_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("broker_credentials.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"MarketplaceSubscription(id={self.id!r}, "
            f"listing_id={self.listing_id!r}, "
            f"subscriber_id={self.subscriber_id!r}, status={self.status!r})"
        )


__all__ = ["MarketplaceSubscription"]
