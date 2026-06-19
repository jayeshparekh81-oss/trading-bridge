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
  /** Structured flags used by the /pricing feature-comparison table. */
  brokers: number;
  strategies: number;
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

export interface PricingPlan {
  id: string;
  name: string;
  tier: string;
  price_monthly_inr: number;
  price_yearly_inr: number;
  feature_limits: PricingFeatureLimits;
  sort_order: number;
}

export interface PlansResponse {
  plans: PricingPlan[];
}
