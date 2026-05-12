"""Pydantic schemas for the chart-markers endpoint (Day 3).

Day-3 sprint surfaces paper-trading entry/exit events on the chart
canvas so operators can see, at a glance, *where* each strategy bought
and sold during a given session window. The wire shape is consumed by
the frontend's ``useChartMarkers`` hook (Phase 7 scaffold) which
overlays the points on the Lightweight Charts series.

Module status (Day 3 prep / scaffold)
    These schemas are defined and unit-tested but the route that
    returns them (``app.api.chart_markers``) is **not** registered in
    ``main.py`` yet — see ``frontend/PATCH_INSTRUCTIONS_FRONTEND_DAY3.md``
    for the manual ``include_router`` line. The intent is to lock the
    wire contract today (so frontend Phase-7 can scaffold against a
    fixed schema) without exposing an unfinished feature on the live
    API surface.

Wire contract
    Strict mode + frozen + ``extra="forbid"`` so:
        * stale fields surface loudly during a future schema change,
        * the response cannot accidentally leak internal fields if a
          caller switches from explicit ``model_dump()`` to a
          dict-shaped serialiser,
        * tests can deep-equal model dumps for determinism.

    Decimal-valued fields (price, pnl) emit as JSON strings to
    preserve precision — same convention as
    :mod:`app.schemas.candle`. The frontend parses them back to
    JS ``number`` at render time.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ChartMarkerKind(StrEnum):
    """The four-way taxonomy the chart overlay distinguishes.

    The frontend uses this to pick marker shape + colour:
        * ENTRY   — green up-arrow, anchored at price.
        * EXIT    — neutral grey square, generic exit (square-off,
                    time-based, indicator-driven, etc.).
        * SL_HIT  — red down-arrow, stop-loss / trailing-stop fired.
        * TP_HIT  — blue checkmark, take-profit target fired.

    The mapping from ``app.strategy_engine.engines.exit.ExitType`` to
    these four buckets lives in
    :func:`app.services.chart_marker_service.classify_exit` so a
    future ExitType addition only changes one line.
    """

    ENTRY = "ENTRY"
    EXIT = "EXIT"
    SL_HIT = "SL_HIT"
    TP_HIT = "TP_HIT"


class ChartMarker(BaseModel):
    """One marker the chart overlay should render."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ChartMarkerKind
    #: ISO 8601 with tz offset (UTC). The chart anchors the marker to
    #: the candle whose bucket contains this timestamp.
    timestamp: datetime
    #: Fill price (entry price for ENTRY kind, exit price for the
    #: three exit kinds). String-encoded Decimal on the wire.
    price: Decimal = Field(..., gt=0)
    #: Position size. ``> 0`` even for shorts (``side`` discriminates).
    quantity: int = Field(..., gt=0)
    #: ``"BUY"`` for long entries, ``"SELL"`` for shorts. Mirrors the
    #: ``paper_trades.side`` column verbatim.
    side: str = Field(..., min_length=1, max_length=8)
    #: Realised P&L for exit markers; ``None`` on entries (no realised
    #: P&L until the leg closes). String-encoded Decimal on the wire.
    pnl: Decimal | None = None
    #: Free-text reason from ``paper_trades.exit_reason`` — only set on
    #: exit markers. Useful for tooltip surfacing but not used for the
    #: shape/colour selection (that's ``kind``).
    exit_reason: str | None = Field(default=None, max_length=128)


class ChartMarkersResponse(BaseModel):
    """Envelope for ``GET /api/chart/markers``.

    The envelope carries the query echo (so callers can verify the
    response matches the request without re-parsing the URL) and a
    ``cached`` flag set on Redis cache hits.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy_id: str = Field(..., min_length=1)
    symbol: str = Field(..., min_length=1, max_length=64)
    timeframe: str = Field(..., min_length=1, max_length=8)
    from_ts: datetime
    to_ts: datetime
    cached: bool = False
    markers: list[ChartMarker]


__all__ = [
    "ChartMarker",
    "ChartMarkerKind",
    "ChartMarkersResponse",
]
