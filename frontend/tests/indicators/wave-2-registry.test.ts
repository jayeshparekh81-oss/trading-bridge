import { describe, expect, it } from "vitest";

import {
  INDICATORS,
  INDICATOR_COUNT,
  getIndicator,
} from "@/lib/indicators/registry";

/**
 * Wave 2 indicators (slugs 31-50). These were added on top of Wave 1
 * (which already has its own `registry.test.ts` canonical-slugs test).
 * This file asserts the Wave 2 entries are present + well-formed,
 * without touching the Wave 1 tests.
 */

const WAVE_2_SLUGS = [
  "dmi-plus",
  "dmi-minus",
  "kama",
  "tema",
  "dema",
  "zlema",
  "hma",
  "alma",
  "linear-regression",
  "choppiness-index",
  "fisher-transform",
  "awesome-oscillator",
  "ultimate-oscillator",
  "balance-of-power",
  "force-index",
  "eom",
  "negative-volume-index",
  "positive-volume-index",
  "chande-momentum-oscillator",
  "trix",
] as const;

describe("Wave 2 indicators registered", () => {
  it("registry contains at least 50 indicators after Wave 2", () => {
    expect(INDICATOR_COUNT).toBeGreaterThanOrEqual(50);
    expect(Object.keys(INDICATORS).length).toBe(INDICATOR_COUNT);
  });

  it("every Wave 2 slug is present in the registry", () => {
    const missing = WAVE_2_SLUGS.filter((s) => getIndicator(s) === null);
    expect(missing, `Wave 2 missing slugs: ${missing.join(", ")}`).toEqual([]);
  });

  it("Wave 2 list has 20 entries", () => {
    expect(WAVE_2_SLUGS.length).toBe(20);
  });

  describe.each(WAVE_2_SLUGS)("indicator %s", (slug) => {
    const ind = getIndicator(slug);

    it("has both languages populated", () => {
      expect(ind).not.toBeNull();
      if (!ind) return;
      expect(ind.one_liner_en.trim().length).toBeGreaterThan(0);
      expect(ind.one_liner_hi.trim().length).toBeGreaterThan(0);
      expect(ind.description_en.trim().length).toBeGreaterThan(0);
      expect(ind.description_hi.trim().length).toBeGreaterThan(0);
    });

    it("has indian_context populated", () => {
      if (!ind) return;
      expect(ind.indian_context.trim().length).toBeGreaterThan(20);
    });

    it("has at least one use case, signal, and pitfall", () => {
      if (!ind) return;
      expect(ind.use_cases.length).toBeGreaterThan(0);
      expect(ind.common_signals.length).toBeGreaterThan(0);
      expect(ind.pitfalls.length).toBeGreaterThan(0);
    });

    it("hi one-liner uses Hinglish (heuristic — has ASCII)", () => {
      if (!ind) return;
      expect(/[a-zA-Z0-9]/.test(ind.one_liner_hi)).toBe(true);
    });
  });
});
