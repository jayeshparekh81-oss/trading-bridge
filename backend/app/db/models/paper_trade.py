"""``paper_trades`` table — durable record of closed paper trades.

Mirrors the in-process Pydantic ``PaperTrade`` snapshot from
:mod:`app.strategy_engine.paper_trading.models` but lives in the DB so
the live-orders SafetyChain (and future analytics) can read closed
trades without depending on the engine's ``_RECORDS`` cache.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.paper_session import PaperSession


class PaperTrade(UUIDPrimaryKeyMixin, Base):
    """One closed paper trade. FK to its parent :class:`PaperSession`."""

    __tablename__ = "paper_trades"
    __table_args__ = (Index("ix_paper_trades_session_id", "session_id"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("paper_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    entry_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    exit_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    entry_price: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), nullable=False
    )
    exit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 4), nullable=True
    )
    pnl: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 4), nullable=True
    )

    exit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[PaperSession] = relationship(
        "PaperSession", back_populates="trades"
    )

    def __repr__(self) -> str:
        return (
            f"PaperTrade(id={self.id!r}, session_id={self.session_id!r}, "
            f"symbol={self.symbol!r}, side={self.side!r}, "
            f"quantity={self.quantity}, pnl={self.pnl})"
        )


__all__ = ["PaperTrade"]
