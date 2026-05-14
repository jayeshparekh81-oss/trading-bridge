/**
 * Chart-module TypeScript types — mirror the backend Pydantic schemas
 * in ``app/schemas/candle.py`` so the wire contract stays one source
 * of truth.
 *
 * Strict mode constraints honoured:
 *   - All optional fields explicitly typed ``T | null`` (never ``T?``
 *     in the JSON shape — backend returns ``null``, not absent).
 *   - Decimal-valued fields (OHLC prices) deserialise as ``string``
 *     because backend's strict Pydantic emits Decimals as JSON strings.
 *     Caller parses to ``number`` at the point of charting.
 *   - Timestamps are ISO 8601 strings (UTC, with offset). ``Date``
 *     parsing happens in the chart renderer.
 */

// ═══════════════════════════════════════════════════════════════════════
// Enums (string literals — matching backend StrEnum values)
// ═══════════════════════════════════════════════════════════════════════

export type Timeframe = "1m" | "3m" | "5m" | "15m" | "30m" | "1h" | "1d";

/** Day-5 UI exposes a subset — matches backend allowlist for historical. */
export const SUPPORTED_TIMEFRAMES: readonly Timeframe[] = [
  "1m",
  "5m",
  "15m",
  "1h",
  "1d",
] as const;

export type Exchange = "NSE" | "BSE" | "NFO" | "BFO" | "MCX" | "CDS" | "IDX";

export type ChartEventType =
  | "tick"
  | "candle"
  | "broker_disconnected"
  | "broker_reconnected"
  | "heartbeat";

// ═══════════════════════════════════════════════════════════════════════
// Wire-shape Candle (OHLC bar)
// ═══════════════════════════════════════════════════════════════════════

/**
 * Matches backend ``app.schemas.candle.Candle``. Prices arrive as
 * **strings** (Decimal-as-JSON convention from the strict-mode
 * Pydantic encoder) — parse to float at chart-render time via
 * :func:`parseCandle`.
 */
export interface WireCandle {
  symbol: string;
  timeframe: Timeframe;
  /** ISO 8601 with tz offset (UTC). Bar OPEN time, not close. */
  timestamp: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: number;
}

