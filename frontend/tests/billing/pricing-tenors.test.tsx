/**
 * Four-tenor pricing (migration 041).
 *
 * The two things that matter: every tenor reaches the card with the right
 * per-month price and billed total, and a PRE-041 payload (no price list)
 * still renders via the legacy scalars instead of breaking mid-deploy.
 */

import { describe, it, expect } from "vitest";
import {
  TENORS,
  TENOR_LABELS,
  priceForTenor,
  type PricingPlan,
} from "@/lib/billing/plans";
import { mentionsOptions } from "@/lib/risk-labels";

const proWithPrices: PricingPlan = {
  id: "p", name: "Pro", tier: "pro",
  price_monthly_inr: 2499, price_yearly_inr: 1999,
  sort_order: 2,
  feature_limits: {
    popular: true, strategies: 3, segments: ["CASH", "OPTIONS"],
    directions: ["long", "short"], killSwitch: true, analytics: true,
    telegram: true, csv: true, ai: false, shadowSl: false,
    support: "Priority",
    bullets: ["3 strategies", "CASH + OPTIONS", "Long + Short", "Priority support"],
  },
  prices: [
    { tenor: "monthly", price_per_month_inr: 2499, months_billed: 1, total_billed_inr: 2499, discount_pct: 0, razorpay_plan_id: null },
    { tenor: "quarterly", price_per_month_inr: 2324, months_billed: 3, total_billed_inr: 6972, discount_pct: 7, razorpay_plan_id: null },
    { tenor: "halfyearly", price_per_month_inr: 2174, months_billed: 6, total_billed_inr: 13044, discount_pct: 13, razorpay_plan_id: null },
    { tenor: "yearly", price_per_month_inr: 1999, months_billed: 12, total_billed_inr: 23988, discount_pct: 20, razorpay_plan_id: null },
  ],
};

describe("tenor vocabulary", () => {
  it("has exactly the four sellable periods", () => {
    expect([...TENORS]).toEqual(["monthly", "quarterly", "halfyearly", "yearly"]);
  });
  it("labels every tenor", () => {
    for (const t of TENORS) expect(TENOR_LABELS[t]).toBeTruthy();
  });
});

describe("priceForTenor — with the 041 price list", () => {
  it.each([
    ["monthly", 2499, 1, 2499, 0],
    ["quarterly", 2324, 3, 6972, 7],
    ["halfyearly", 2174, 6, 13044, 13],
    ["yearly", 1999, 12, 23988, 20],
  ])("%s", (tenor, perMonth, months, total, pct) => {
    const p = priceForTenor(proWithPrices, tenor as never);
    expect(p.price_per_month_inr).toBe(perMonth);
    expect(p.months_billed).toBe(months);
    expect(p.total_billed_inr).toBe(total);
    expect(p.discount_pct).toBe(pct);
  });

  it("price falls monotonically as the tenor lengthens", () => {
    const vals = TENORS.map((t) => priceForTenor(proWithPrices, t).price_per_month_inr);
    expect(vals).toEqual([...vals].sort((a, b) => b - a));
  });
});

describe("PRE-041 payload still renders (no mid-deploy breakage)", () => {
  const legacy: PricingPlan = { ...proWithPrices, prices: undefined };

  it("falls back to the legacy monthly scalar", () => {
    const p = priceForTenor(legacy, "monthly");
    expect(p.price_per_month_inr).toBe(2499);
    expect(p.total_billed_inr).toBe(2499);
  });

  it("falls back to the legacy yearly scalar with the right total", () => {
    const p = priceForTenor(legacy, "yearly");
    expect(p.price_per_month_inr).toBe(1999);
    expect(p.months_billed).toBe(12);
    expect(p.total_billed_inr).toBe(23988);
    expect(p.discount_pct).toBe(20);
  });

  it("never returns NaN or throws for any tenor", () => {
    for (const t of TENORS) {
      const p = priceForTenor(legacy, t);
      expect(Number.isFinite(p.price_per_month_inr)).toBe(true);
      expect(Number.isFinite(p.total_billed_inr)).toBe(true);
    }
  });

  it("survives an all-zero plan without dividing by zero", () => {
    const empty: PricingPlan = {
      ...legacy, price_monthly_inr: 0, price_yearly_inr: 0,
    };
    for (const t of TENORS) {
      expect(priceForTenor(empty, t).discount_pct).toBe(0);
    }
  });
});

describe("OPTIONS honesty note fires under the NEW tiers", () => {
  it("Pro advertises options → note fires", () => {
    expect(mentionsOptions(proWithPrices.feature_limits.bullets)).toBe(true);
  });

  it("Premium advertises options → note fires", () => {
    expect(mentionsOptions(["All strategies", "CASH + OPTIONS + FUTURES"])).toBe(true);
  });

  it("Starter does NOT → note stays hidden", () => {
    expect(mentionsOptions(["1 strategy", "CASH only", "Long only"])).toBe(false);
  });
});
