/**
 * Mapper unit tests — Marker → Lightweight-Charts SeriesMarker.
 *
 * Covers the full 4-side × 6-exit_reason matrix (where applicable),
 * plus the highlight + sort behaviour of the bulk helper.
 */

import { describe, expect, it } from "vitest";

import {
  MARKER_COLORS,
  markerToSeriesMarker,
  markersToSeriesMarkers,
} from "@/lib/markers-overlay/mapper";
import type { Marker, MarkerExitReason } from "@/lib/markers-overlay/types";

function marker(overrides: Partial<Marker> = {}): Marker {
  return {
    id: "m-1",
    strategyId: "s-1",
    userId: "u-1",
    symbol: "NIFTY",
    exchange: "NSE",
    side: "LONG_ENTRY",
    price: 22500,
    quantity: 50,
    time: 1715679000,
    mode: "PAPER",
    linkedMarkerId: null,
    pnl: null,
    exitReason: null,
    signalMetadata: {},
    timestampIso: "2026-05-14T09:15:00+00:00",
    createdAtIso: "2026-05-14T09:15:00.123+00:00",
    ...overrides,
  };
}

describe("markerToSeriesMarker — entries", () => {
  it("LONG_ENTRY → arrowUp belowBar, green, BUY text", () => {
    const sm = markerToSeriesMarker(marker({ side: "LONG_ENTRY", price: 22500 }));
    expect(sm.shape).toBe("arrowUp");
    expect(sm.position).toBe("belowBar");
    expect(sm.color).toBe(MARKER_COLORS.green);
    expect(sm.text).toBe("BUY 22500");
    expect(sm.id).toBe("m-1");
  });

  it("SHORT_ENTRY → arrowDown aboveBar, red, SELL text", () => {
    const sm = markerToSeriesMarker(
      marker({ side: "SHORT_ENTRY", price: 22600.5 }),
    );
    expect(sm.shape).toBe("arrowDown");
    expect(sm.position).toBe("aboveBar");
    expect(sm.color).toBe(MARKER_COLORS.red);
    expect(sm.text).toBe("SELL 22600.5");
  });

  it("formats trailing zeros off the price label", () => {
    const sm = markerToSeriesMarker(marker({ side: "LONG_ENTRY", price: 100 }));
    expect(sm.text).toBe("BUY 100");
  });

  it("preserves significant decimals in the price label", () => {
    const sm = markerToSeriesMarker(marker({ side: "LONG_ENTRY", price: 1234.56 }));
    expect(sm.text).toBe("BUY 1234.56");
  });
});

describe("markerToSeriesMarker — long exits", () => {
  const longExit = (reason: MarkerExitReason | null): Marker =>
    marker({ side: "LONG_EXIT", exitReason: reason, price: 22550 });

  it("LONG_EXIT + TAKE_PROFIT → circle aboveBar, green, TP text", () => {
    const sm = markerToSeriesMarker(longExit("TAKE_PROFIT"));
    expect(sm.shape).toBe("circle");
    expect(sm.position).toBe("aboveBar");
    expect(sm.color).toBe(MARKER_COLORS.green);
    expect(sm.text).toBe("TP 22550");
  });

  it("LONG_EXIT + STOP_LOSS → arrowDown aboveBar, red, SL text", () => {
    const sm = markerToSeriesMarker(longExit("STOP_LOSS"));
    expect(sm.shape).toBe("arrowDown");
    expect(sm.color).toBe(MARKER_COLORS.red);
    expect(sm.text).toBe("SL 22550");
  });

  it("LONG_EXIT + SIGNAL → square aboveBar, gray, EXIT text", () => {
    const sm = markerToSeriesMarker(longExit("SIGNAL"));
    expect(sm.shape).toBe("square");
    expect(sm.color).toBe(MARKER_COLORS.gray);
    expect(sm.text).toBe("EXIT 22550");
  });

  it("LONG_EXIT + MANUAL → gray EXIT", () => {
    const sm = markerToSeriesMarker(longExit("MANUAL"));
    expect(sm.color).toBe(MARKER_COLORS.gray);
    expect(sm.text).toBe("EXIT 22550");
  });

  it("LONG_EXIT + SQUARE_OFF → gray SQOFF text", () => {
    const sm = markerToSeriesMarker(longExit("SQUARE_OFF"));
    expect(sm.color).toBe(MARKER_COLORS.gray);
    expect(sm.text).toBe("SQOFF 22550");
  });

  it("LONG_EXIT + EXPIRY → gray EXPIRY text", () => {
    const sm = markerToSeriesMarker(longExit("EXPIRY"));
    expect(sm.color).toBe(MARKER_COLORS.gray);
    expect(sm.text).toBe("EXPIRY 22550");
  });

  it("LONG_EXIT + null reason → gray EXIT text", () => {
    const sm = markerToSeriesMarker(longExit(null));
    expect(sm.color).toBe(MARKER_COLORS.gray);
    expect(sm.text).toBe("EXIT 22550");
  });
});