/** Same shape but with numeric OHLC — used by the chart renderer. */
export interface Candle {
  symbol: string;
  timeframe: Timeframe;
  /** Epoch seconds (UTC). Lightweight Charts native unit. */
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export function parseCandle(wire: WireCandle): Candle {
  return {
    symbol: wire.symbol,
    timeframe: wire.timeframe,
    time: Math.floor(new Date(wire.timestamp).getTime() / 1000),
    open: parseFloat(wire.open),
    high: parseFloat(wire.high),
    low: parseFloat(wire.low),
    close: parseFloat(wire.close),
    volume: wire.volume,
  };
}

// ═══════════════════════════════════════════════════════════════════════
// REST: GET /api/chart/history response
// ═══════════════════════════════════════════════════════════════════════

export interface ChartHistoryResponse {
  symbol: string;
  timeframe: Timeframe;
  from_ts: string;
  to_ts: string;
  cached: boolean;
  candles: WireCandle[];
}

// ═══════════════════════════════════════════════════════════════════════
// REST: GET /api/chart/ws-token response
// ═══════════════════════════════════════════════════════════════════════

export interface WsTokenResponse {
  token: string;
  /** Lifetime in seconds. Backend issues 900 (15 min). */
  expires_in: number;
}

// ═══════════════════════════════════════════════════════════════════════
// WS: envelope shapes pushed from /ws/chart/{symbol}/{timeframe}
// ═══════════════════════════════════════════════════════════════════════
//
// The backend chart route wraps every message in an envelope:
//   { "event": <ChartEventType>, ...payload }
// Control events (BROKER_DISCONNECTED / BROKER_RECONNECTED / HEARTBEAT)
// carry their own fields; candle frames are { event: "candle", data: WireCandle }.

export interface CandleEnvelope {
  event: "candle";
  data: WireCandle;
}

export interface BrokerDisconnectedEnvelope {
  event: "broker_disconnected";
  symbol: string;
  reason: string;
  failed_attempts: number;
  since: string;
}

export interface BrokerReconnectedEnvelope {
  event: "broker_reconnected";
  symbol: string;
  at: string;
}

export interface HeartbeatEnvelope {
  event: "heartbeat";
  at: string;
}

/** Discriminated union over the ``event`` field. */
export type ChartEnvelope =
  | CandleEnvelope
  | BrokerDisconnectedEnvelope
  | BrokerReconnectedEnvelope
  | HeartbeatEnvelope;

// ═══════════════════════════════════════════════════════════════════════
// Connection status (UI-facing)
// ═══════════════════════════════════════════════════════════════════════

/**
 * Three observable states the chart UI cares about. ``connecting`` and
 * ``open`` are normal; ``disconnected`` is emitted ONLY after the
 * backend's 5-minute reconnect threshold has been breached (BROKER_DISCONNECTED
 * event arrived). Between ``open`` and ``disconnected`` we stay in
 * ``connecting`` while the WS adapter retries silently.
 */
export type ConnectionStatus =
  | { kind: "connecting" }
  | { kind: "open" }
  | {
      kind: "disconnected";
      /** Operator-readable reason from the BROKER_DISCONNECTED event. */
      reason: string;
      /** When the outage opened (ISO 8601, UTC). */
      since: string;
      /** How many reconnect attempts happened before threshold breach. */
      failed_attempts: number;
    };

// ═══════════════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════════════

/**
 * Type guard for the discriminated WS envelope. Useful inside the
 * onmessage handler so TypeScript narrows the payload type for each
 * branch.
 */
export function isCandleEnvelope(
  env: ChartEnvelope,
): env is CandleEnvelope {
  return env.event === "candle";
}

export function isBrokerDisconnectedEnvelope(
  env: ChartEnvelope,
): env is BrokerDisconnectedEnvelope {
  return env.event === "broker_disconnected";
}

export function isBrokerReconnectedEnvelope(
  env: ChartEnvelope,
): env is BrokerReconnectedEnvelope {
  return env.event === "broker_reconnected";
}

export function isHeartbeatEnvelope(
  env: ChartEnvelope,
): env is HeartbeatEnvelope {
  return env.event === "heartbeat";
}

// ═══════════════════════════════════════════════════════════════════════
// Day 3 / Phase 7 — Chart markers (paper-trading entry/exit overlay)
// ═══════════════════════════════════════════════════════════════════════
//
// Mirrors backend ``app.schemas.chart_marker.ChartMarker`` /
// ``ChartMarkerKind`` / ``ChartMarkersResponse``. The wire shape is
// frozen here so frontend Phase-7 (the useChartMarkers hook) and
// backend Phase-6 (the GET /api/chart/markers route) agree on the
// envelope before Day-3 wires them up end-to-end.

/** Four-way taxonomy the chart overlay distinguishes. */
export type ChartMarkerKind = "ENTRY" | "EXIT" | "SL_HIT" | "TP_HIT";

/** Wire shape — Decimal-valued price + pnl arrive as JSON STRINGS to
 *  preserve precision (same convention as :type:`WireCandle`). The
 *  hook parses them to ``number`` at consumption time. */
export interface WireChartMarker {
  kind: ChartMarkerKind;
  /** ISO 8601 with tz offset (UTC). */
  timestamp: string;
  /** String-encoded Decimal. */
  price: string;
  quantity: number;
  side: string;
  /** String-encoded Decimal; ``null`` on entry markers. */
  pnl: string | null;
  exit_reason: string | null;
}

/** Render-time numeric form, post-parse. Time is epoch SECONDS to
 *  match :type:`Candle.time` so a Lightweight Charts
 *  ``series.setMarkers([...])`` call can use the same axis units. */
export interface ChartMarker {
  kind: ChartMarkerKind;
  /** Epoch seconds (UTC). Matches :type:`Candle.time`. */
  time: number;
  price: number;
  quantity: number;
  side: string;
  pnl: number | null;
  exit_reason: string | null;
}

/** Full envelope returned by ``GET /api/chart/markers``. */
export interface ChartMarkersResponse {
  strategy_id: string;
  symbol: string;
  timeframe: string;
  from_ts: string;
  to_ts: string;
  cached: boolean;
  markers: WireChartMarker[];
}

export function parseChartMarker(wire: WireChartMarker): ChartMarker {
  return {
    kind: wire.kind,
    time: Math.floor(new Date(wire.timestamp).getTime() / 1000),
    price: parseFloat(wire.price),
    quantity: wire.quantity,
    side: wire.side,
    pnl: wire.pnl === null ? null : parseFloat(wire.pnl),
    exit_reason: wire.exit_reason,
  };
}

// ═══════════════════════════════════════════════════════════════════════
// Day 3 / Phase 1 — Strategy summary (for the selector dropdown)
// ═══════════════════════════════════════════════════════════════════════
//
// Mirrors a SUBSET of backend ``GET /api/strategies`` response — only
// the fields the chart's StrategySelector needs (id + name +
// is_active). The full Strategy shape is consumed elsewhere in the
// dashboard (``app/(dashboard)/strategies/page.tsx``); duplicating
// the entire shape here would create coupling we don't need.

export interface ChartStrategySummary {
  id: string;
  name: string;
  is_active: boolean;
}

export interface ChartStrategyListResponse {
  strategies: ChartStrategySummary[];
  count: number;
}
