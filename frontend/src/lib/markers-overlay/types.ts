/**
 * Phase E — Trade-markers overlay wire + render-ready TypeScript types.
 *
 * Mirrors the Phase A Pydantic schemas in
 * ``backend/app/schemas/trade_marker.py`` + the enum module
 * ``backend/app/db/models/trade_marker.py``. The wire contract is the
 * source-of-truth; types here exist only to keep the frontend honest
 * when the backend re-issues a Decimal as a JSON string or surfaces a
 * new ``exit_reason`` literal.
 *
 * Two parallel families per response shape — same convention as
 * :mod:`@/lib/strategy-tester/types` and :mod:`@/lib/chart/types`:
 *
 *   - ``Wire*``  → exact JSON shape on the wire. Decimal-valued
 *                  fields arrive as **strings**. Caller MUST NOT do
 *                  arithmetic on these directly.
 *   - bare types → render-ready form with numeric price/pnl and
 *                  epoch-seconds timestamps. Produced by ``parse*``
 *                  fns below; the hook calls them once on response,
 *                  components consume the parsed shape.
 *
 * Distinct from the legacy ``ChartMarker`` (kind: ENTRY/EXIT/SL_HIT/
 * TP_HIT) — the Phase A schema splits the four-way kind taxonomy into
 * two orthogonal axes (``side`` + ``exit_reason``). The mapper module
 * (``./mapper.ts``) collapses the two-axis backend shape back into the
 * one-axis SeriesMarker shape the chart canvas needs.
 */

import type { SeriesMarker, UTCTimestamp } from "lightweight-charts";

// ═══════════════════════════════════════════════════════════════════════
// Enums — string literals matching backend StrEnum values
// ═══════════════════════════════════════════════════════════════════════

/** Position-event taxonomy. Every marker row carries exactly one. */
export type MarkerSide =
  | "LONG_ENTRY"
  | "LONG_EXIT"
  | "SHORT_ENTRY"
  | "SHORT_EXIT";

/** Execution mode the marker was produced in. */
export type MarkerMode = "BACKTEST" | "PAPER" | "LIVE";

/** Why the position was closed. ``null`` on entry markers. */
export type MarkerExitReason =
  | "SIGNAL"
  | "STOP_LOSS"
  | "TAKE_PROFIT"
  | "MANUAL"
  | "SQUARE_OFF"
  | "EXPIRY";

export function isEntrySide(side: MarkerSide): boolean {
  return side === "LONG_ENTRY" || side === "SHORT_ENTRY";
}

export function isExitSide(side: MarkerSide): boolean {
  return side === "LONG_EXIT" || side === "SHORT_EXIT";
}

export function isLongSide(side: MarkerSide): boolean {
  return side === "LONG_ENTRY" || side === "LONG_EXIT";
}

// ═══════════════════════════════════════════════════════════════════════
// Wire + render shapes
// ═══════════════════════════════════════════════════════════════════════

/** Free-form JSONB payload returned by the backend.
 *
 * Validated server-side via :class:`SignalMetadata` with
 * ``extra="allow"`` — unknown keys round-trip without breaking the
 * schema. We deliberately type as ``Record<string, unknown>`` so a
 * forward-compatible field can be inspected at consumer sites without
 * either a type-cast or a parser update here. */
export type WireSignalMetadata = Record<string, unknown>;

export interface WireMarker {
  id: string;
  strategy_id: string;
  user_id: string;
  symbol: string;
  exchange: string;
  side: MarkerSide;
  /** String-encoded Decimal — parse to ``number`` via :func:`parseMarker`. */
  price: string;
  quantity: number;
  /** ISO 8601 with tz offset (UTC). */
  timestamp_utc: string;
  mode: MarkerMode;
  linked_marker_id: string | null;
  /** String-encoded Decimal; ``null`` on entry markers. */
  pnl: string | null;
  exit_reason: MarkerExitReason | null;
  signal_metadata: WireSignalMetadata;
  /** ISO 8601 with tz offset (UTC). */
  created_at: string;
}

/** Render-time numeric form, post-parse. ``time`` is epoch SECONDS so
 *  a Lightweight Charts ``series.setMarkers([...])`` call can use the
 *  same axis units as the candle series. */
export interface Marker {
  id: string;
  strategyId: string;
  userId: string;
  symbol: string;
  exchange: string;
  side: MarkerSide;
  price: number;
  quantity: number;
  /** Epoch seconds (UTC). */
  time: number;
  mode: MarkerMode;
  linkedMarkerId: string | null;
  pnl: number | null;
  exitReason: MarkerExitReason | null;
  signalMetadata: WireSignalMetadata;
  /** Echo of the wire ISO string — kept for tooltip / row labelling
   *  without paying a round-trip through ``new Date(time * 1000)``. */
  timestampIso: string;
  createdAtIso: string;
}

export interface WireTradeMarkerListResponse {
  strategy_id: string;
  mode: MarkerMode;
  limit: number;
  offset: number;
  total: number;
  markers: WireMarker[];
}

export interface TradeMarkerListResponse {
  strategyId: string;
  mode: MarkerMode;
  limit: number;
  offset: number;
  total: number;
  markers: Marker[];
}

// ═══════════════════════════════════════════════════════════════════════
// Parsers
// ═══════════════════════════════════════════════════════════════════════

export function parseMarker(wire: WireMarker): Marker {
  return {
    id: wire.id,
    strategyId: wire.strategy_id,
    userId: wire.user_id,
    symbol: wire.symbol,
    exchange: wire.exchange,
    side: wire.side,
    price: parseFloat(wire.price),
    quantity: wire.quantity,
    time: Math.floor(new Date(wire.timestamp_utc).getTime() / 1000),
    mode: wire.mode,
    linkedMarkerId: wire.linked_marker_id,
    pnl: wire.pnl === null ? null : parseFloat(wire.pnl),
    exitReason: wire.exit_reason,
    signalMetadata: wire.signal_metadata ?? {},
    timestampIso: wire.timestamp_utc,
    createdAtIso: wire.created_at,
  };
}

export function parseTradeMarkerListResponse(
  wire: WireTradeMarkerListResponse,
): TradeMarkerListResponse {
  return {
    strategyId: wire.strategy_id,
    mode: wire.mode,
    limit: wire.limit,
    offset: wire.offset,
    total: wire.total,
    markers: wire.markers.map(parseMarker),
  };
}

// ═══════════════════════════════════════════════════════════════════════
// Lightweight-Charts adapter alias
// ═══════════════════════════════════════════════════════════════════════

/** Re-export the Lightweight Charts ``SeriesMarker<UTCTimestamp>`` shape
 *  so consumers of this module don't have to pull from
 *  ``lightweight-charts`` directly. The mapper in ``./mapper.ts``
 *  produces values of this exact type. */
export type ChartSeriesMarker = SeriesMarker<UTCTimestamp>;