describe("markerToSeriesMarker — short exits", () => {
  const shortExit = (reason: MarkerExitReason | null): Marker =>
    marker({ side: "SHORT_EXIT", exitReason: reason, price: 22450 });

  it("SHORT_EXIT + TAKE_PROFIT → circle belowBar, blue (distinct from long entry green)", () => {
    const sm = markerToSeriesMarker(shortExit("TAKE_PROFIT"));
    expect(sm.shape).toBe("circle");
    expect(sm.position).toBe("belowBar");
    expect(sm.color).toBe(MARKER_COLORS.blue);
    expect(sm.text).toBe("TP 22450");
  });

  it("SHORT_EXIT + STOP_LOSS → arrowUp (price moved against the short) belowBar, red", () => {
    const sm = markerToSeriesMarker(shortExit("STOP_LOSS"));
    expect(sm.shape).toBe("arrowUp");
    expect(sm.position).toBe("belowBar");
    expect(sm.color).toBe(MARKER_COLORS.red);
    expect(sm.text).toBe("SL 22450");
  });

  it("SHORT_EXIT + SIGNAL → square belowBar, gray", () => {
    const sm = markerToSeriesMarker(shortExit("SIGNAL"));
    expect(sm.shape).toBe("square");
    expect(sm.position).toBe("belowBar");
    expect(sm.color).toBe(MARKER_COLORS.gray);
  });

  it("SHORT_EXIT + MANUAL → gray EXIT", () => {
    const sm = markerToSeriesMarker(shortExit("MANUAL"));
    expect(sm.color).toBe(MARKER_COLORS.gray);
    expect(sm.text).toBe("EXIT 22450");
  });

  it("SHORT_EXIT + SQUARE_OFF → gray SQOFF", () => {
    const sm = markerToSeriesMarker(shortExit("SQUARE_OFF"));
    expect(sm.text).toBe("SQOFF 22450");
  });

  it("SHORT_EXIT + EXPIRY → gray EXPIRY", () => {
    const sm = markerToSeriesMarker(shortExit("EXPIRY"));
    expect(sm.text).toBe("EXPIRY 22450");
  });
});

describe("markerToSeriesMarker — highlight", () => {
  it("default size is 1", () => {
    const sm = markerToSeriesMarker(marker());
    expect(sm.size).toBe(1);
  });

  it("highlighted=true bumps size to 2", () => {
    const sm = markerToSeriesMarker(marker(), { highlighted: true });
    expect(sm.size).toBe(2);
  });

  it("highlighted=false collapses back to 1", () => {
    const sm = markerToSeriesMarker(marker(), { highlighted: false });
    expect(sm.size).toBe(1);
  });

  it("uses backend marker.id as SeriesMarker.id (stable UUID handshake)", () => {
    const sm = markerToSeriesMarker(marker({ id: "uuid-abc-123" }));
    expect(sm.id).toBe("uuid-abc-123");
  });
});

describe("markersToSeriesMarkers — bulk helper", () => {
  it("sorts ascending by time even when input is out-of-order", () => {
    const out = markersToSeriesMarkers([
      marker({ id: "later", time: 1715679600 }),
      marker({ id: "earlier", time: 1715679000 }),
      marker({ id: "middle", time: 1715679300 }),
    ]);
    expect(out.map((m) => m.id)).toEqual(["earlier", "middle", "later"]);
  });

  it("returns empty array on empty input", () => {
    expect(markersToSeriesMarkers([])).toEqual([]);
  });

  it("highlight target gets size=2, others stay at size=1", () => {
    const out = markersToSeriesMarkers(
      [
        marker({ id: "a", time: 1 }),
        marker({ id: "b", time: 2 }),
        marker({ id: "c", time: 3 }),
      ],
      { highlightedId: "b" },
    );
    expect(out.find((m) => m.id === "a")?.size).toBe(1);
    expect(out.find((m) => m.id === "b")?.size).toBe(2);
    expect(out.find((m) => m.id === "c")?.size).toBe(1);
  });

  it("null highlight target leaves every marker at size=1", () => {
    const out = markersToSeriesMarkers(
      [marker({ id: "a", time: 1 }), marker({ id: "b", time: 2 })],
      { highlightedId: null },
    );
    expect(out.every((m) => m.size === 1)).toBe(true);
  });

  it("does not mutate the input array", () => {
    const input = [
      marker({ id: "later", time: 1715679600 }),
      marker({ id: "earlier", time: 1715679000 }),
    ];
    markersToSeriesMarkers(input);
    expect(input.map((m) => m.id)).toEqual(["later", "earlier"]);
  });
});
