"""``strategy_positions`` table — live position state.

A position represents the consolidated open exposure for a strategy on
a single symbol. Lifecycle:

    open      → 4 lots filled, full quantity in market
    partial   → some lots booked at target / SL; remaining still open
    closed    → all lots exited; ``final_pnl`` populated

The position-manager loop polls open rows, applies trailing-SL math, and
fires exits via :mod:`app.services.strategy_executor`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Uuid,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class StrategyPosition(UUIDPrimaryKeyMixin, Base):
    """One row per (strategy, symbol) while at least one lot is open."""

    __tablename__ = "strategy_positions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("strategies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    broker_credential_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("broker_credentials.id", ondelete="RESTRICT"),
        nullable=False,
    )
    signal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("strategy_signals.id", ondelete="SET NULL"),
        nullable=True,
    )

    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_entry_price: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True
    )

    # Targets / SL — populated at open time from strategy config
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    stop_loss_price: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    trail_offset: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    highest_price_seen: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    best_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    current_atr: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    circuit_breaker_triggered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false(), default=False
    )
    exit_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Lifecycle: open | partial | closed
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="open", index=True
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    final_pnl: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"StrategyPosition(id={self.id!r}, symbol={self.symbol!r}, "
            f"side={self.side!r}, remaining={self.remaining_quantity}, "
            f"status={self.status!r})"
        )


__all__ = ["StrategyPosition"]
