"""Copy-trading tables — schema only (Phase 5 feature).

Tables are created in the initial migration so the FKs from future
features line up cleanly, but no service code touches them yet.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class CopyTradingGroup(UUIDPrimaryKeyMixin, Base):
    """A master account publishing trades to followers."""

    __tablename__ = "copy_trading_groups"

    master_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"CopyTradingGroup(id={self.id!r}, name={self.name!r})"


class CopyTradingFollower(UUIDPrimaryKeyMixin, Base):
    """One follower subscribed to a :class:`CopyTradingGroup`."""

    __tablename__ = "copy_trading_followers"

    group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("copy_trading_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    follower_credential_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("broker_credentials.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), default=Decimal("1.0"), nullable=False
    )
    max_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"CopyTradingFollower(id={self.id!r})"


__all__ = ["CopyTradingFollower", "CopyTradingGroup"]
