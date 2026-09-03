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
    // 042 shape: futures-only, cash/options named as coming soon, no shadowSl.
    popular: true, strategies: 3, segments: ["FUTURES"],
    comingSoon: ["CASH", "OPTIONS"],
    directions: ["long", "short"], killSwitch: true, analytics: true,
    telegram: true, csv: true, ai: false,
    support: "Priority",
    bullets: [
      "3 strategies",
      "Futures only \u2014 cash & options coming soon",
      "Long + Short",
      "Analytics + Telegram alerts + CSV export",
      "Priority support",
    ],
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

describe("the OPTIONS honesty note under 042's futures-only tiers", () => {
  // The note's own text says "Is plan mein Options milta hai" — THIS PLAN
  // INCLUDES OPTIONS. So it must fire on inclusion and never on a roadmap
  // line, or the guard becomes the false claim it exists to prevent.

  it("🔴 the 042 coming-soon line does NOT fire it", () => {
    // Regression: the loose substring match saw "options" in this bullet and
    // would have stamped "this plan includes options" on ALL THREE cards.
    expect(mentionsOptions(proWithPrices.feature_limits.bullets)).toBe(false);
    expect(
      mentionsOptions(["Futures only \u2014 cash & options coming soon"]),
    ).toBe(false);
  });

  it("no 042 tier fires it — none of them include options", () => {
    expect(mentionsOptions(proWithPrices.feature_limits.segments)).toBe(false);
    expect(mentionsOptions(["FUTURES"])).toBe(false);
    expect(mentionsOptions(["1 strategy", "Long only"])).toBe(false);
  });

  it("but a tier that GENUINELY includes options still fires it", () => {
    // The guard must survive 042 intact, ready for the day options ship.
    expect(mentionsOptions(["CASH + OPTIONS"])).toBe(true);
    expect(mentionsOptions(["All strategies", "CASH + OPTIONS + FUTURES"])).toBe(true);
    expect(mentionsOptions(["Options trading"])).toBe(true);
    // ...including via the structured segments field, which is what the
    // pricing card now feeds it alongside the bullets.
    expect(mentionsOptions(["FUTURES", "OPTIONS"])).toBe(true);
  });

  it("the exclusion is narrow — naming options is not enough to be exempt", () => {
    // "coming soon" is the ONLY escape. A plan that includes options and
    // happens to mention a different coming-soon thing still fires.
    expect(mentionsOptions(["CASH + OPTIONS", "More brokers coming soon"])).toBe(true);
  });
});
