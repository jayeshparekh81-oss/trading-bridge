import { describe, expect, it } from "vitest";

import {
  INDICATORS,
  INDICATOR_COUNT,
  listIndicators,
  type IndicatorContent,
} from "@/lib/indicators/registry";

const REQUIRED_CATEGORIES: IndicatorContent["category"][] = [
  "momentum",
  "trend",
  "volatility",
  "volume",
  "rate",
  "pattern",
  "advanced",
];

describe("indicator content completeness", () => {
  it("registry exports at least 30 indicators", () => {
    expect(INDICATOR_COUNT).toBeGreaterThanOrEqual(30);
    expect(Object.keys(INDICATORS).length).toBe(INDICATOR_COUNT);
  });

  it("every indicator has both en + hi for one_liner, description, all required fields", () => {
    const offenders: string[] = [];
    for (const ind of Object.values(INDICATORS)) {
      const issues: string[] = [];
      if (!ind.slug?.trim()) issues.push("slug");
      if (!ind.name?.trim()) issues.push("name");
      if (!ind.one_liner_en?.trim()) issues.push("one_liner_en");
      if (!ind.one_liner_hi?.trim()) issues.push("one_liner_hi");
      if (!ind.description_en?.trim()) issues.push("description_en");
      if (!ind.description_hi?.trim()) issues.push("description_hi");
      if (!ind.formula_explanation?.trim()) issues.push("formula_explanation");
      if (!ind.indian_context?.trim()) issues.push("indian_context");
      if (ind.use_cases.length === 0) issues.push("use_cases");
      if (ind.common_signals.length === 0) issues.push("common_signals");
      if (ind.pitfalls.length === 0) issues.push("pitfalls");
      if (issues.length > 0) {
        offenders.push(`${ind.slug}: missing ${issues.join(", ")}`);
      }
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });

  it("every required category appears in at least one indicator", () => {
    const used = new Set(
      Object.values(INDICATORS).map((i) => i.category),
    );
    const missing = REQUIRED_CATEGORIES.filter((c) => !used.has(c));
    expect(missing).toEqual([]);
  });

  it("every slug in registry matches its content file's slug", () => {
    const mismatches: string[] = [];
    for (const [key, ind] of Object.entries(INDICATORS)) {
      if (key !== ind.slug) {
        mismatches.push(`registry key '${key}' vs content slug '${ind.slug}'`);
      }
    }
    expect(mismatches).toEqual([]);
  });

  it("all hi one-liners use Hinglish (no pure-Devanagari)", () => {
    const offenders = Object.values(INDICATORS).filter(
      (i) => !/[a-zA-Z0-9]/.test(i.one_liner_hi),
    );
    expect(
      offenders.map((i) => i.slug),
      "pure-Devanagari hi one_liners",
    ).toEqual([]);
  });

  it("all complexity values are within the allowed set", () => {
    const allowed = new Set(["beginner", "intermediate", "advanced"]);
    const bad = Object.values(INDICATORS).filter(
      (i) => !allowed.has(i.complexity),
    );
    expect(bad).toEqual([]);
  });

  it("works_well_with references only known slugs (or known external tokens)", () => {
    // Skip strings that aren't slugs (e.g. 'other_oscillators_redundant').
    // For known-slug references, verify they exist in the registry.
    const slugs = new Set(Object.keys(INDICATORS));
    const stragglers: string[] = [];
    for (const ind of Object.values(INDICATORS)) {
      for (const ref of ind.works_well_with) {
        // Only validate refs that look like slugs (lowercase + dashes).
        if (/^[a-z][a-z0-9-]*$/.test(ref) && !slugs.has(ref)) {
          stragglers.push(`${ind.slug}.works_well_with -> ${ref}`);
        }
      }
    }
    expect(stragglers).toEqual([]);
  });

  it("listIndicators returns alphabetically sorted by name", () => {
    const list = listIndicators();
    for (let i = 1; i < list.length; i++) {
      expect(
        list[i - 1].name.localeCompare(list[i].name),
      ).toBeLessThanOrEqual(0);
    }
  });
});
