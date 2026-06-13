"""``alerts`` table — Queue HHH M10 skeleton.

Per-user price-condition alerts. **STORAGE ONLY**: the evaluation
engine that watches live ticks and fires notifications is NOT built
in this sprint and is out-of-scope for Queue HHH. The UI flags this
explicitly to avoid any "it works" impression.

Phase 3+ work (not this sprint):
    * Background tick consumer that checks active alerts against the
      most-recent close and writes to ``last_triggered_at``.
    * Notification fanout via the existing notification_service.
    * Cooldown / rearm policy.

Additive only — new table, no ALTER on existing tables.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# Condition kinds — keep the enum small + grow it in future sprints.
CONDITION_PRICE_ABOVE = "price_above"
CONDITION_PRICE_BELOW = "price_below"

ALL_CONDITION_KINDS: tuple[str, ...] = (
    CONDITION_PRICE_ABOVE,
    CONDITION_PRICE_BELOW,
)


class Alert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One per-user price alert. Storage only; engine in a future sprint."""

    __tablename__ = "alerts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_alerts_user"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    condition_kind: Mapped[str] = mapped_column(Text, nullable=False)
    threshold: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            f"condition_kind IN ({', '.join(repr(k) for k in ALL_CONDITION_KINDS)})",
            name="ck_alerts_condition_kind_enum",
        ),
        Index(
            "ix_alerts_user_active",
            "user_id",
            "is_active",
        ),
        Index(
            "ix_alerts_symbol_active",
            "symbol",
            "is_active",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Alert({self.symbol} {self.condition_kind} {self.threshold} active={self.is_active})>"
        )


__all__ = [
    "ALL_CONDITION_KINDS",
    "CONDITION_PRICE_ABOVE",
    "CONDITION_PRICE_BELOW",
    "Alert",
]
