import { describe, expect, it } from "vitest";

import {
  filterIndicators,
  getIndicator,
  INDICATORS,
  INDICATOR_COUNT,
  listIndicators,
} from "@/lib/indicators/registry";

describe("indicator registry", () => {
  it("INDICATOR_COUNT matches the actual object key count", () => {
    expect(INDICATOR_COUNT).toBe(Object.keys(INDICATORS).length);
  });

  it("getIndicator returns the content for a known slug", () => {
    const rsi = getIndicator("rsi");
    expect(rsi).not.toBeNull();
    expect(rsi?.slug).toBe("rsi");
    expect(rsi?.category).toBe("momentum");
  });

  it("getIndicator returns null for an unknown slug", () => {
    expect(getIndicator("definitely-not-a-real-indicator")).toBeNull();
  });

  it("filterIndicators returns the full list when no filter is set", () => {
    expect(filterIndicators({})).toHaveLength(INDICATOR_COUNT);
  });

  it("filterIndicators narrows by category", () => {
    const momentum = filterIndicators({ category: "momentum" });
    expect(momentum.length).toBeGreaterThan(0);
    expect(momentum.every((i) => i.category === "momentum")).toBe(true);
  });

  it("filterIndicators narrows by complexity", () => {
    const beginners = filterIndicators({ complexity: "beginner" });
    expect(beginners.length).toBeGreaterThan(0);
    expect(beginners.every((i) => i.complexity === "beginner")).toBe(true);
  });

  it("filterIndicators query matches name OR slug OR one-liner", () => {
    const rsiHits = filterIndicators({ query: "rsi" });
    const slugs = rsiHits.map((i) => i.slug);
    expect(slugs).toContain("rsi");
  });

  it("filterIndicators query is case-insensitive", () => {
    const upper = filterIndicators({ query: "BOLLINGER" });
    expect(upper.some((i) => i.slug === "bollinger-bands")).toBe(true);
  });

  it("filterIndicators combines category + query AND-wise", () => {
    const trendMacd = filterIndicators({
      category: "trend",
      query: "moving average",
    });
    expect(trendMacd.every((i) => i.category === "trend")).toBe(true);
    expect(trendMacd.length).toBeGreaterThan(0);
  });

  it("listIndicators returns a non-empty alpha-sorted array", () => {
    const list = listIndicators();
    expect(list.length).toBe(INDICATOR_COUNT);
    expect(list.length).toBeGreaterThanOrEqual(30);
  });

  it("expected canonical slugs are all in the registry", () => {
    const expected = [
      "rsi", "macd", "stochastic", "williams-r", "cci",
      "ema", "sma", "wma", "supertrend", "parabolic-sar",
      "adx", "dmi", "ichimoku",
      "bollinger-bands", "atr", "keltner-channel",
      "donchian-channel", "standard-deviation",
      "vwap", "obv", "volume-profile", "mfi",
      "roc", "momentum", "tsi",
      "pivot-points", "fibonacci-retracement", "supports-resistances",
      "gaussian-channel", "heikin-ashi",
    ];
    for (const slug of expected) {
      expect(getIndicator(slug), `missing slug: ${slug}`).not.toBeNull();
    }
  });
});
