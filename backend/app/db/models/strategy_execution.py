"""``strategy_executions`` table — every order placement attempt.

Multi-leg by design: one signal can spawn 4 entry rows + N exit rows
(partial profit, trailing-SL trigger, hard SL, kill-switch close). The
``leg_role`` field disambiguates.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class StrategyExecution(UUIDPrimaryKeyMixin, Base):
    """One row per outbound order. Linked back to its ``strategy_signal``."""

    __tablename__ = "strategy_executions"

    signal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("strategy_signals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    broker_credential_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("broker_credentials.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    leg_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # leg_role: entry | partial_target | trailing_sl | hard_sl | exit | kill_switch
    leg_role: Mapped[str] = mapped_column(String(32), nullable=False)

    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)

    broker_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    broker_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    broker_response: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    placed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"StrategyExecution(id={self.id!r}, leg={self.leg_number}/{self.leg_role}, "
            f"symbol={self.symbol!r})"
        )


__all__ = ["StrategyExecution"]
