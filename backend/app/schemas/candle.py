"""Chart-module Pydantic v2 schemas — ticks, candles, history responses.

These contracts back three flows:
    * Live ticks from ``DhanWebSocketAdapter`` published on Redis pub/sub
      (``chart:ticks:{symbol}``).
    * Aggregated OHLC bars (``chart:candles:{symbol}:{timeframe}``) used
      by the live chart WebSocket and the REST history endpoint.
    * Control-plane events (``BrokerDisconnectedEvent`` etc.) that the
      WebSocket route forwards to the browser so the frontend can show
      a Hinglish disconnect banner.

Design rules:
    * Every model is ``frozen=True`` + ``strict=True`` + ``extra="forbid"``.
      Strict catches the silent ``"42.5"`` → ``42.5`` float coercion that
      Pydantic v2 does by default; frozen prevents in-flight mutation
      after a candle leaves the aggregator.
    * Prices use :class:`~decimal.Decimal` — never ``float``. OHLC values
      are monetary and must round-trip exactly through JSON.
    * Timestamps are ``datetime`` with a non-null ``tzinfo`` (UTC). Aware
      datetimes mean every consumer can compare bars without first
      guessing their timezone.
    * Symbol is stored upper-case so cache keys, channel names, and
      broker requests all align without a downstream ``.upper()`` call.

Yeh schemas chart-module ke har layer mein ek hi shape ka enforce karte
hain — WS adapter, Redis pub/sub, REST API, frontend — sab same contract.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ═══════════════════════════════════════════════════════════════════════
# Timeframe enum
# ═══════════════════════════════════════════════════════════════════════


class Timeframe(StrEnum):
    """Candle aggregation windows supported by the chart module.

    The string value is also used as the URL path segment in
    ``/ws/chart/{symbol}/{timeframe}`` and as part of the Redis channel
    name, so keep these tokens short and URL-safe.
    """

    ONE_MIN = "1m"
    THREE_MIN = "3m"
    FIVE_MIN = "5m"
    FIFTEEN_MIN = "15m"
    THIRTY_MIN = "30m"
    ONE_HOUR = "1h"
    ONE_DAY = "1d"

    @property
    def seconds(self) -> int:
        """Window size in seconds — used by the candle aggregator to
        decide when to roll a bar."""
        return _TIMEFRAME_SECONDS[self]


_TIMEFRAME_SECONDS: dict[Timeframe, int] = {
    Timeframe.ONE_MIN: 60,
    Timeframe.THREE_MIN: 180,
    Timeframe.FIVE_MIN: 300,
    Timeframe.FIFTEEN_MIN: 900,
    Timeframe.THIRTY_MIN: 1_800,
    Timeframe.ONE_HOUR: 3_600,
    Timeframe.ONE_DAY: 86_400,
}


# ═══════════════════════════════════════════════════════════════════════
# Tick (raw broker payload, normalized)
# ═══════════════════════════════════════════════════════════════════════


class TickData(BaseModel):
    """A single market-data tick after broker-specific normalisation.

    The Dhan binary tick frame is decoded into this shape inside
    :mod:`app.brokers.dhan_websocket`. Downstream (aggregator, frontend
    fallback rendering) cares only about this normalized form.
    """

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    symbol: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Trading symbol in upper-case (matches scrip master).",
    )
    exchange_segment: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Dhan exchange segment (e.g. NSE_EQ, NSE_FNO).",
    )
    ltp: Decimal = Field(..., gt=Decimal("0"), description="Last traded price.")
    last_traded_quantity: int = Field(
        default=0, ge=0, description="Quantity of the last trade."
    )
    volume: int = Field(
        default=0, ge=0, description="Cumulative day volume up to this tick."
    )
    timestamp: datetime = Field(
        ..., description="Exchange tick timestamp (UTC, aware)."
    )

    @field_validator("symbol", "exchange_segment")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("timestamp")
    @classmethod
    def _tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware (UTC).")
        return value


# ═══════════════════════════════════════════════════════════════════════
# Candle (OHLC bar)
# ═══════════════════════════════════════════════════════════════════════


class Candle(BaseModel):
    """One OHLC bar at a fixed timeframe.

    The aggregator builds these from :class:`TickData`; the historical
    endpoint deserialises them directly from Dhan's ``/charts/historical``
    response. Both paths share this single shape so a chart consumer
    can splice live + historical without conversion.
    """

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    symbol: str = Field(..., min_length=1, max_length=64)
    timeframe: Timeframe = Field(...)
    timestamp: datetime = Field(
        ..., description="Bar open time (UTC, aware)."
    )
    open: Decimal = Field(..., gt=Decimal("0"))
    high: Decimal = Field(..., gt=Decimal("0"))
    low: Decimal = Field(..., gt=Decimal("0"))
    close: Decimal = Field(..., gt=Decimal("0"))
    volume: int = Field(default=0, ge=0)

    @field_validator("symbol")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("timestamp")
    @classmethod
    def _tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware (UTC).")
        return value

    @model_validator(mode="after")
    def _ohlc_invariants(self) -> Candle:
        """Enforce OHLC sanity: high == max, low == min, low <= open/close <= high.

        Bars violating this come from broker bugs or partial frames — we
        refuse to propagate them so charting clients never have to deal
        with high < low oddities.
        """
        if self.high < self.low:
            raise ValueError(
                f"Candle invariant violated: high ({self.high}) < low ({self.low})."
            )
        if not (self.low <= self.open <= self.high):
            raise ValueError(
                f"Candle invariant violated: open ({self.open}) outside "
                f"[low={self.low}, high={self.high}]."
            )
        if not (self.low <= self.close <= self.high):
            raise ValueError(
                f"Candle invariant violated: close ({self.close}) outside "
                f"[low={self.low}, high={self.high}]."
            )
        return self


# ═══════════════════════════════════════════════════════════════════════
# Historical endpoint response
# ═══════════════════════════════════════════════════════════════════════


class ChartHistoryResponse(BaseModel):
    """Response shape for ``GET /api/chart/history``.

    ``cached=True`` means the bars came from the Redis 5-min cache. The
    flag travels through to the frontend so the UI can surface "live"
    vs "from cache" indicators when ops are debugging stale renders.
    """

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    symbol: str = Field(..., min_length=1, max_length=64)
    timeframe: Timeframe = Field(...)
    from_ts: datetime = Field(..., description="Inclusive window start (UTC).")
    to_ts: datetime = Field(..., description="Inclusive window end (UTC).")
    cached: bool = Field(default=False)
    candles: list[Candle] = Field(default_factory=list)

    @field_validator("symbol")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("from_ts", "to_ts")
    @classmethod
    def _tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware (UTC).")
        return value

    @model_validator(mode="after")
    def _window_ordered(self) -> ChartHistoryResponse:
        if self.from_ts > self.to_ts:
            raise ValueError(
                f"from_ts ({self.from_ts.isoformat()}) must be <= "
                f"to_ts ({self.to_ts.isoformat()})."
            )
        return self


# ═══════════════════════════════════════════════════════════════════════
# Control events — pushed over the live WS to the browser
# ═══════════════════════════════════════════════════════════════════════


class ChartEventType(StrEnum):
    """Discriminator for the JSON envelope the live WS sends to clients."""

    TICK = "tick"
    CANDLE = "candle"
    BROKER_DISCONNECTED = "broker_disconnected"
    BROKER_RECONNECTED = "broker_reconnected"
    HEARTBEAT = "heartbeat"


class BrokerDisconnectedEvent(BaseModel):
    """Emitted when the WS adapter has been reconnecting unsuccessfully
    for longer than the disconnect threshold (default 5 minutes).

    The frontend should render a Hinglish banner — e.g.
    "Broker connection toot gaya, retry kar rahe hain..." — and continue
    rendering the last-known candles while we keep retrying in the
    background.
    """

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    event: ChartEventType = Field(default=ChartEventType.BROKER_DISCONNECTED)
    symbol: str = Field(..., min_length=1, max_length=64)
    reason: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Operator-readable English reason; UI may show its own copy.",
    )
    failed_attempts: int = Field(..., ge=1, description="Consecutive reconnect attempts so far.")
    since: datetime = Field(..., description="When the disconnect window opened (UTC).")

    @field_validator("symbol")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("since")
    @classmethod
    def _tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("since must be timezone-aware (UTC).")
        return value


class BrokerReconnectedEvent(BaseModel):
    """Emitted exactly once when the WS adapter recovers from a
    BROKER_DISCONNECTED state. Lets the frontend dismiss its banner."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    event: ChartEventType = Field(default=ChartEventType.BROKER_RECONNECTED)
    symbol: str = Field(..., min_length=1, max_length=64)
    at: datetime = Field(..., description="Recovery timestamp (UTC).")

    @field_validator("symbol")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("at")
    @classmethod
    def _tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("at must be timezone-aware (UTC).")
        return value


__all__ = [
    "BrokerDisconnectedEvent",
    "BrokerReconnectedEvent",
    "Candle",
    "ChartEventType",
    "ChartHistoryResponse",
    "TickData",
    "Timeframe",
]
