/**
 * Subscription-plan types — shared shape for the pricing surfaces.
 *
 * Phase 2 Billing B1: the Starter / Pro / Premium tiers now come from
 * `GET /api/pricing/plans` (one DB source) instead of being hardcoded in
 * two places. Both the dedicated pricing page and the home page's pricing
 * section consume these types via `useApi<PlansResponse>("/pricing/plans")`.
 */

/** Opaque render blob stored per plan (mirrors the backend JSON column). */
export interface PricingFeatureLimits {
  /** "Most Popular" highlight flag. */
  popular: boolean;
  /** Structured flags used by the /pricing feature-comparison table.
   *  `brokers` was removed by migration 041 — the differentiator is now
   *  SEGMENT + STRATEGY COUNT, not broker caps. */
  strategies: number | string;
  segments?: string[];
  directions?: string[];
  killSwitch: boolean;
  analytics: boolean;
  telegram: boolean;
  csv: boolean;
  ai: boolean;
  shadowSl: boolean;
  support: string;
  /** Per-card bullet list used by the home page's pricing cards. */
  bullets: string[];
}

/** Sellable billing periods, cheapest-per-month last. */
export const TENORS = ["monthly", "quarterly", "halfyearly", "yearly"] as const;
export type Tenor = (typeof TENORS)[number];

export const TENOR_LABELS: Record<Tenor, string> = {
  monthly: "Monthly",
  quarterly: "3 months",
  halfyearly: "6 months",
  yearly: "Yearly",
};

/** One (tier, tenor) with its OWN Razorpay handle — see migration 041. */
export interface PricingPlanPrice {
  tenor: string;
  price_per_month_inr: number;
  months_billed: number;
  total_billed_inr: number;
  discount_pct: number;
  razorpay_plan_id: string | null;
}

export interface PricingPlan {
  id: string;
  name: string;
  tier: string;
  price_monthly_inr: number;
  price_yearly_inr: number;
  feature_limits: PricingFeatureLimits;
  sort_order: number;
  /** All tenors. Empty before migration 041 — callers fall back to the
   *  legacy monthly/yearly scalars so the page never breaks mid-deploy. */
  prices?: PricingPlanPrice[];
}

/** The price for one tenor, falling back to the legacy scalars when the
 *  price list is absent (pre-041 API). Never throws, never returns NaN. */
export function priceForTenor(plan: PricingPlan, tenor: Tenor): PricingPlanPrice {
  const hit = plan.prices?.find((p) => p.tenor === tenor);
  if (hit) return hit;
  const months = { monthly: 1, quarterly: 3, halfyearly: 6, yearly: 12 }[tenor];
  const perMonth =
    tenor === "yearly" ? plan.price_yearly_inr : plan.price_monthly_inr;
  const base = plan.price_monthly_inr || perMonth || 0;
  return {
    tenor,
    price_per_month_inr: perMonth,
    months_billed: months,
    total_billed_inr: perMonth * months,
    discount_pct: base ? Math.max(0, Math.round((1 - perMonth / base) * 100)) : 0,
    razorpay_plan_id: null,
  };
}

export interface PlansResponse {
  plans: PricingPlan[];
}
