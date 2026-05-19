import { describe, it, expect } from "vitest";
import { INDICATORS, getIndicator } from "@/lib/indicators/registry";
import type { IndicatorContent } from "@/lib/indicators/registry";

const WAVE_3_SLUGS = [
  "mass-index",
  "coppock-curve",
  "detrended-price-oscillator",
  "price-oscillator",
  "accelerator-oscillator",
  "williams-vix-fix",
  "relative-vigor-index",
  "demarker",
  "accumulation-distribution",
  "price-volume-trend",
  "klinger-oscillator",
  "elder-ray-bull-bear",
  "schaff-trend-cycle",
  "random-walk-index",
  "linear-regression-channel",
  "standard-error-channel",
  "mcginley-dynamic",
  "swing-index",
  "accumulative-swing-index",
  "comparative-relative-strength",
];

// Hinglish heuristic: at least one of these Devanagari-free Hindi
// markers should appear, meaning the HI text is in Roman script.
const HINGLISH_MARKERS = [
  /\bhai\b/i,
  /\bnahi\b/i,
  /\bka\b/i,
  /\bki\b/i,
  /\bse\b/i,
  /\bmein\b/i,
  /\bkar\b/i,
  /\bho\b/i,
];

const isHinglish = (s: string): boolean => HINGLISH_MARKERS.some((r) => r.test(s));
const hasDevanagari = (s: string): boolean => /[ऀ-ॿ]/.test(s);

const assertShape = (slug: string, ind: IndicatorContent) => {
  expect(ind.slug, `${slug}: slug match`).toBe(slug);
  expect(ind.name.length, `${slug}: name`).toBeGreaterThan(3);
  expect(["momentum", "trend", "volatility", "volume", "rate", "pattern", "advanced"]).toContain(
    ind.category,
  );
  expect(["beginner", "intermediate", "advanced"]).toContain(ind.complexity);

  expect(ind.one_liner_en.length, `${slug}: one_liner_en`).toBeGreaterThan(40);
  expect(ind.one_liner_hi.length, `${slug}: one_liner_hi`).toBeGreaterThan(40);
  expect(ind.description_en.length, `${slug}: description_en`).toBeGreaterThan(500);
  expect(ind.description_hi.length, `${slug}: description_hi`).toBeGreaterThan(500);
  expect(ind.formula_explanation.length, `${slug}: formula`).toBeGreaterThan(80);

  expect(ind.use_cases.length, `${slug}: ≥2 use cases`).toBeGreaterThanOrEqual(2);
  expect(ind.common_signals.length, `${slug}: ≥2 signals`).toBeGreaterThanOrEqual(2);
  expect(ind.pitfalls.length, `${slug}: ≥3 pitfalls`).toBeGreaterThanOrEqual(3);
  expect(ind.indian_context.length, `${slug}: indian_context`).toBeGreaterThan(150);

  // Bilingual content checks
  expect(hasDevanagari(ind.description_hi), `${slug}: description_hi must NOT have Devanagari`).toBe(false);
  expect(hasDevanagari(ind.one_liner_hi), `${slug}: one_liner_hi must NOT have Devanagari`).toBe(false);
  expect(isHinglish(ind.description_hi), `${slug}: description_hi must read as Hinglish`).toBe(true);

  // Three-paragraph structure check
  const paragraphs = ind.description_en.split("\n\n").filter((p) => p.trim().length > 0);
  expect(paragraphs.length, `${slug}: description_en should have ≥3 paragraphs`).toBeGreaterThanOrEqual(3);
};

describe("Wave 3 indicators (slugs 51-70)", () => {
  it("all 20 wave-3 indicators are registered", () => {
    for (const slug of WAVE_3_SLUGS) {
      expect(getIndicator(slug), `slug ${slug} should be registered`).not.toBeNull();
    }
  });

  it("registry contains at least 50 indicators total (30 Phase 1 + 20 Wave 3)", () => {
    expect(Object.keys(INDICATORS).length).toBeGreaterThanOrEqual(50);
  });

  it("every wave-3 indicator has well-formed content", () => {
    for (const slug of WAVE_3_SLUGS) {
      const ind = getIndicator(slug);
      expect(ind, `${slug} must exist`).not.toBeNull();
      if (ind) assertShape(slug, ind);
    }
  });

  it("every wave-3 indicator declares works_well_with that exist OR are reserved for future waves", () => {
    // Allow references to indicators that may not exist yet (Wave 2 not merged
    // to this base). Just check that referenced slugs are well-formed strings.
    for (const slug of WAVE_3_SLUGS) {
      const ind = getIndicator(slug)!;
      for (const ref of ind.works_well_with) {
        expect(ref, `${slug}.works_well_with[${ref}] should be kebab-case`).toMatch(/^[a-z][a-z0-9-]*$/);
      }
      for (const ref of ind.works_poorly_with) {
        expect(ref, `${slug}.works_poorly_with[${ref}] should be kebab-case`).toMatch(/^[a-z][a-z0-9-]*$/);
      }
    }
  });
});
