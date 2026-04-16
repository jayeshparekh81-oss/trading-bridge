"""Webhook-facing Pydantic schemas.

TradingView alert JSON lands here first. If any of these validations fail,
the request gets a 422 and nothing downstream is touched. That keeps the
webhook hot path bulletproof — malformed payloads can never cost broker
credits or pollute the DB.

Design notes:
    * ``WebhookPayload`` is frozen — the downstream order service receives
      the exact payload the user signed; in-flight mutation would break
      HMAC verification semantics.
    * Decimals, not floats, for money fields.
    * ``extra="ignore"`` on the payload: TradingView users often send extra
      template variables. Strict mode would reject every alert with a
      description or timestamp field.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.broker import Exchange, OrderType, ProductType


# ═══════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════


class WebhookAction(StrEnum):
    """TradingView alert action.

    BUY/SELL create orders; EXIT triggers a symbol-specific square-off.
    Keeping this distinct from :class:`OrderSide` so the webhook vocabulary
    can evolve (e.g. ``REVERSE``) without leaking into broker contracts.
    """

    BUY = "BUY"
    SELL = "SELL"
    EXIT = "EXIT"


class WebhookResponseStatus(StrEnum):
    """Outcome reported back to TradingView."""

    SUCCESS = "success"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    ERROR = "error"


# ═══════════════════════════════════════════════════════════════════════
# Request payload
# ═══════════════════════════════════════════════════════════════════════


class WebhookPayload(BaseModel):
    """Normalized TradingView alert payload.

    Raw JSON example::

        {
          "action": "BUY",
          "symbol": "RELIANCE",
          "exchange": "NSE",
          "quantity": 10,
          "order_type": "MARKET",
          "product_type": "INTRADAY",
          "strategy_name": "ema-crossover",
          "message": "long entry"
        }

    Any extra field TradingView injects (description, timestamp, …) is
    silently discarded via ``extra="ignore"``.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
        str_strip_whitespace=True,
        use_enum_values=False,
    )

    action: WebhookAction
    symbol: str = Field(..., min_length=1, max_length=64)
    exchange: Exchange = Exchange.NSE
    order_type: OrderType = OrderType.MARKET
    product_type: ProductType = ProductType.INTRADAY
    quantity: int = Field(..., gt=0)
    price: Decimal | None = Field(default=None, ge=Decimal("0"))
    trigger_price: Decimal | None = Field(default=None, ge=Decimal("0"))
    stoploss: Decimal | None = Field(default=None, ge=Decimal("0"))
    target: Decimal | None = Field(default=None, ge=Decimal("0"))
    strategy_name: str | None = Field(default=None, max_length=64)
    message: str | None = Field(default=None, max_length=512)
    signal_id: str | None = Field(
        default=None,
        max_length=128,
        description=(
            "Caller-supplied idempotency token. When present, "
            "duplicates are detected by this value; otherwise a content "
            "hash is computed."
        ),
    )

    @model_validator(mode="after")
    def _validate_price_shape(self) -> WebhookPayload:
        """Mirror of ``OrderRequest`` price/trigger rules, at the edge.

        Catching shape errors here means we never hand a broker an
        internally-inconsistent order (e.g., LIMIT without price).
        """
        match self.order_type:
            case OrderType.MARKET:
                if self.price is not None:
                    raise ValueError("MARKET order must not carry a price.")
                if self.trigger_price is not None:
                    raise ValueError("MARKET order must not carry a trigger_price.")
            case OrderType.LIMIT:
                if self.price is None or self.price <= Decimal("0"):
                    raise ValueError("LIMIT order requires a positive price.")
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


# ═══════════════════════════════════════════════════════════════════════
# Response
# ═══════════════════════════════════════════════════════════════════════


class WebhookResponse(BaseModel):
    """Response body returned to the TradingView webhook caller.

    Always includes ``latency_ms`` — TradingView logs it and so do our
    clients; it doubles as a health signal when alerts start bunching up.
    """

    model_config = ConfigDict(extra="forbid")

    status: WebhookResponseStatus
    message: str = ""
    order_id: str | None = None
    trade_id: str | None = None
    latency_ms: int = Field(..., ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "WebhookAction",
    "WebhookPayload",
    "WebhookResponse",
    "WebhookResponseStatus",
]
