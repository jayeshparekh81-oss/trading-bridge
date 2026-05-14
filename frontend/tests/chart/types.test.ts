import { describe, expect, it } from "vitest";

import {
  isBrokerDisconnectedEnvelope,
  isBrokerReconnectedEnvelope,
  isCandleEnvelope,
  isHeartbeatEnvelope,
  parseCandle,
  parseChartMarker,
  type WireCandle,
  type WireChartMarker,
} from "@/lib/chart/types";

describe("parseCandle", () => {
  const wire: WireCandle = {
    symbol: "NIFTY",
    timeframe: "5m",
    timestamp: "2026-01-15T03:45:00.000Z",
    open: "22500.5000",
    high: "22510.5000",
    low: "22498.2500",
    close: "22505.7500",
    volume: 250_000,
  };

  it("decimal-string OHLC parses to number", () => {
    const c = parseCandle(wire);
    expect(c.open).toBeCloseTo(22500.5, 4);
    expect(c.close).toBeCloseTo(22505.75, 4);
  });

  it("timestamp parses to epoch seconds", () => {
    expect(parseCandle(wire).time).toBe(
      Math.floor(Date.parse("2026-01-15T03:45:00.000Z") / 1000),
    );
  });

  it("preserves symbol and timeframe", () => {
    const c = parseCandle(wire);
    expect(c.symbol).toBe("NIFTY");
    expect(c.timeframe).toBe("5m");
    expect(c.volume).toBe(250_000);
  });
});

describe("envelope type guards", () => {
  it("isCandleEnvelope discriminates", () => {
    expect(
      isCandleEnvelope({
        event: "candle",
        data: {} as WireCandle,
      }),
    ).toBe(true);
    expect(
      isCandleEnvelope({
        event: "heartbeat",
        at: "2026-01-01T00:00:00Z",
      }),
    ).toBe(false);
  });

  it("isBrokerDisconnectedEnvelope discriminates", () => {
    expect(
      isBrokerDisconnectedEnvelope({
        event: "broker_disconnected",
        symbol: "X",
        reason: "r",
        failed_attempts: 1,
        since: "2026-01-01T00:00:00Z",
      }),
    ).toBe(true);
    expect(
      isBrokerDisconnectedEnvelope({
        event: "candle",
        data: {} as WireCandle,
      }),
    ).toBe(false);
  });

  it("isBrokerReconnectedEnvelope discriminates", () => {
    expect(
      isBrokerReconnectedEnvelope({
        event: "broker_reconnected",
        symbol: "X",
        at: "2026-01-01T00:00:00Z",
      }),
    ).toBe(true);
  });

  it("isHeartbeatEnvelope discriminates", () => {
    expect(
      isHeartbeatEnvelope({
        event: "heartbeat",
        at: "2026-01-01T00:00:00Z",
      }),
    ).toBe(true);
  });
});

describe("parseChartMarker (Phase 7)", () => {
  const wire: WireChartMarker = {
    kind: "TP_HIT",
    timestamp: "2026-05-12T05:30:00.000Z",
    price: "22580.7500",
    quantity: 50,
    side: "BUY",
    pnl: "4037.50",
    exit_reason: "target",
  };

  it("decimal-string price + pnl parse to number", () => {
    const m = parseChartMarker(wire);
    expect(m.price).toBeCloseTo(22580.75, 4);
    expect(m.pnl).toBeCloseTo(4037.5, 4);
  });

  it("timestamp parses to epoch SECONDS (matches Candle.time)", () => {
    expect(parseChartMarker(wire).time).toBe(
      Math.floor(Date.parse("2026-05-12T05:30:00.000Z") / 1000),
    );
  });

  it("preserves kind, quantity, side, exit_reason verbatim", () => {
    const m = parseChartMarker(wire);
    expect(m.kind).toBe("TP_HIT");
    expect(m.quantity).toBe(50);
    expect(m.side).toBe("BUY");
    expect(m.exit_reason).toBe("target");
  });

  it("null pnl + null exit_reason (entry markers) survive the parse", () => {
    const entry: WireChartMarker = {
      kind: "ENTRY",
      timestamp: "2026-05-12T05:30:00.000Z",
      price: "22500.00",
      quantity: 50,
      side: "BUY",
      pnl: null,
      exit_reason: null,
    };
    const m = parseChartMarker(entry);
    expect(m.pnl).toBeNull();
    expect(m.exit_reason).toBeNull();
    expect(m.kind).toBe("ENTRY");
  });
});
