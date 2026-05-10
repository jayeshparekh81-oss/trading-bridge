"""Broker-facing Pydantic schemas.

Yahan har broker integration ke liye shared data contracts define hain.
`BrokerInterface` in sab models ko use karta hai — toh koi bhi naya broker
(Fyers, Dhan, Zerodha, …) exactly same shape mein data return karega.

Design rules:
    * `Decimal` only for money — never `float`.
    * Enums for every fixed vocabulary — no magic strings leak into services.
    * Models are frozen (`model_config.frozen = True`) so broker code cannot
      mutate a request/response object in place.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ═══════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════


class BrokerName(StrEnum):
    """Supported brokers. Order follows the integration roadmap."""

    FYERS = "fyers"
    DHAN = "dhan"
    SHOONYA = "shoonya"
    ZERODHA = "zerodha"
    UPSTOX = "upstox"
    ANGELONE = "angelone"


class OrderSide(StrEnum):
    """Trade direction."""

    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    """Order types supported across Indian brokers.

    * ``MARKET``  — Execute at best available price.
    * ``LIMIT``   — Execute only at ``price`` or better.
    * ``SL``      — Stop-loss limit (needs ``trigger_price`` + ``price``).
    * ``SL_M``    — Stop-loss market (needs ``trigger_price`` only).
    """

    MARKET = "market"
    LIMIT = "limit"
    SL = "sl"
    SL_M = "sl_m"


class ProductType(StrEnum):
    """Product / margin category.

    * ``INTRADAY`` — MIS, square-off same day.
    * ``DELIVERY`` — CNC, T+1 settlement.
    * ``MARGIN``   — NRML / overnight margin (F&O carry-forward).
    * ``BO``       — Bracket order (auto SL + target).
    * ``CO``       — Cover order (mandatory SL).
    """

    INTRADAY = "intraday"
    DELIVERY = "delivery"
    MARGIN = "margin"
    BO = "bo"
    CO = "co"


class Exchange(StrEnum):
    """Indian exchanges and segments."""

    NSE = "NSE"   # NSE cash
    BSE = "BSE"   # BSE cash
    NFO = "NFO"   # NSE F&O
    BFO = "BFO"   # BSE F&O
    MCX = "MCX"   # Commodities
    CDS = "CDS"   # Currency derivatives


class OrderStatus(StrEnum):
    """Normalized order status — each broker's raw status maps into these."""

    PENDING = "pending"       # Submitted to broker, awaiting ack
    OPEN = "open"             # Ack'd, sitting in order book
    COMPLETE = "complete"     # Fully filled
    CANCELLED = "cancelled"   # User/system cancelled
    REJECTED = "rejected"     # Broker rejected
    PARTIAL = "partial"       # Partially filled


# ═══════════════════════════════════════════════════════════════════════
# Base model
# ═══════════════════════════════════════════════════════════════════════


