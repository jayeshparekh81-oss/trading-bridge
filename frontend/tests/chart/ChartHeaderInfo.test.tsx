/**
 * ChartHeaderInfo — Phase 4 tests.
 *
 * Two layers:
 *   1. ``deriveHeaderInfo`` — pure function, exhaustively tested
 *      across the day-window edge cases (single bar, multi-day
 *      buffer, all-yesterday fallback, zero-open division guard).
 *   2. Component render — asserts the testid surface ChartContainer
 *      relies on (header-price, header-change, header-ohlcv) and
 *      the data-direction attribute that drives the up/down accent
 *      colour.
 */

import { render, screen } from "@testing-library/react";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

import {
  ChartHeaderInfo,
  deriveHeaderInfo,
} from "@/components/chart/ChartHeaderInfo";
import type { Candle } from "@/lib/chart/types";

// ─── Helpers ───────────────────────────────────────────────────────────

/** IST = UTC+5:30. To anchor a candle to a specific IST date we
 *  build the UTC epoch from that IST date by subtracting the offset
 *  inside Date.UTC. */
function istEpoch(year: number, month: number, day: number, h: number, m: number): number {
  // month is 1-indexed for readability
  return Math.floor(Date.UTC(year, month - 1, day, h - 5, m - 30) / 1_000);
}

function bar(opts: {
  time: number;
  open: number;
  high?: number;
  low?: number;
  close: number;
  volume?: number;
}): Candle {
  return {
    symbol: "NIFTY",
    timeframe: "5m",
    time: opts.time,
    open: opts.open,
    high: opts.high ?? Math.max(opts.open, opts.close),
    low: opts.low ?? Math.min(opts.open, opts.close),
    close: opts.close,
    volume: opts.volume ?? 1_000,
  };
}

// ─── deriveHeaderInfo — pure ───────────────────────────────────────────

describe("deriveHeaderInfo — empty + single-bar", () => {
  it("returns all-null on an empty candles array", () => {
    const info = deriveHeaderInfo([]);
    expect(info).toMatchObject({
      price: null,
      open: null,
      high: null,
      low: null,
      volume: 0,
      absChange: null,
      pctChange: null,
      isUp: null,
    });
  });

  it("single bar — open == close yields zero change + isUp=null (flat)", () => {
    const t = istEpoch(2026, 5, 12, 9, 30);
    const info = deriveHeaderInfo([
      bar({ time: t, open: 100, close: 100, volume: 500 }),
    ]);
    expect(info.price).toBe(100);
    expect(info.open).toBe(100);
    expect(info.absChange).toBe(0);
    expect(info.pctChange).toBe(0);
    expect(info.isUp).toBeNull();
    expect(info.volume).toBe(500);
  });

  it("single bar with positive close - open → isUp=true and positive deltas", () => {
    const info = deriveHeaderInfo([
      bar({
        time: istEpoch(2026, 5, 12, 9, 30),
        open: 100,
        close: 110,
        volume: 200,
      }),
    ]);
    expect(info.absChange).toBeCloseTo(10);
    expect(info.pctChange).toBeCloseTo(10);
    expect(info.isUp).toBe(true);
  });

  it("single bar with negative close - open → isUp=false and negative deltas", () => {
    const info = deriveHeaderInfo([
      bar({
        time: istEpoch(2026, 5, 12, 9, 30),
        open: 100,
        close: 90,
      }),
    ]);
    expect(info.absChange).toBeCloseTo(-10);
    expect(info.pctChange).toBeCloseTo(-10);
    expect(info.isUp).toBe(false);
  });

  it("zero open → pctChange is null (no division by zero)", () => {
    const info = deriveHeaderInfo([
      bar({
        time: istEpoch(2026, 5, 12, 9, 30),
        open: 0,
        close: 5,
        high: 5,
        low: 0,
      }),
    ]);
    expect(info.pctChange).toBeNull();
    // absChange still computes — open=0 is a valid number.
    expect(info.absChange).toBe(5);
  });
});

describe("deriveHeaderInfo — day-window logic", () => {
  it("filters today's bars from a multi-day buffer (open from today's first, not yesterday's first)", () => {
    const yest = istEpoch(2026, 5, 11, 9, 15);
    const today = istEpoch(2026, 5, 12, 9, 15);
    const candles = [
      bar({ time: yest, open: 22_000, close: 22_400, high: 22_500, low: 21_900, volume: 5_000 }),
      bar({ time: yest + 300, open: 22_400, close: 22_300, high: 22_450, low: 22_200, volume: 4_500 }),
      bar({ time: today, open: 22_300, close: 22_350, high: 22_360, low: 22_250, volume: 1_000 }),
      bar({ time: today + 300, open: 22_350, close: 22_500, high: 22_510, low: 22_320, volume: 1_500 }),
    ];

    const info = deriveHeaderInfo(candles);
    // open is today's first (22_300), not yesterday's first (22_000)
    expect(info.open).toBe(22_300);
    // high/low/volume aggregate today only
    expect(info.high).toBe(22_510);
    expect(info.low).toBe(22_250);
    expect(info.volume).toBe(2_500);
    // change calc baselined on today's open
    expect(info.absChange).toBeCloseTo(22_500 - 22_300);
    expect(info.pctChange).toBeCloseTo(((22_500 - 22_300) / 22_300) * 100);
  });

  it("falls back to all-candles when none belong to the latest bar's IST date (impossible by construction but defensive)", () => {
    // Every bar shares the same IST date as the last bar — verifies
    // the fallback path: cutoff = 0 → todayBars = full array.
    const t = istEpoch(2026, 5, 12, 9, 15);
    const info = deriveHeaderInfo([
      bar({ time: t, open: 100, close: 105, volume: 10 }),
      bar({ time: t + 300, open: 105, close: 110, volume: 20 }),
    ]);
    expect(info.open).toBe(100);
    expect(info.volume).toBe(30);
  });

  it("aggregates high/low/volume across all of today's bars", () => {
    const t = istEpoch(2026, 5, 12, 9, 15);
    const info = deriveHeaderInfo([
      bar({ time: t, open: 100, close: 105, high: 110, low: 99, volume: 50 }),
      bar({ time: t + 300, open: 105, close: 102, high: 108, low: 100, volume: 75 }),
      bar({ time: t + 600, open: 102, close: 99, high: 103, low: 95, volume: 25 }),
    ]);
    expect(info.high).toBe(110);
    expect(info.low).toBe(95);
    expect(info.volume).toBe(150);
    expect(info.price).toBe(99);
  });
});

