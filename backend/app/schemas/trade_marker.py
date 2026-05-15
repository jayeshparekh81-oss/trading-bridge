"""Pydantic schemas for the Phase A trade-markers stack.

Five schemas, one per role in the read/write pipeline:

    * :class:`SignalMetadata`     — typed view over ``trade_markers.signal_metadata``
                                    JSONB column. ``extra="allow"`` so unknown
                                    forward-compatible fields round-trip.
    * :class:`TradeMarkerCreate`  — single-row write payload (service input).
    * :class:`TradeMarkerBulkCreate` — backtest batch-insert envelope.
    * :class:`TradeMarkerRead`    — single-row read shape (API response item).
    * :class:`TradeMarkerFilter`  — query-string params for the list endpoint.
    * :class:`TradeMarkerSummary` — aggregate response for the summary endpoint.

Decimal-valued fields (``price``, ``pnl``) emit as JSON strings to
preserve precision — same convention as ``app.schemas.candle`` and
``app.schemas.chart_marker``. The frontend parses them back to JS
``number`` at render time.

Strict mode (``frozen=True`` + ``extra="forbid"``) on every model
EXCEPT :class:`SignalMetadata` so:
    * Stale fields surface loudly during a schema change.
    * Tests can deep-equal ``model_dump()`` outputs deterministically.
    * Internal fields can't accidentally leak via dict-shaped
      serialisers.

The lone exception is :class:`SignalMetadata`'s ``extra="allow"`` — the
JSONB column is deliberately forward-compatible (a future indicator
sprint should be able to drop a new key in without breaking existing
rows or schemas).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.trade_marker import (
    MarkerExitReason,
    MarkerMode,
    MarkerSide,
)


# ─── JSONB payload schema ──────────────────────────────────────────────


class SignalMetadata(BaseModel):
    """Typed view over ``trade_markers.signal_metadata``.

    Known keys are validated; unknown keys pass through unchanged so a
    later sprint can extend the payload without schema migrations or
    test churn.
    """

    model_config = ConfigDict(extra="allow")

    #: Broker order id, if the marker corresponds to a real fill. ``None``
    #: for paper and backtest markers (no broker round-trip).
    broker_order_id: str | None = Field(default=None, max_length=64)
    #: Snapshot of indicator values at signal time (e.g. ``{"rsi": 72,
    #: "sma_20": 21450.5, "atr": 30.2}``). Used by the strategy-tester
    #: drill-in UI.
    indicator_snapshot: dict[str, Any] | None = None
    #: Raw webhook payload as received (TradingView, custom emitter,
    #: etc.). Stored verbatim for debuggability.
    raw_payload: dict[str, Any] | None = None
    #: Free-form notes — e.g. operator-entered context for MANUAL exits.
    notes: str | None = Field(default=None, max_length=512)


# ─── Write-side schemas ────────────────────────────────────────────────


class TradeMarkerCreate(BaseModel):
    """Single-row write input — what the service emitter consumes.

    The service layer fills in ``id``, ``created_at``, and ``updated_at``
    at insert time; callers provide everything else explicitly. The
    optional ``signal_metadata`` defaults to an empty dict so a caller
    can emit an entry marker with no metadata at all.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy_id: uuid.UUID
    user_id: uuid.UUID
    symbol: str = Field(..., min_length=1, max_length=64)
    exchange: str = Field(..., min_length=1, max_length=16)
    side: MarkerSide
    price: Decimal = Field(..., gt=0)
    quantity: int = Field(..., gt=0)
    timestamp_utc: datetime
    mode: MarkerMode
    linked_marker_id: uuid.UUID | None = None
    pnl: Decimal | None = None
    exit_reason: MarkerExitReason | None = None
    signal_metadata: SignalMetadata | None = None

    @field_validator("timestamp_utc")
    @classmethod
    def _require_timezone(cls, v: datetime) -> datetime:
        """Enforce tz-aware timestamps — naive datetimes leak local
        timezone into the DB and break cross-region comparisons."""
        if v.tzinfo is None:
            raise ValueError(
                "timestamp_utc must be timezone-aware "
                "(ISO 8601 with offset, e.g. 2026-05-14T09:15:00+00:00)."
            )
        return v

    @field_validator("exit_reason")
    @classmethod
    def _exit_reason_only_on_exit(
        cls,
        v: MarkerExitReason | None,
        info: Any,
    ) -> MarkerExitReason | None:
        """Mirror the DB CHECK: ``exit_reason`` only on EXIT rows."""
        if v is None:
            return v
        side = info.data.get("side")
        if side is None:
            return v
        if not MarkerSide.is_exit(side):
            raise ValueError(
                "exit_reason is only valid on LONG_EXIT / SHORT_EXIT "
                "markers."
            )
        return v

    @field_validator("pnl")
    @classmethod
    def _pnl_only_on_exit(
        cls,
        v: Decimal | None,
        info: Any,
    ) -> Decimal | None:
        """Mirror the DB CHECK: ``pnl`` only on EXIT rows."""
        if v is None:
            return v
        side = info.data.get("side")
        if side is None:
            return v
        if not MarkerSide.is_exit(side):
            raise ValueError(
                "pnl is only valid on LONG_EXIT / SHORT_EXIT markers."
            )
        return v


