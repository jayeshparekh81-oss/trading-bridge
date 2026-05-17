import { describe, expect, it } from "vitest";

import {
  CATEGORIES,
  CATEGORY_COUNT,
  FAQ_COUNT,
  FAQS,
  type FAQ,
  type FAQCategory,
} from "@/lib/help/faq-content";

describe("faq-content", () => {
  it("has at least 25 FAQ entries", () => {
    expect(FAQ_COUNT).toBeGreaterThanOrEqual(25);
    expect(FAQS.length).toBe(FAQ_COUNT);
  });

  it("declares 10 categories", () => {
    expect(CATEGORY_COUNT).toBe(10);
    expect(CATEGORIES.length).toBe(10);
  });

  it("every FAQ has both languages populated (non-empty)", () => {
    const offenders = FAQS.filter(
      (f) =>
        !f.question_en?.trim() ||
        !f.question_hi?.trim() ||
        !f.answer_en?.trim() ||
        !f.answer_hi?.trim(),
    );
    expect(
      offenders,
      `FAQs missing translations:\n${offenders.map((f) => f.id).join("\n")}`,
    ).toEqual([]);
  });

  it("every category appears in at least one FAQ", () => {
    const categoriesUsed = new Set<FAQCategory>(FAQS.map((f) => f.category));
    const declared = new Set<FAQCategory>(CATEGORIES.map((c) => c.id));
    const missing = [...declared].filter((c) => !categoriesUsed.has(c));
    expect(
      missing,
      `categories with zero FAQs: ${missing.join(", ")}`,
    ).toEqual([]);
  });

  it("every FAQ category is a declared CategoryMeta id", () => {
    const declared = new Set<FAQCategory>(CATEGORIES.map((c) => c.id));
    const offenders = FAQS.filter((f) => !declared.has(f.category));
    expect(offenders).toEqual([]);
  });

  it("ids are unique across the FAQ array", () => {
    const seen = new Set<string>();
    const dupes: string[] = [];
    for (const f of FAQS) {
      if (seen.has(f.id)) dupes.push(f.id);
      seen.add(f.id);
    }
    expect(dupes, `duplicate ids: ${dupes.join(", ")}`).toEqual([]);
  });

  it("every FAQ has at least one tag", () => {
    const offenders = FAQS.filter((f) => !f.tags || f.tags.length === 0);
    expect(
      offenders,
      `FAQs missing tags: ${offenders.map((f) => f.id).join(", ")}`,
    ).toEqual([]);
  });

  it("each category has both en and hi labels", () => {
    const offenders = CATEGORIES.filter(
      (c: { label_en?: string; label_hi?: string }) =>
        !c.label_en?.trim() || !c.label_hi?.trim(),
    );
    expect(offenders).toEqual([]);
  });

  it("question_hi values use Hinglish, not pure Devanagari", () => {
    // Heuristic: at least one ASCII alphanumeric char per Hindi
    // question. Pure Devanagari sentences would have 0 — this catches
    // the "ये क्या है" style without false-positives on Hinglish.
    const purelyDevanagari = FAQS.filter(
      (f) => !/[a-zA-Z0-9]/.test(f.question_hi),
    );
    expect(
      purelyDevanagari,
      `pure-Devanagari questions: ${purelyDevanagari.map((f: FAQ) => f.id).join(", ")}`,
    ).toEqual([]);
  });
});
