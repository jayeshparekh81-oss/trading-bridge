"""``razorpay_webhook_events`` — durable idempotency + audit for webhooks.

Phase 2 (Razorpay), Module 1. Every accepted (signature-verified) webhook
records its idempotency key here under a UNIQUE constraint. A duplicate
delivery of the same event collides on insert and is treated as already
processed → the entitlement side-effect happens **exactly once**. Durable (DB,
not Redis TTL) because payment events drive real-money entitlements.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class RazorpayWebhookEvent(UUIDPrimaryKeyMixin, Base):
    """One row per processed Razorpay webhook event (idempotency ledger)."""

    __tablename__ = "razorpay_webhook_events"

    #: Idempotency key — the Razorpay ``X-Razorpay-Event-Id`` header when
    #: present, else a derived ``{event}:{entity_id}:{created_at}``. UNIQUE so a
    #: duplicate delivery cannot apply the entitlement effect twice.
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)

    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    razorpay_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"RazorpayWebhookEvent(event_id={self.event_id!r}, "
            f"event_type={self.event_type!r})"
        )


__all__ = ["RazorpayWebhookEvent"]
