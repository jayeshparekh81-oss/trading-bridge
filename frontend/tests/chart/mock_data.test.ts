import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createMockWsServer,
  generateCandles,
  getMockHistory,
  getMockOlderHistory,
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

  it("(C11) anchors the series to the current timeframe bucket — last candle is within one bucket of 'now'", () => {
    const tfSeconds = 300; // 5m
    const before = Math.floor(Date.now() / 1000);
    const resp = getMockHistory({ symbol: "NIFTY", timeframe: "5m" });
    const after = Math.floor(Date.now() / 1000);

    const lastEpoch = Math.floor(
      new Date(resp.candles[resp.candles.length - 1].timestamp).getTime() /
        1000,
    );
    const beforeBucket = before - (before % tfSeconds);
    const afterBucket = after - (after % tfSeconds);

    // Last candle must align with one of the bucket boundaries the
    // test window straddles (most often the same bucket; occasionally
    // the next one if Date.now() crossed during the call).
    expect([beforeBucket, afterBucket]).toContain(lastEpoch);
  });

  it("(C11) candles are evenly spaced by the timeframe — no holes in the series", () => {
    const resp = getMockHistory({
      symbol: "NIFTY",
      timeframe: "5m",
      length: 50,
    });
    const epochs = resp.candles.map((c) =>
      Math.floor(new Date(c.timestamp).getTime() / 1000),
    );
    for (let i = 1; i < epochs.length; i++) {
      expect(epochs[i] - epochs[i - 1]).toBe(300);
    }
  });

  it("(C11/Phase1) the first mock WS candle is the SAME real-time bucket as history's last candle — intra-bar tick, not a future-dated bar", () => {
    // Phase-1 regression fix: prior to this, ``createMockWsServer``
    // emitted at ``currentBucket + tfSeconds`` and advanced by
    // ``tfSeconds`` per real-time tick. With a 5s tick interval and
    // a 5m timeframe, that meant the chart accumulated +5min of
    // "future" candles every 5s of viewing — Lightweight Charts'
    // auto-pan-to-tail then silently pushed the 200-candle
    // historical preload off-screen on narrow viewports. Fix: the
    // server now emits for the CURRENT real-time bucket. First emit
    // → same timestamp as history's last candle → upsert reducer
    // replaces tail (intra-bar). When wall-clock crosses the next
    // bucket boundary, the timestamp naturally advances and the
    // reducer appends a new bar.
    vi.useFakeTimers();
    try {
      // Pin Date.now() to a deterministic moment well inside a 5m
      // bucket (09:32 UTC = bucket 09:30:00..09:34:59).
      vi.setSystemTime(Date.UTC(2026, 4, 12, 9, 32, 0));

      const resp = getMockHistory({ symbol: "NIFTY", timeframe: "5m" });
      const historyLastEpoch = Math.floor(
        new Date(
          resp.candles[resp.candles.length - 1].timestamp,
        ).getTime() / 1000,
      );

      const received: ChartEnvelope[] = [];
      const server = createMockWsServer({
        symbol: "NIFTY",
        timeframe: "5m",
        tickIntervalMs: 1_000,
      });
      server.onMessage((env) => received.push(env));
      server.start();
      // Advance < tfSeconds (300s) so all emits stay inside the
      // same real-time bucket.
      vi.advanceTimersByTime(3_000);
      server.stop();

      expect(received.length).toBeGreaterThan(0);
      for (const env of received) {
        expect(env.event).toBe("candle");
        if (env.event === "candle") {
          const epoch = Math.floor(
            new Date(env.data.timestamp).getTime() / 1000,
          );
          // Every emit inside one real-time bucket must reuse the
          // same timestamp as history's last candle — intra-bar.
          expect(epoch).toBe(historyLastEpoch);
        }
      }
    } finally {
      vi.useRealTimers();
    }
  });

  it("(Phase1) crossing the wall-clock bucket boundary advances the emit timestamp by exactly one tfSeconds", () => {
    // Companion to the intra-bar test: after real time crosses the
    // next bucket boundary, the emit's timestamp must advance by
    // exactly tfSeconds (no skipped buckets, no double-jumps).
    vi.useFakeTimers();
    try {
      vi.setSystemTime(Date.UTC(2026, 4, 12, 9, 32, 0));
      const tfSeconds = 300;

      const received: ChartEnvelope[] = [];
      const server = createMockWsServer({
        symbol: "NIFTY",
        timeframe: "5m",
        tickIntervalMs: 1_000,
      });
      server.onMessage((env) => received.push(env));
      server.start();
      vi.advanceTimersByTime(1_000); // first emit (bucket A)
      const firstCandle = received[0];
      expect(firstCandle.event).toBe("candle");
      const firstEpoch =
        firstCandle.event === "candle"
          ? Math.floor(
              new Date(firstCandle.data.timestamp).getTime() / 1000,
            )
          : 0;

      // Jump real time forward by one full bucket + a small slice.
      vi.advanceTimersByTime(tfSeconds * 1_000);
      const after = received[received.length - 1];
      const afterEpoch =
        after.event === "candle"
          ? Math.floor(new Date(after.data.timestamp).getTime() / 1000)
          : 0;
      expect(afterEpoch - firstEpoch).toBe(tfSeconds);
      server.stop();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("getMockOlderHistory — Phase 5 scroll-back", () => {
  it("returns the requested length of bars", () => {
    const resp = getMockOlderHistory({
      symbol: "NIFTY",
      timeframe: "5m",
      beforeEpochSeconds: 1_800_000_000,
      length: 50,
    });
    expect(resp.candles).toHaveLength(50);
  });

  it("the LAST returned candle is exactly one tfSeconds before beforeEpochSeconds (contiguous prepend)", () => {
    const tfSeconds = 300;
    const before = 1_800_000_000;
    const resp = getMockOlderHistory({
      symbol: "NIFTY",
      timeframe: "5m",
      beforeEpochSeconds: before,
    });
    const last = resp.candles[resp.candles.length - 1];
    const lastEpoch = Math.floor(new Date(last.timestamp).getTime() / 1000);
    expect(before - lastEpoch).toBe(tfSeconds);
  });

  it("candles are evenly spaced by tfSeconds", () => {
    const resp = getMockOlderHistory({
      symbol: "NIFTY",
      timeframe: "5m",
      beforeEpochSeconds: 1_800_000_000,
      length: 20,
    });
    const epochs = resp.candles.map((c) =>
      Math.floor(new Date(c.timestamp).getTime() / 1000),
    );
    for (let i = 1; i < epochs.length; i++) {
      expect(epochs[i] - epochs[i - 1]).toBe(300);
    }
  });

  it("two consecutive scroll-back fetches stitch end-to-end with no gap or overlap", () => {
    const tfSeconds = 300;
    const before1 = 1_800_000_000;
    const resp1 = getMockOlderHistory({
      symbol: "NIFTY",
      timeframe: "5m",
      beforeEpochSeconds: before1,
      length: 50,
    });
    const earliest1 = Math.floor(
      new Date(resp1.candles[0].timestamp).getTime() / 1000,
    );

    const resp2 = getMockOlderHistory({
      symbol: "NIFTY",
      timeframe: "5m",
      beforeEpochSeconds: earliest1,
      length: 50,
    });
    const last2 = Math.floor(
      new Date(resp2.candles[resp2.candles.length - 1].timestamp).getTime() /
        1000,
    );
    expect(earliest1 - last2).toBe(tfSeconds);
  });

  it("is deterministic for a fixed beforeEpochSeconds (stable seed derivation)", () => {
    const a = getMockOlderHistory({
      symbol: "NIFTY",
      timeframe: "5m",
      beforeEpochSeconds: 1_800_000_000,
      length: 5,
    });
    const b = getMockOlderHistory({
      symbol: "NIFTY",
      timeframe: "5m",
      beforeEpochSeconds: 1_800_000_000,
      length: 5,
    });
    expect(a.candles).toEqual(b.candles);
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
