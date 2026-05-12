/**
 * Indicators — pure compute tests.
 *
 * Numeric values are checked against hand-computed expectations on
 * tiny fixtures so a future refactor can't silently drift the math.
 */

import { describe, expect, it } from "vitest";

import {
  computeEMA,
  computeMACD,
  computeRSI,
  computeSMA,
} from "@/lib/chart/indicators";
import type { Candle } from "@/lib/chart/types";

function bar(time: number, close: number): Candle {
  return {
    symbol: "X",
    timeframe: "5m",
    time,
    open: close,
    high: close,
    low: close,
    close,
    volume: 0,
  };
}

describe("computeSMA", () => {
  it("throws on non-positive period", () => {
    expect(() => computeSMA([bar(1, 1)], 0)).toThrow(/period/);
    expect(() => computeSMA([bar(1, 1)], -3)).toThrow(/period/);
  });

  it("returns empty when candles.length < period", () => {
    expect(computeSMA([bar(1, 1), bar(2, 2)], 5)).toEqual([]);
  });

  it("hand-computed SMA(3) matches expectation on a 5-bar fixture", () => {
    const candles = [1, 2, 3, 4, 5].map((c, i) => bar(i, c));
    const out = computeSMA(candles, 3);
    expect(out).toEqual([
      { time: 2, value: 2 }, // (1+2+3)/3
      { time: 3, value: 3 }, // (2+3+4)/3
      { time: 4, value: 4 }, // (3+4+5)/3
    ]);
  });

  it("handles candles.length === period exactly", () => {
    const out = computeSMA([1, 2, 3].map((c, i) => bar(i, c)), 3);
    expect(out).toEqual([{ time: 2, value: 2 }]);
  });
});

describe("computeEMA", () => {
  it("throws on non-positive period", () => {
    expect(() => computeEMA([bar(1, 1)], 0)).toThrow(/period/);
  });

  it("returns empty when candles.length < period", () => {
    expect(computeEMA([bar(1, 1)], 3)).toEqual([]);
  });

  it("first emitted point equals the SMA seed (alignment with computeSMA)", () => {
    const candles = [10, 20, 30, 40, 50].map((c, i) => bar(i, c));
    const ema = computeEMA(candles, 3);
    const sma = computeSMA(candles, 3);
    expect(ema[0]).toEqual(sma[0]);
  });

  it("subsequent points apply alpha = 2/(N+1) recursively", () => {
    const candles = [10, 20, 30, 40].map((c, i) => bar(i, c));
    const out = computeEMA(candles, 3);
    // seed = (10+20+30)/3 = 20; alpha = 0.5
    // next = 40*0.5 + 20*0.5 = 30
    expect(out[1].value).toBeCloseTo(30, 6);
  });
});

describe("computeRSI", () => {
  it("throws on non-positive period", () => {
    expect(() => computeRSI([bar(1, 1)], 0)).toThrow(/period/);
  });

  it("returns empty when candles.length <= period", () => {
    expect(computeRSI([bar(1, 1), bar(2, 2)], 14)).toEqual([]);
  });

  it("strictly-rising series gives RSI near 100 (avgLoss = 0 → 100 by definition)", () => {
    const candles = Array.from({ length: 20 }, (_, i) =>
      bar(i, 100 + i),
    );
    const out = computeRSI(candles, 14);
    for (const p of out) expect(p.value).toBe(100);
  });

  it("strictly-falling series gives RSI near 0", () => {
    const candles = Array.from({ length: 20 }, (_, i) => bar(i, 100 - i));
    const out = computeRSI(candles, 14);
    for (const p of out) expect(p.value).toBe(0);
  });

  it("output starts at index === period (first window with N changes)", () => {
    const candles = Array.from({ length: 20 }, (_, i) =>
      bar(i, 100 + Math.sin(i)),
    );
    const out = computeRSI(candles, 14);
    expect(out[0].time).toBe(candles[14].time);
    expect(out[out.length - 1].time).toBe(candles[19].time);
  });
});

describe("computeMACD", () => {
  it("throws on bad params", () => {
    expect(() => computeMACD([bar(1, 1)], 0)).toThrow(/period/);
    expect(() => computeMACD([bar(1, 1)], 12, 5)).toThrow(/slow/);
  });

  it("returns empty when candles too short for slow + signal - 1", () => {
    expect(
      computeMACD(
        Array.from({ length: 10 }, (_, i) => bar(i, 100)),
      ),
    ).toEqual([]);
  });

  it("emits {time, macd, signal, histogram} per point on a long-enough series", () => {
    const candles = Array.from({ length: 50 }, (_, i) =>
      bar(i, 100 + Math.sin(i / 3) * 10),
    );
    const out = computeMACD(candles);
    expect(out.length).toBeGreaterThan(0);
    for (const p of out) {
      expect(typeof p.macd).toBe("number");
      expect(typeof p.signal).toBe("number");
      expect(typeof p.histogram).toBe("number");
      expect(p.histogram).toBeCloseTo(p.macd - p.signal, 6);
    }
  });

  it("flat-priced series produces all-zero MACD + zero histogram", () => {
    const candles = Array.from({ length: 50 }, (_, i) => bar(i, 100));
    const out = computeMACD(candles);
    for (const p of out) {
      expect(p.macd).toBeCloseTo(0, 6);
      expect(p.signal).toBeCloseTo(0, 6);
      expect(p.histogram).toBeCloseTo(0, 6);
    }
  });
});
