import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createMockWsServer,
  generateCandles,
  getMockHistory,
  isMockEnabled,
} from "@/lib/chart/mock_data";
import type { ChartEnvelope } from "@/lib/chart/types";

describe("generateCandles", () => {
  it("returns the requested length", () => {
    const out = generateCandles({
      symbol: "NIFTY",
      timeframe: "5m",
      length: 50,
    });
    expect(out).toHaveLength(50);
  });

  it("is deterministic for a fixed seed", () => {
    const a = generateCandles({ symbol: "NIFTY", timeframe: "5m", length: 5, seed: 7 });
    const b = generateCandles({ symbol: "NIFTY", timeframe: "5m", length: 5, seed: 7 });
    expect(a).toEqual(b);
  });

  it("uppercases the symbol", () => {
    const [first] = generateCandles({ symbol: "nifty", timeframe: "5m", length: 1 });
    expect(first.symbol).toBe("NIFTY");
  });

  it("satisfies OHLC invariant low ≤ open/close ≤ high", () => {
    const out = generateCandles({ symbol: "NIFTY", timeframe: "5m", length: 50 });
    for (const c of out) {
      const o = parseFloat(c.open);
      const h = parseFloat(c.high);
      const l = parseFloat(c.low);
      const cl = parseFloat(c.close);
      expect(l).toBeLessThanOrEqual(o);
      expect(l).toBeLessThanOrEqual(cl);
      expect(h).toBeGreaterThanOrEqual(o);
      expect(h).toBeGreaterThanOrEqual(cl);
    }
  });

  it("default options produce 200-bar default series", () => {
    const out = generateCandles({ symbol: "X", timeframe: "5m" });
    expect(out).toHaveLength(200);
  });
});

describe("getMockHistory", () => {
  it("wraps generateCandles in the wire-shape response", () => {
    const resp = getMockHistory({ symbol: "NIFTY", timeframe: "5m" });
    expect(resp.symbol).toBe("NIFTY");
    expect(resp.timeframe).toBe("5m");
    expect(resp.cached).toBe(false);
    expect(resp.candles).toHaveLength(200);
    expect(resp.from_ts).toBe(resp.candles[0].timestamp);
    expect(resp.to_ts).toBe(resp.candles[resp.candles.length - 1].timestamp);
  });

  it("respects explicit length override", () => {
    expect(
      getMockHistory({ symbol: "X", timeframe: "5m", length: 10 }).candles,
    ).toHaveLength(10);
  });
});

describe("isMockEnabled", () => {
  const original = process.env.NEXT_PUBLIC_USE_MOCK;
  afterEach(() => {
    process.env.NEXT_PUBLIC_USE_MOCK = original;
  });

  it("returns true when env var is exactly 'true'", () => {
    process.env.NEXT_PUBLIC_USE_MOCK = "true";
    expect(isMockEnabled()).toBe(true);
  });

  it("returns false when env var is absent or any other value", () => {
    delete process.env.NEXT_PUBLIC_USE_MOCK;
    expect(isMockEnabled()).toBe(false);
    process.env.NEXT_PUBLIC_USE_MOCK = "false";
    expect(isMockEnabled()).toBe(false);
    process.env.NEXT_PUBLIC_USE_MOCK = "1";
    expect(isMockEnabled()).toBe(false);
  });
});

describe("createMockWsServer", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("emits a candle envelope on every tickIntervalMs", () => {
    const received: ChartEnvelope[] = [];
    const server = createMockWsServer({
      symbol: "NIFTY",
      timeframe: "5m",
      tickIntervalMs: 1000,
    });
    server.onMessage((env) => received.push(env));
    server.start();
    vi.advanceTimersByTime(3500);
    expect(received).toHaveLength(3);
    for (const env of received) {
      expect(env.event).toBe("candle");
    }
    server.stop();
  });

  it("stop() halts further emissions", () => {
    const received: ChartEnvelope[] = [];
    const server = createMockWsServer({
      symbol: "NIFTY",
      timeframe: "5m",
      tickIntervalMs: 100,
    });
    server.onMessage((env) => received.push(env));
    server.start();
    vi.advanceTimersByTime(250);
    const before = received.length;
    server.stop();
    vi.advanceTimersByTime(500);
    expect(received.length).toBe(before);
  });

  it("start() is idempotent", () => {
    const received: ChartEnvelope[] = [];
    const server = createMockWsServer({
      symbol: "X",
      timeframe: "5m",
      tickIntervalMs: 100,
    });
    server.onMessage((env) => received.push(env));
    server.start();
    server.start(); // second call must not double the rate
    vi.advanceTimersByTime(350);
    expect(received).toHaveLength(3);
    server.stop();
  });

  it("emitDisconnected / emitReconnected push control envelopes", () => {
    const received: ChartEnvelope[] = [];
    const server = createMockWsServer({ symbol: "X", timeframe: "5m" });
    server.onMessage((env) => received.push(env));
    server.emitDisconnected("test");
    server.emitReconnected();
    expect(received.map((e) => e.event)).toEqual([
      "broker_disconnected",
      "broker_reconnected",
    ]);
  });

  it("control emits before onMessage handler are silent no-ops", () => {
    const server = createMockWsServer({ symbol: "X", timeframe: "5m" });
    // No handler registered — these must not throw.
    expect(() => server.emitDisconnected()).not.toThrow();
    expect(() => server.emitReconnected()).not.toThrow();
  });

  it("does not emit when handler is absent and start() fires", () => {
    const server = createMockWsServer({
      symbol: "X",
      timeframe: "5m",
      tickIntervalMs: 50,
    });
    server.start();
    vi.advanceTimersByTime(200);
    // No assertion needed — the test fails only if the interval
    // throws because handler is null.
    server.stop();
  });
});
