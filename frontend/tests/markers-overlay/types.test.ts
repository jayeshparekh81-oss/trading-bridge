/**
 * Parser + helper unit tests for the Phase E markers-overlay types.
 *
 * Verifies:
 *   - Wire → render-ready: Decimal strings parse to numbers, nullable
 *     fields preserved, ISO timestamps convert to epoch seconds.
 *   - Envelope wrapper round-trips (strategyId / mode / pagination).
 *   - Side helpers (isEntrySide, isExitSide, isLongSide) cover all
 *     four enum values.
 *   - signal_metadata round-trips with unknown forward-compatible
 *     fields preserved (the JSONB column is deliberately ``extra=allow``
 *     on the backend).
 */

import { describe, expect, it } from "vitest";

import {
  isEntrySide,
  isExitSide,
  isLongSide,
  parseMarker,
  parseTradeMarkerListResponse,
  type WireMarker,
  type WireTradeMarkerListResponse,
} from "@/lib/markers-overlay/types";

const baseWire: WireMarker = {
  id: "marker-1",
  strategy_id: "11111111-1111-1111-1111-111111111111",
  user_id: "22222222-2222-2222-2222-222222222222",
  symbol: "NIFTY",
  exchange: "NSE",
  side: "LONG_ENTRY",
  price: "22500.50",
  quantity: 50,
  timestamp_utc: "2026-05-14T09:15:00+00:00",
  mode: "PAPER",
  linked_marker_id: null,
  pnl: null,
  exit_reason: null,
  signal_metadata: {
    broker_order_id: "ORDER-42",
    indicator_snapshot: { rsi: 72, sma_20: 21450.5 },
  },
  created_at: "2026-05-14T09:15:00.123+00:00",
};

describe("parseMarker", () => {
  it("converts Decimal-string price to a number", () => {
    const m = parseMarker(baseWire);
    expect(m.price).toBe(22500.5);
    expect(typeof m.price).toBe("number");
  });

  it("converts ISO timestamp_utc to epoch seconds", () => {
    const m = parseMarker(baseWire);
    expect(m.time).toBe(
      Math.floor(new Date(baseWire.timestamp_utc).getTime() / 1000),
    );
  });

  it("keeps pnl null on entry markers", () => {
    const m = parseMarker(baseWire);
    expect(m.pnl).toBeNull();
    expect(m.exitReason).toBeNull();
  });

  it("parses pnl Decimal-string on exit markers", () => {
    const exit: WireMarker = {
      ...baseWire,
      id: "marker-exit",
      side: "LONG_EXIT",
      pnl: "1250.75",
      exit_reason: "TAKE_PROFIT",
      linked_marker_id: "marker-1",
    };
    const m = parseMarker(exit);
    expect(m.pnl).toBe(1250.75);
    expect(m.exitReason).toBe("TAKE_PROFIT");
    expect(m.linkedMarkerId).toBe("marker-1");
  });

  it("preserves signal_metadata including unknown forward-compatible keys", () => {
    const wire: WireMarker = {
      ...baseWire,
      signal_metadata: {
        broker_order_id: "ORDER-7",
        future_field: "should round-trip",
        nested: { foo: "bar" },
      },
    };
    const m = parseMarker(wire);
    expect(m.signalMetadata.broker_order_id).toBe("ORDER-7");
    expect(m.signalMetadata.future_field).toBe("should round-trip");
    expect(m.signalMetadata.nested).toEqual({ foo: "bar" });
  });

  it("echoes the original ISO timestamp + created_at strings for tooltip use", () => {
    const m = parseMarker(baseWire);
    expect(m.timestampIso).toBe(baseWire.timestamp_utc);
    expect(m.createdAtIso).toBe(baseWire.created_at);
  });

  it("camelCases id-shaped fields", () => {
    const m = parseMarker(baseWire);
    expect(m.strategyId).toBe(baseWire.strategy_id);
    expect(m.userId).toBe(baseWire.user_id);
  });

  it("defaults signalMetadata to empty object when wire omits it via null/undef", () => {
    const wire = {
      ...baseWire,
      signal_metadata: null as unknown as Record<string, unknown>,
    };
    const m = parseMarker(wire);
    expect(m.signalMetadata).toEqual({});
  });
});

describe("parseTradeMarkerListResponse", () => {
  const envelope: WireTradeMarkerListResponse = {
    strategy_id: "11111111-1111-1111-1111-111111111111",
    mode: "PAPER",
    limit: 100,
    offset: 0,
    total: 2,
    markers: [
      baseWire,
      {
        ...baseWire,
        id: "marker-2",
        side: "LONG_EXIT",
        price: "22550.25",
        pnl: "2487.50",
        exit_reason: "TAKE_PROFIT",
        timestamp_utc: "2026-05-14T10:00:00+00:00",
        linked_marker_id: "marker-1",
      },
    ],
  };

  it("camelCases envelope fields + parses every marker row", () => {
    const r = parseTradeMarkerListResponse(envelope);
    expect(r.strategyId).toBe(envelope.strategy_id);
    expect(r.mode).toBe("PAPER");
    expect(r.limit).toBe(100);
    expect(r.offset).toBe(0);
    expect(r.total).toBe(2);
    expect(r.markers).toHaveLength(2);
    expect(r.markers[0].price).toBe(22500.5);
    expect(r.markers[1].pnl).toBe(2487.5);
  });

  it("preserves marker order", () => {
    const r = parseTradeMarkerListResponse(envelope);
    expect(r.markers[0].id).toBe("marker-1");
    expect(r.markers[1].id).toBe("marker-2");
  });

  it("handles empty marker list", () => {
    const r = parseTradeMarkerListResponse({ ...envelope, total: 0, markers: [] });
    expect(r.markers).toEqual([]);
    expect(r.total).toBe(0);
  });
});

describe("side helpers", () => {
  it("isEntrySide returns true only for *_ENTRY", () => {
    expect(isEntrySide("LONG_ENTRY")).toBe(true);
    expect(isEntrySide("SHORT_ENTRY")).toBe(true);
    expect(isEntrySide("LONG_EXIT")).toBe(false);
    expect(isEntrySide("SHORT_EXIT")).toBe(false);
  });

  it("isExitSide returns true only for *_EXIT", () => {
    expect(isExitSide("LONG_EXIT")).toBe(true);
    expect(isExitSide("SHORT_EXIT")).toBe(true);
    expect(isExitSide("LONG_ENTRY")).toBe(false);
    expect(isExitSide("SHORT_ENTRY")).toBe(false);
  });

  it("isLongSide returns true for LONG_*", () => {
    expect(isLongSide("LONG_ENTRY")).toBe(true);
    expect(isLongSide("LONG_EXIT")).toBe(true);
    expect(isLongSide("SHORT_ENTRY")).toBe(false);
    expect(isLongSide("SHORT_EXIT")).toBe(false);
  });
});