class _BrokerBaseModel(BaseModel):
    """Shared Pydantic config for all broker schemas.

    Frozen models prevent in-place mutation from broker code — a request
    object handed to ``place_order`` must be reusable / auditable.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


# ═══════════════════════════════════════════════════════════════════════
# Credentials (decrypted form handed to broker client)
# ═══════════════════════════════════════════════════════════════════════


class BrokerCredentials(_BrokerBaseModel):
    """Decrypted broker credentials passed to a broker class constructor.

    Storage mein ye Fernet-encrypted hote hain — decryption kernel-side
    hota hai, phir is model mein wrap karke broker ko dete hain.
    """

    broker: BrokerName
    user_id: str = Field(..., description="Our internal user UUID (stringified).")
    client_id: str = Field(..., description="Broker-issued client / login ID.")
    api_key: str
    api_secret: str
    access_token: str | None = Field(
        default=None,
        description="Current session token; may be None until first login().",
    )
    refresh_token: str | None = None
    token_expires_at: datetime | None = None
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Broker-specific fields (e.g., Fyers PIN, TOTP secret).",
    )


# ═══════════════════════════════════════════════════════════════════════
# Orders
# ═══════════════════════════════════════════════════════════════════════


class OrderRequest(_BrokerBaseModel):
    """Normalized order request.

    BrokerInterface implementations translate this into each broker's
    native payload. Cross-field validation enforces the price/trigger
    rules for LIMIT and SL variants.
    """

    symbol: str = Field(..., min_length=1, max_length=64)
    exchange: Exchange
    side: OrderSide
    quantity: int = Field(..., gt=0, description="Lot-adjusted quantity, always positive.")
    order_type: OrderType
    product_type: ProductType
    price: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        description="Limit price — required for LIMIT and SL orders.",
    )
    trigger_price: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        description="Trigger price — required for SL and SL_M orders.",
    )
    tag: str | None = Field(
        default=None,
        max_length=32,
        description="Optional client tag (e.g., strategy name) for reconciliation.",
    )

    @model_validator(mode="after")
    def _validate_price_and_trigger(self) -> OrderRequest:
        """Price/trigger rules per order type — reject ambiguous requests early."""
        match self.order_type:
            case OrderType.MARKET:
                if self.price is not None:
                    raise ValueError("MARKET order must not carry a price.")
                if self.trigger_price is not None:
                    raise ValueError("MARKET order must not carry a trigger_price.")
            case OrderType.LIMIT:
                if self.price is None or self.price <= Decimal("0"):
                    raise ValueError("LIMIT order requires a positive price.")
                if self.trigger_price is not None:
                    raise ValueError("LIMIT order must not carry a trigger_price.")
            case OrderType.SL:
                if self.price is None or self.price <= Decimal("0"):
                    raise ValueError("SL order requires a positive price.")
                if self.trigger_price is None or self.trigger_price <= Decimal("0"):
                    raise ValueError("SL order requires a positive trigger_price.")
            case OrderType.SL_M:
                if self.trigger_price is None or self.trigger_price <= Decimal("0"):
                    raise ValueError("SL_M order requires a positive trigger_price.")
                if self.price is not None:
                    raise ValueError("SL_M order must not carry a price.")
        return self


class OrderResponse(_BrokerBaseModel):
    """Normalized order response from a broker.

    ``raw_response`` preserves the broker's full payload for audit and
    debugging — we never lose information by normalizing.
    """

    broker_order_id: str
    status: OrderStatus
    message: str = Field(default="", description="Broker-provided status message.")
    raw_response: dict[str, Any] = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════
# Portfolio
# ═══════════════════════════════════════════════════════════════════════


class Position(_BrokerBaseModel):
    """Open position — intraday or overnight (F&O carry-forward).

    ``quantity`` is signed: positive = long, negative = short.
    """

    symbol: str
    exchange: Exchange
    quantity: int
    avg_price: Decimal = Field(..., ge=Decimal("0"))
    ltp: Decimal = Field(..., ge=Decimal("0"), description="Last traded price.")
    unrealized_pnl: Decimal
    product_type: ProductType


class Holding(_BrokerBaseModel):
    """Delivery holding (CNC / T+1 settled, sitting in demat)."""

    symbol: str
    exchange: Exchange
    quantity: int = Field(..., gt=0)
    avg_price: Decimal = Field(..., ge=Decimal("0"))
    ltp: Decimal = Field(..., ge=Decimal("0"))
    current_value: Decimal = Field(..., ge=Decimal("0"))
    pnl: Decimal


# ═══════════════════════════════════════════════════════════════════════
# Market data
# ═══════════════════════════════════════════════════════════════════════


class Quote(_BrokerBaseModel):
    """Lightweight market quote used by kill-switch valuation and pre-trade checks."""

    symbol: str
    exchange: Exchange
    ltp: Decimal = Field(..., ge=Decimal("0"))
    bid: Decimal = Field(..., ge=Decimal("0"))
    ask: Decimal = Field(..., ge=Decimal("0"))
    volume: int = Field(..., ge=0)
    timestamp: datetime


__all__ = [
    "BrokerCredentials",
    "BrokerName",
    "Exchange",
    "Holding",
    "OrderRequest",
    "OrderResponse",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "Position",
    "ProductType",
    "Quote",
]
