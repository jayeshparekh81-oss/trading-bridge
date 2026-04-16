"""Kill-switch tables — user config + triggered-event history."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.user import User


class KillSwitchConfig(Base):
    """Per-user kill-switch thresholds.

    ``user_id`` is both PK and FK — one config row per user.
    """

    __tablename__ = "kill_switch_config"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    max_daily_loss_inr: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("10000"), nullable=False
    )
    max_daily_trades: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_square_off: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="kill_switch_config")

    def __repr__(self) -> str:
        return f"KillSwitchConfig(user_id={self.user_id!r}, enabled={self.enabled!r})"


class KillSwitchEvent(UUIDPrimaryKeyMixin, Base):
    """One triggered kill-switch firing — append-only history."""

    __tablename__ = "kill_switch_events"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    daily_pnl_at_trigger: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    positions_squared_off: Mapped[list[Any]] = mapped_column(
        JSON, default=list, nullable=False
    )
    reset_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reset_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"KillSwitchEvent(id={self.id!r}, user_id={self.user_id!r})"


__all__ = ["KillSwitchConfig", "KillSwitchEvent"]
