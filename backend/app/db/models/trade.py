"""``trades`` table — every order placed through the platform."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.schemas.broker import OrderSide, OrderType, ProductType


class TradeStatus(StrEnum):
    """Persisted lifecycle state for a trade row.

    Kept distinct from :class:`app.schemas.broker.OrderStatus` because
    the DB view has extra terminal states — e.g., ``SQUARED_OFF`` by
    the kill switch — that the broker contract does not expose.
    """

    PENDING = "pending"
    OPEN = "open"
    COMPLETE = "complete"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    PARTIAL = "partial"
    SQUARED_OFF = "squared_off"


class ProcessingStatus(StrEnum):
    """Pipeline status shared by webhook events and trades."""

    RECEIVED = "received"
    VALIDATED = "validated"
    EXECUTED = "executed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Trade(UUIDPrimaryKeyMixin, Base):
    """One trade attempt — final, immutable audit target."""

    __tablename__ = "trades"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    broker_credential_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("broker_credentials.id", ondelete="RESTRICT"),
        nullable=False,
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("strategies.id", ondelete="SET NULL"),
        nullable=True,
    )
    broker_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    tradingview_signal_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    exchange: Mapped[str] = mapped_column(String(8), nullable=False)
    side: Mapped[OrderSide] = mapped_column(
        SAEnum(OrderSide, name="order_side_enum", native_enum=False),
        nullable=False,
    )
    order_type: Mapped[OrderType] = mapped_column(
        SAEnum(OrderType, name="order_type_enum", native_enum=False),
        nullable=False,
    )
    product_type: Mapped[ProductType] = mapped_column(
        SAEnum(ProductType, name="product_type_enum", native_enum=False),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    avg_fill_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    status: Mapped[TradeStatus] = mapped_column(
        SAEnum(TradeStatus, name="trade_status_enum", native_enum=False),
        nullable=False,
        default=TradeStatus.PENDING,
    )
    placed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    filled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pnl_realized: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"Trade(id={self.id!r}, symbol={self.symbol!r}, "
            f"side={self.side!r}, status={self.status!r})"
        )


__all__ = ["ProcessingStatus", "Trade", "TradeStatus"]
