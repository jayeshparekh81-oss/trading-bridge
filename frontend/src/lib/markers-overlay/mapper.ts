/**
 * Phase E — Marker → SeriesMarker mapper.
 *
 * Collapses the two-axis Phase A wire shape (``side`` ×
 * ``exit_reason``) back into the one-axis Lightweight Charts
 * ``SeriesMarker`` shape the canvas needs. The existing chart
 * (``CandlestickChart``) already accepts the legacy ``ChartMarker``
 * via its own internal mapper; this module reproduces that visual
 * grammar against the Phase A field names so the cutover keeps the
 * chart's look-and-feel identical.
 *
 * Color choices preserve the existing palette:
 *   - green  #22c55e  long-entry / take-profit-on-long
 *   - red    #ef4444  short-entry / stop-loss-on-long / stop-loss-on-short
 *   - blue   #3b82f6  take-profit-on-short
 *   - gray   #737373  generic exit (SIGNAL / MANUAL / SQUARE_OFF / EXPIRY)
 *
 * Position:
 *   - LONG_ENTRY  belowBar (buy from below)
 *   - LONG_EXIT   aboveBar
 *   - SHORT_ENTRY aboveBar (sell from above)
 *   - SHORT_EXIT  belowBar
 *
 * Highlight handshake: the SeriesMarker.id is the backend UUID of the
 * marker row. Consumers that want a chart-list highlight handshake can
 * pass that UUID through unchanged — no derived "kind:time" fingerprint
 * needed (the Phase A schema gives every marker a stable identifier).
 */

import type { SeriesMarker, UTCTimestamp } from "lightweight-charts";

import type { ChartSeriesMarker, Marker, MarkerSide } from "./types";

// ═══════════════════════════════════════════════════════════════════════
// Palette + shape lookups
// ═══════════════════════════════════════════════════════════════════════

export const MARKER_COLORS = {
  green: "#22c55e",
  red: "#ef4444",
  blue: "#3b82f6",
  gray: "#737373",
} as const;

type SeriesMarkerShape = SeriesMarker<UTCTimestamp>["shape"];
type SeriesMarkerPosition = SeriesMarker<UTCTimestamp>["position"];

const SIDE_POSITION: Record<MarkerSide, SeriesMarkerPosition> = {
  LONG_ENTRY: "belowBar",
  LONG_EXIT: "aboveBar",
  SHORT_ENTRY: "aboveBar",
  SHORT_EXIT: "belowBar",
};

const SIDE_SHAPE: Record<MarkerSide, SeriesMarkerShape> = {
  LONG_ENTRY: "arrowUp",
  LONG_EXIT: "square",
  SHORT_ENTRY: "arrowDown",
  SHORT_EXIT: "square",
};

// ═══════════════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════════════

function formatPrice(price: number): string {
  // Match the existing chart's price formatting — two-decimal max,
  // no trailing zeros, no thousands separator (chart canvas labels
  // stay short to avoid overlapping adjacent bars).
  return price
    .toFixed(2)
    .replace(/\.00$/, "")
    .replace(/(\.\d*?)0+$/, "$1");
}

function entryColor(side: MarkerSide): string {
  return side === "LONG_ENTRY" ? MARKER_COLORS.green : MARKER_COLORS.red;
}

function entryText(side: MarkerSide, price: number): string {
  const verb = side === "LONG_ENTRY" ? "BUY" : "SELL";
  return `${verb} ${formatPrice(price)}`;
}

function exitShape(
  side: MarkerSide,
  reason: Marker["exitReason"],
): SeriesMarkerShape {
  switch (reason) {
    case "TAKE_PROFIT":
      return "circle";
    case "STOP_LOSS":
      // Direction echoes the losing-direction price move — long stopped
      // out as price falls (arrowDown), short stopped out as price
      // rises (arrowUp).
      return side === "LONG_EXIT" ? "arrowDown" : "arrowUp";
    default:
      return SIDE_SHAPE[side];
  }
}

function exitColor(
  side: MarkerSide,
  reason: Marker["exitReason"],
): string {
  switch (reason) {
    case "TAKE_PROFIT":
      // TP-on-long stays green (we hit our target on the way up);
      // TP-on-short uses blue so it's visually distinct from a long
      // entry on the same axis.
      return side === "LONG_EXIT" ? MARKER_COLORS.green : MARKER_COLORS.blue;
    case "STOP_LOSS":
      return MARKER_COLORS.red;
    case "SIGNAL":
    case "MANUAL":
    case "SQUARE_OFF":
    case "EXPIRY":
    case null:
      return MARKER_COLORS.gray;
  }
}

function exitText(marker: Marker): string {
  const priceStr = formatPrice(marker.price);
  switch (marker.exitReason) {
    case "TAKE_PROFIT":
      return `TP ${priceStr}`;
    case "STOP_LOSS":
      return `SL ${priceStr}`;
    case "SQUARE_OFF":
      return `SQOFF ${priceStr}`;
    case "EXPIRY":
      return `EXPIRY ${priceStr}`;
    case "MANUAL":
    case "SIGNAL":
    case null:
      return `EXIT ${priceStr}`;
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Public mapper
// ═══════════════════════════════════════════════════════════════════════

export interface MarkerToSeriesMarkerOptions {
  /** When ``true``, render the marker at size=2 so the canvas-side of
   *  a chart-list highlight handshake produces a visible flash. Same
   *  convention as the legacy CandlestickChart mapper. */
  highlighted?: boolean;
}

export function markerToSeriesMarker(
  marker: Marker,
  opts: MarkerToSeriesMarkerOptions = {},
): ChartSeriesMarker {
  const isEntry = marker.side === "LONG_ENTRY" || marker.side === "SHORT_ENTRY";
  const color = isEntry
    ? entryColor(marker.side)
    : exitColor(marker.side, marker.exitReason);
  const shape = isEntry
    ? SIDE_SHAPE[marker.side]
    : exitShape(marker.side, marker.exitReason);
  const text = isEntry
    ? entryText(marker.side, marker.price)
    : exitText(marker);

  return {
    time: marker.time as UTCTimestamp,
    position: SIDE_POSITION[marker.side],
    shape,
    color,
    id: marker.id,
    text,
    size: opts.highlighted ? 2 : 1,
  };
}

/** Convenience: convert a list of Marker rows to SeriesMarker[].
 *
 * Lightweight Charts asserts strict-ascending time on
 * ``setMarkers([...])``. Backend already returns rows in
 * ``timestamp_utc`` order, but the mapper applies a defensive sort so
 * an out-of-order response (e.g. retry-induced reordering, mock data)
 * doesn't throw inside the canvas. */
export function markersToSeriesMarkers(
  markers: Marker[],
  opts: { highlightedId?: string | null } = {},
): ChartSeriesMarker[] {
  const sorted = [...markers].sort((a, b) => a.time - b.time);
  return sorted.map((m) =>
    markerToSeriesMarker(m, {
      highlighted: opts.highlightedId === m.id,
    }),
  );
}
