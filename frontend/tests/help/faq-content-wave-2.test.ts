import { describe, expect, it } from "vitest";

import { FAQS, FAQ_COUNT } from "@/lib/help/faq-content";

/**
 * Wave 2 FAQ additions. The original test file (faq-content.test.ts)
 * pinned the count at 35 and category set at 10. This file layers
 * Wave 2 assertions on top — 25 new FAQs added into the existing
 * 10 categories (no category type change to preserve original tests).
 */

const WAVE_2_FAQ_IDS = [
  // Advanced Strategy → 'strategies'
  "interpret-backtest-results",
  "strategy-lifecycle",
  "when-to-retire-strategy",
  "walk-forward-vs-backtest",
  "single-vs-portfolio-strategies",
  // Indicator Combinations → 'strategies'
  "complementary-indicators",
  "conflicting-signals",
  "how-many-indicators",
  "trend-vs-momentum-vs-volume",
  "indicator-period-tuning",
  // Risk Management → 'compliance'
  "position-sizing-basics",
  "kill-switch-when-to-use",
  "drawdown-handling",
  "leverage-warning",
  "stop-loss-discipline",
  // Indian Market Specifics → 'live-trading'
  "expiry-day-quirks",
  "circuit-breakers",
  "bse-vs-nse",
  "muhurat-trading",
  "rbi-policy-impact",
  // Tax & Compliance → 'compliance'
  "stcg-ltcg-basics",
  "fno-tax-treatment",
  "advance-tax-for-traders",
  "fno-turnover-calculation",
  "tax-loss-harvesting",
] as const;

describe("Wave 2 FAQs added", () => {
  it("FAQ_COUNT is 60 (35 Wave 1 + 25 Wave 2)", () => {
    expect(FAQ_COUNT).toBe(60);
  });

  it("Wave 2 IDs list contains 25 entries", () => {
    expect(WAVE_2_FAQ_IDS.length).toBe(25);
  });

  it("every Wave 2 ID is present in the FAQS array", () => {
    const ids = new Set(FAQS.map((f) => f.id));
    const missing = WAVE_2_FAQ_IDS.filter((id) => !ids.has(id));
    expect(missing).toEqual([]);
  });

  describe.each(WAVE_2_FAQ_IDS)("FAQ %s", (id) => {
    const f = FAQS.find((x) => x.id === id);

    it("has both languages populated", () => {
      expect(f, `missing FAQ id=${id}`).toBeDefined();
      if (!f) return;
      expect(f.question_en.trim().length).toBeGreaterThan(0);
      expect(f.question_hi.trim().length).toBeGreaterThan(0);
      expect(f.answer_en.trim().length).toBeGreaterThan(50);
      expect(f.answer_hi.trim().length).toBeGreaterThan(50);
    });

    it("question_hi uses Hinglish (has ASCII letters)", () => {
      if (!f) return;
      expect(/[a-zA-Z0-9]/.test(f.question_hi)).toBe(true);
    });

    it("has at least one tag", () => {
      if (!f) return;
      expect(f.tags.length).toBeGreaterThan(0);
    });

    it("category is one of the existing 10 (no new categories added)", () => {
      if (!f) return;
      const allowed = new Set([
        "getting-started",
        "account",
        "brokers",
        "chart",
        "strategies",
        "backtest",
        "live-trading",
        "pricing",
        "compliance",
        "troubleshooting",
      ]);
      expect(allowed.has(f.category)).toBe(true);
    });
  });
});
