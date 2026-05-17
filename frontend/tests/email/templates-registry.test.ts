import { describe, it, expect } from "vitest";
import {
  TEMPLATES,
  TEMPLATE_COUNT,
  getTemplate,
  listTemplates,
  type EmailTemplate,
} from "@/lib/email/templates";

const EXPECTED_COUNT = 10;
const VAR_REGEX = /\{\{(\w+)\}\}/g;

const extractVars = (s: string): Set<string> => {
  const vars = new Set<string>();
  for (const match of s.matchAll(VAR_REGEX)) {
    vars.add(match[1]);
  }
  return vars;
};

const assertShape = (slug: string, t: EmailTemplate) => {
  expect(t.slug, `${slug}: slug match`).toBe(slug);
  expect(t.name.length, `${slug}: name`).toBeGreaterThan(5);
  expect(["transactional", "digest", "welcome", "nudge", "compliance"]).toContain(
    t.category,
  );
  expect(t.subject_en.length, `${slug}: subject_en`).toBeGreaterThan(10);
  expect(t.subject_hi.length, `${slug}: subject_hi`).toBeGreaterThan(10);
  expect(t.body_en.length, `${slug}: body_en`).toBeGreaterThan(100);
  expect(t.body_hi.length, `${slug}: body_hi`).toBeGreaterThan(100);
  expect(Array.isArray(t.required_vars), `${slug}: required_vars array`).toBe(true);
};

describe("email templates registry", () => {
  it("registers the expected number of templates", () => {
    expect(TEMPLATE_COUNT).toBe(EXPECTED_COUNT);
    expect(listTemplates()).toHaveLength(EXPECTED_COUNT);
  });

  it("every template has a well-formed shape", () => {
    for (const [slug, tpl] of Object.entries(TEMPLATES)) {
      assertShape(slug, tpl);
    }
  });

  it("getTemplate returns null for unknown slug", () => {
    expect(getTemplate("does-not-exist")).toBeNull();
    expect(getTemplate("")).toBeNull();
  });

  it("every {{var}} reference in subject/body is declared in required_vars", () => {
    for (const [slug, tpl] of Object.entries(TEMPLATES)) {
      const declared = new Set(tpl.required_vars);
      const usedInContent = new Set<string>([
        ...extractVars(tpl.subject_en),
        ...extractVars(tpl.subject_hi),
        ...extractVars(tpl.body_en),
        ...extractVars(tpl.body_hi),
      ]);
      for (const v of usedInContent) {
        expect(declared.has(v), `${slug}: uses {{${v}}} but not in required_vars`).toBe(true);
      }
    }
  });

  it("every required_var is actually used in subject or body", () => {
    for (const [slug, tpl] of Object.entries(TEMPLATES)) {
      const usedInContent = new Set<string>([
        ...extractVars(tpl.subject_en),
        ...extractVars(tpl.subject_hi),
        ...extractVars(tpl.body_en),
        ...extractVars(tpl.body_hi),
      ]);
      for (const v of tpl.required_vars) {
        expect(usedInContent.has(v), `${slug}: declared {{${v}}} but never used`).toBe(true);
      }
    }
  });

  it("EN and HI bodies use the same set of variables (bilingual parity)", () => {
    for (const [slug, tpl] of Object.entries(TEMPLATES)) {
      const enVars = new Set([
        ...extractVars(tpl.subject_en),
        ...extractVars(tpl.body_en),
      ]);
      const hiVars = new Set([
        ...extractVars(tpl.subject_hi),
        ...extractVars(tpl.body_hi),
      ]);
      for (const v of enVars) {
        expect(hiVars.has(v), `${slug}: EN uses {{${v}}} but HI does not`).toBe(true);
      }
      for (const v of hiVars) {
        expect(enVars.has(v), `${slug}: HI uses {{${v}}} but EN does not`).toBe(true);
      }
    }
  });
});
