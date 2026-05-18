import { describe, it, expect } from "vitest";
import {
  MARKETING,
  MARKETING_COUNT,
  getMarketing,
  listMarketing,
  listMarketingByPlatform,
  type MarketingTemplate,
} from "@/lib/marketing";

const EXPECTED_COUNT = 22;
const EXPECTED_PLATFORM_COUNTS = {
  telegram: 8,
  twitter: 6,
  whatsapp: 5,
  instagram: 3,
};
const VAR_REGEX = /\{\{(\w+)\}\}/g;

const extractVars = (s: string): Set<string> => {
  const out = new Set<string>();
  for (const m of s.matchAll(VAR_REGEX)) out.add(m[1]);
  return out;
};

const assertShape = (slug: string, t: MarketingTemplate) => {
  expect(t.slug, `${slug}: slug match`).toBe(slug);
  expect(["telegram", "twitter", "whatsapp", "instagram"]).toContain(t.platform);
  expect(["new_user", "active_user", "waitlist", "general"]).toContain(t.audience);
  expect(t.use_case.length, `${slug}: use_case`).toBeGreaterThan(10);
  expect(t.content_en.length, `${slug}: content_en`).toBeGreaterThan(50);
  expect(t.content_hi.length, `${slug}: content_hi`).toBeGreaterThan(50);
  expect(t.cta.length, `${slug}: cta`).toBeGreaterThan(3);
  expect(t.estimated_chars, `${slug}: estimated_chars`).toBeGreaterThan(0);
  expect(Array.isArray(t.visuals_suggested), `${slug}: visuals array`).toBe(true);
  expect(t.visuals_suggested.length, `${slug}: ≥1 visual`).toBeGreaterThanOrEqual(1);
  expect(Array.isArray(t.required_vars), `${slug}: required_vars array`).toBe(true);
};

describe("marketing content registry", () => {
  it("registers the expected number of templates", () => {
    expect(MARKETING_COUNT).toBe(EXPECTED_COUNT);
    expect(listMarketing()).toHaveLength(EXPECTED_COUNT);
  });

  it("platform distribution matches design", () => {
    for (const [platform, expected] of Object.entries(EXPECTED_PLATFORM_COUNTS)) {
      expect(
        listMarketingByPlatform(platform as "telegram" | "twitter" | "whatsapp" | "instagram"),
        `${platform} count`,
      ).toHaveLength(expected);
    }
  });

  it("every template has a well-formed shape", () => {
    for (const [slug, tpl] of Object.entries(MARKETING)) {
      assertShape(slug, tpl);
    }
  });

  it("getMarketing returns null for unknown slug", () => {
    expect(getMarketing("does-not-exist")).toBeNull();
    expect(getMarketing("")).toBeNull();
  });

  it("every {{var}} in EN/HI is declared in required_vars", () => {
    for (const [slug, tpl] of Object.entries(MARKETING)) {
      const declared = new Set(tpl.required_vars);
      const used = new Set([...extractVars(tpl.content_en), ...extractVars(tpl.content_hi)]);
      for (const v of used) {
        expect(declared.has(v), `${slug}: uses {{${v}}} but not declared`).toBe(true);
      }
    }
  });

  it("every declared var is actually used in content (no orphans)", () => {
    for (const [slug, tpl] of Object.entries(MARKETING)) {
      const used = new Set([...extractVars(tpl.content_en), ...extractVars(tpl.content_hi)]);
      for (const v of tpl.required_vars) {
        expect(used.has(v), `${slug}: declared {{${v}}} but not used`).toBe(true);
      }
    }
  });
});