class TradeMarkerBulkCreate(BaseModel):
    """Envelope for backtest batch inserts.

    Backtests emit hundreds of markers per run; bundling them into one
    payload lets the service hand the whole list to a single
    ``session.add_all`` + flush, cutting round-trip cost vs N individual
    ``emit_entry_marker`` calls.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    markers: list[TradeMarkerCreate] = Field(..., min_length=1, max_length=10000)


# ─── Read-side schemas ─────────────────────────────────────────────────


class TradeMarkerRead(BaseModel):
    """One marker, as the read API returns it."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    id: uuid.UUID
    strategy_id: uuid.UUID
    user_id: uuid.UUID
    symbol: str
    exchange: str
    side: MarkerSide
    price: Decimal
    quantity: int
    timestamp_utc: datetime
    mode: MarkerMode
    linked_marker_id: uuid.UUID | None = None
    pnl: Decimal | None = None
    exit_reason: MarkerExitReason | None = None
    signal_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class TradeMarkerFilter(BaseModel):
    """Query-string params for ``GET /api/markers``.

    ``mode`` is REQUIRED — splitting by mode is the whole point of the
    persistent table. ``strategy_id`` is REQUIRED — listing every marker
    a user ever produced would be a footgun.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy_id: uuid.UUID
    mode: MarkerMode
    from_ts: datetime | None = None
    to_ts: datetime | None = None
    symbol: str | None = Field(default=None, min_length=1, max_length=64)
    side: MarkerSide | None = None
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)

    @field_validator("from_ts", "to_ts")
    @classmethod
    def _require_tz(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError(
                "from/to timestamps must be timezone-aware "
                "(ISO 8601 with offset)."
            )
        return v


class TradeMarkerListResponse(BaseModel):
    """Envelope for the list endpoint — markers + pagination echo."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy_id: uuid.UUID
    mode: MarkerMode
    limit: int
    offset: int
    total: int
    markers: list[TradeMarkerRead]


class TradeMarkerSummary(BaseModel):
    """Aggregate stats for ``GET /api/markers/strategy/{id}/summary``.

    Computed from ``mode``-filtered EXIT rows only — entry-only rows
    have ``pnl=NULL`` and don't contribute to realised P&L or win-rate.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy_id: uuid.UUID
    mode: MarkerMode
    #: Count of EXIT rows (= number of closed trades). Open positions
    #: contribute zero — their exit marker hasn't been written yet.
    trade_count: int = Field(..., ge=0)
    #: Sum of ``pnl`` across all EXIT rows in the selected mode.
    total_pnl: Decimal
    #: Fraction in ``[0.0, 1.0]``. Defined as
    #: ``(EXIT rows with pnl > 0) / trade_count``. Returns ``0.0`` when
    #: ``trade_count == 0`` so the frontend never has to handle NaN.
    win_rate: float = Field(..., ge=0.0, le=1.0)
    #: Mean P&L per closed trade. ``Decimal('0')`` when ``trade_count == 0``.
    avg_pnl: Decimal


__all__ = [
    "SignalMetadata",
    "TradeMarkerBulkCreate",
    "TradeMarkerCreate",
    "TradeMarkerFilter",
    "TradeMarkerListResponse",
    "TradeMarkerRead",
    "TradeMarkerSummary",
]
