import { describe, expect, it } from "vitest";

import {
  DISCLAIMER_SECTIONS,
  FOOTER_COPY,
  LS_KEY_PRE_TRADE_ACK,
  LS_KEY_RISK_ACK,
  PRE_TRADE_COPY,
  RISK_ACK_COPY,
  SECTION_COUNT,
} from "@/lib/compliance/disclaimer-text";

describe("disclaimer-text content", () => {
  it("declares at least 6 legal sections", () => {
    expect(SECTION_COUNT).toBeGreaterThanOrEqual(6);
    expect(DISCLAIMER_SECTIONS.length).toBe(SECTION_COUNT);
  });

  it("every section has both languages populated", () => {
    const offenders = DISCLAIMER_SECTIONS.filter(
      (s) =>
        !s.title_en?.trim() ||
        !s.title_hi?.trim() ||
        !s.body_en?.trim() ||
        !s.body_hi?.trim(),
    );
    expect(
      offenders,
      `sections missing translations: ${offenders.map((s) => s.id).join(", ")}`,
    ).toEqual([]);
  });

  it("section ids are unique", () => {
    const seen = new Set<string>();
    const dupes: string[] = [];
    for (const s of DISCLAIMER_SECTIONS) {
      if (seen.has(s.id)) dupes.push(s.id);
      seen.add(s.id);
    }
    expect(dupes, `duplicate section ids: ${dupes.join(", ")}`).toEqual([]);
  });

  it("required canonical sections are present", () => {
    const ids = new Set(DISCLAIMER_SECTIONS.map((s) => s.id));
    // The spec listed six; assert each appears so future refactors
    // can't silently drop one.
    expect(ids.has("risk-disclosure")).toBe(true);
    expect(ids.has("terms")).toBe(true);
    expect(ids.has("sebi-framework")).toBe(true);
    expect(ids.has("data-privacy")).toBe(true);
    expect(ids.has("glass-box-ai")).toBe(true);
    expect(ids.has("transparency-ledger")).toBe(true);
  });

  it("footer copy is non-empty in both languages", () => {
    expect(FOOTER_COPY.en.length).toBeGreaterThan(40);
    expect(FOOTER_COPY.hi.length).toBeGreaterThan(40);
    expect(FOOTER_COPY.cta_en).toBeTruthy();
    expect(FOOTER_COPY.cta_hi).toBeTruthy();
  });

  it("risk-ack copy mentions 'risk' (en) and 'risk' (hi)", () => {
    expect(RISK_ACK_COPY.en.toLowerCase()).toContain("risk");
    expect(RISK_ACK_COPY.hi.toLowerCase()).toContain("risk");
    expect(RISK_ACK_COPY.error_en).toBeTruthy();
    expect(RISK_ACK_COPY.error_hi).toBeTruthy();
  });

  it("pre-trade modal carries title + intro + bullets + CTAs in both langs", () => {
    expect(PRE_TRADE_COPY.title_en).toBeTruthy();
    expect(PRE_TRADE_COPY.title_hi).toBeTruthy();
    expect(PRE_TRADE_COPY.intro_en).toBeTruthy();
    expect(PRE_TRADE_COPY.intro_hi).toBeTruthy();
    expect(PRE_TRADE_COPY.bullets_en.length).toBeGreaterThanOrEqual(5);
    expect(PRE_TRADE_COPY.bullets_hi.length).toBe(
      PRE_TRADE_COPY.bullets_en.length,
    );
    expect(PRE_TRADE_COPY.cta_en).toBeTruthy();
    expect(PRE_TRADE_COPY.cta_hi).toBeTruthy();
    expect(PRE_TRADE_COPY.cancel_en).toBeTruthy();
    expect(PRE_TRADE_COPY.cancel_hi).toBeTruthy();
  });

  it("hi titles use Hinglish, not pure Devanagari (heuristic)", () => {
    const offenders = DISCLAIMER_SECTIONS.filter(
      (s) => !/[a-zA-Z0-9]/.test(s.title_hi),
    );
    expect(
      offenders,
      `pure-Devanagari titles: ${offenders.map((s) => s.id).join(", ")}`,
    ).toEqual([]);
  });

  it("localStorage keys are stable + non-colliding", () => {
    expect(LS_KEY_RISK_ACK).toBe("tradetri_risk_ack_v1");
    expect(LS_KEY_PRE_TRADE_ACK).toBe("tradetri_pre_trade_ack_v1");
    expect(LS_KEY_RISK_ACK).not.toBe(LS_KEY_PRE_TRADE_ACK);
  });
});
