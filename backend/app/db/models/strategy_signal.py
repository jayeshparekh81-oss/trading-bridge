"""``strategy_signals`` table — every signal received from a webhook source.

A signal is the input contract: a TradingView (or other) alert that says
"BUY NIFTY24500CE". It carries the raw payload for audit, plus parsed
fields the executor needs. AI validation result lives on the same row so
the audit trail is one read.
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


class StrategySignal(UUIDPrimaryKeyMixin, Base):
    """One row per signal received. Lifecycle moves through ``status``."""

    __tablename__ = "strategy_signals"

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

    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_type: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # AI validation
    ai_decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ai_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)

    # Lifecycle: received | validating | rejected | executing | executed | failed
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="received", index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"StrategySignal(id={self.id!r}, symbol={self.symbol!r}, "
            f"action={self.action!r}, status={self.status!r})"
        )


__all__ = ["StrategySignal"]
