"""Pydantic schemas for the Phase B strategy-tester aggregation API.

All response shapes for ``GET /api/strategy-tester/{strategy_id}/...``
endpoints. Reads exclusively from ``trade_markers`` (Phase A).

Decimal-valued fields (P&L, equity, prices) round-trip as JSON strings
to preserve cents-level precision — same convention as
:mod:`app.schemas.trade_marker`. The frontend parses to JS ``number``
at render time.

Strict mode (``frozen=True`` + ``extra="forbid"``) on every model so
deletions of fields surface as test failures rather than silent dict
shrinkage on the wire.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.trade_marker import MarkerExitReason, MarkerMode


# ─── Filter (request-side) ─────────────────────────────────────────────


class StrategyTesterFilter(BaseModel):
    """Common query-string params shared by the three endpoints.

    Constructed from FastAPI ``Query`` params at the route layer; carved
    out here so service-layer signatures can take a single object once
    the surface area grows.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: MarkerMode
    from_ts: datetime | None = None
    to_ts: datetime | None = None
    symbol_filter: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("from_ts", "to_ts")
    @classmethod
    def _require_tz(cls, v: datetime | None) -> datetime | None:
        """Naive timestamps leak local-tz into PG; reject at the edge."""
        if v is not None and v.tzinfo is None:
            raise ValueError(
                "from/to timestamps must be timezone-aware "
                "(ISO 8601 with offset, e.g. 2026-05-14T09:15:00+05:30)."
            )
        return v


# ─── Metrics ───────────────────────────────────────────────────────────


class StrategyTesterMetrics(BaseModel):
    """Aggregate report-card numbers for one strategy + mode.

    All counts are over CLOSED trades only (entries with a linked exit
    in the window). Open positions don't contribute to realised metrics.

    ``profit_factor`` is ``None`` when there are no losing trades AND at
    least one winning trade (mathematically infinite — surface as
    ``null`` rather than an arbitrary cap so the frontend can render
    ``∞`` deliberately). Returns ``Decimal('0')`` on a fully empty set.

    ``sharpe_ratio_proxy`` is a per-trade proxy: ``mean(pnl) /
    stdev(pnl)``. Not annualised — chart UI labels it explicitly as a
    proxy. ``None`` when fewer than 2 closed trades or zero variance.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_pnl: Decimal
    win_rate_pct: float = Field(..., ge=0.0, le=100.0)
    profit_factor: float | None = Field(default=None, ge=0.0)
    total_trades: int = Field(..., ge=0)
    profitable_trades: int = Field(..., ge=0)
    max_drawdown_pct: float = Field(..., ge=0.0, le=100.0)
    sharpe_ratio_proxy: float | None = None
    avg_win: Decimal
    avg_loss: Decimal
    largest_win: Decimal
    largest_loss: Decimal
    expectancy: Decimal


# ─── Equity curve ──────────────────────────────────────────────────────


class EquityPoint(BaseModel):
    """One point on the equity curve.

    ``trade_id_or_none`` references the EXIT marker that produced this
    step (so the chart can wire each point to its underlying trade for
    drill-in). The first point — the starting-equity anchor — has no
    trade_id.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: datetime
    equity: Decimal
    drawdown_pct: float = Field(..., ge=0.0, le=100.0)
    trade_id_or_none: uuid.UUID | None = None


class EquityCurveResponse(BaseModel):
    """Envelope for ``GET /equity``.

    ``starting_equity`` echoes the caller-supplied value so the frontend
    needn't track it independently. ``ending_equity`` matches
    ``points[-1].equity`` when there's at least one trade, else equals
    ``starting_equity`` (we still return the anchor point in that case).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    points: list[EquityPoint]
    starting_equity: Decimal
    ending_equity: Decimal
    max_equity: Decimal
    min_equity: Decimal


# ─── Trade list ────────────────────────────────────────────────────────


class TradeRecord(BaseModel):
    """One closed-or-open trade.

    Built by pairing an entry marker with its linked exit (if any).
    Open trades have ``exit_marker_id``, ``exit_time``, ``exit_price``,
    ``pnl``, ``pnl_pct``, ``duration_minutes``, and ``exit_reason`` all
    set to ``None``.

    ``side`` is the position side, NOT the marker side enum:
        * ``LONG``  ← anchored on a ``LONG_ENTRY`` marker
        * ``SHORT`` ← anchored on a ``SHORT_ENTRY`` marker
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    entry_marker_id: uuid.UUID
    exit_marker_id: uuid.UUID | None = None
    symbol: str
    side: str = Field(..., pattern="^(LONG|SHORT)$")
    entry_time: datetime
    exit_time: datetime | None = None
    entry_price: Decimal
    exit_price: Decimal | None = None
    qty: int = Field(..., gt=0)
    pnl: Decimal | None = None
    pnl_pct: float | None = None
    duration_minutes: float | None = None
    exit_reason: MarkerExitReason | None = None


class TradePagination(BaseModel):
    """Pagination echo block for the trade-list response."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    limit: int = Field(..., ge=1, le=500)
    offset: int = Field(..., ge=0)
    total: int = Field(..., ge=0)


class TradeListResponse(BaseModel):
    """Envelope for ``GET /trades``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    trades: list[TradeRecord]
    pagination: TradePagination
    mode: MarkerMode


__all__ = [
    "EquityCurveResponse",
    "EquityPoint",
    "StrategyTesterFilter",
    "StrategyTesterMetrics",
    "TradeListResponse",
    "TradePagination",
    "TradeRecord",
]