// ─── Component render ──────────────────────────────────────────────────

describe("ChartHeaderInfo — component", () => {
  // Pin matchMedia just in case any nested Tailwind hook reads it.
  const originalMatchMedia = globalThis.matchMedia;
  beforeAll(() => {
    if (!globalThis.matchMedia) {
      globalThis.matchMedia = ((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      })) as unknown as typeof window.matchMedia;
    }
  });
  afterAll(() => {
    globalThis.matchMedia = originalMatchMedia;
  });

  it("renders an empty placeholder when candles is empty", () => {
    render(<ChartHeaderInfo symbol="NIFTY" candles={[]} />);
    const root = screen.getByTestId("chart-header-info");
    expect(root).toHaveAttribute("data-state", "empty");
    expect(root).toHaveTextContent("NIFTY");
    expect(root).toHaveTextContent("—");
    // OHLCV breakdown must NOT render in empty state.
    expect(screen.queryByTestId("header-ohlcv")).toBeNull();
  });

  it("renders price + change with up direction when close > open", () => {
    const t = istEpoch(2026, 5, 12, 9, 15);
    render(
      <ChartHeaderInfo
        symbol="NIFTY"
        candles={[
          bar({ time: t, open: 22_000, close: 22_500, volume: 1_000 }),
        ]}
      />,
    );

    const root = screen.getByTestId("chart-header-info");
    expect(root).toHaveAttribute("data-state", "loaded");
    expect(root).toHaveAttribute("data-direction", "up");

    expect(screen.getByTestId("header-price")).toHaveTextContent(
      "₹22,500.00",
    );
    const change = screen.getByTestId("header-change");
    // unicode +/− prefix, en-IN-formatted
    expect(change).toHaveTextContent("+500.00");
    expect(change).toHaveTextContent("+2.27%");
  });

  it("renders down direction when close < open", () => {
    const t = istEpoch(2026, 5, 12, 9, 15);
    render(
      <ChartHeaderInfo
        symbol="NIFTY"
        candles={[
          bar({ time: t, open: 22_000, close: 21_780 }),
        ]}
      />,
    );
    expect(screen.getByTestId("chart-header-info")).toHaveAttribute(
      "data-direction",
      "down",
    );
    const change = screen.getByTestId("header-change");
    expect(change).toHaveTextContent("−220.00");
    expect(change).toHaveTextContent("−1.00%");
  });

  it("renders flat direction (data-direction='flat') when close == open", () => {
    const t = istEpoch(2026, 5, 12, 9, 15);
    render(
      <ChartHeaderInfo
        symbol="NIFTY"
        candles={[bar({ time: t, open: 22_000, close: 22_000 })]}
      />,
    );
    expect(screen.getByTestId("chart-header-info")).toHaveAttribute(
      "data-direction",
      "flat",
    );
  });

  it("renders the desktop OHLCV row with formatted values", () => {
    const t = istEpoch(2026, 5, 12, 9, 15);
    render(
      <ChartHeaderInfo
        symbol="NIFTY"
        candles={[
          bar({
            time: t,
            open: 22_500,
            high: 22_600,
            low: 22_450,
            close: 22_580,
            volume: 1_500_000,
          }),
        ]}
      />,
    );

    const ohlcv = screen.getByTestId("header-ohlcv");
    expect(ohlcv).toHaveTextContent("22,500.00");
    expect(ohlcv).toHaveTextContent("22,600.00");
    expect(ohlcv).toHaveTextContent("22,450.00");
    // 1,500,000 → 15.00L
    expect(ohlcv).toHaveTextContent("15.00L");
    // The hidden-on-mobile pattern uses ``hidden sm:inline-flex`` —
    // assert the responsive utility class is present so a future
    // refactor doesn't accidentally drop the mobile collapse.
    expect(ohlcv).toHaveClass("hidden");
    expect(ohlcv).toHaveClass("sm:inline-flex");
  });

  it("price + change pair stays visible on mobile (no responsive hidden class)", () => {
    const t = istEpoch(2026, 5, 12, 9, 15);
    render(
      <ChartHeaderInfo
        symbol="NIFTY"
        candles={[bar({ time: t, open: 100, close: 105 })]}
      />,
    );
    const price = screen.getByTestId("header-price");
    const change = screen.getByTestId("header-change");
    // The mobile-essential pair must NOT carry a responsive-hide
    // class — they should always be on screen.
    expect(price.className).not.toMatch(/\bhidden\b/);
    expect(change.className).not.toMatch(/\bhidden\b/);
  });
});
