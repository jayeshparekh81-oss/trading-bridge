"use client";

import { CheckCircle } from "lucide-react";
import Link from "next/link";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { cn } from "@/lib/utils";
import { useApi } from "@/lib/use-api";
import type { PlansResponse } from "@/lib/billing/plans";

/**
 * Home-page pricing cards — DB-sourced (Phase 2 Billing B1).
 *
 * Renders the same Starter / Pro / Premium cards the home page used to
 * hardcode, now from `GET /api/pricing/plans` — one source shared with the
 * dedicated /pricing page (kills the previous two-copy drift). Public
 * endpoint; the api client sends no auth header when unauthenticated.
 */
export function HomePricing() {
  const { data, isLoading, error } = useApi<PlansResponse>("/pricing/plans");
  const plans = (data?.plans ?? []).map((p) => ({
    name: p.name,
    price: p.price_monthly_inr,
    features: p.feature_limits.bullets,
    popular: p.feature_limits.popular,
  }));

  if (isLoading) {
    return <p className="text-center text-sm text-muted-foreground">Loading plans…</p>;
  }
  if (error) {
    return (
      <p className="text-center text-sm text-loss">Couldn&apos;t load pricing — please refresh.</p>
    );
  }
  if (plans.length === 0) {
    return (
      <p className="text-center text-sm text-muted-foreground">No plans available right now.</p>
    );
  }

  return (
    <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
      {plans.map((plan) => (
        <GlassmorphismCard
          key={plan.name}
          glow={plan.popular ? "blue" : "none"}
          className={cn("relative", plan.popular && "border-accent-blue/40 scale-[1.02]")}
        >
          {plan.popular && (
            <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full bg-accent-blue text-white text-xs font-bold">
              Most Popular
            </div>
          )}
          <div className="text-center mb-6">
            <h3 className="font-bold text-xl mb-1">{plan.name}</h3>
            <div className="text-3xl font-bold">
              {"₹"}
              {plan.price}
              <span className="text-base font-normal text-muted-foreground">/mo</span>
            </div>
          </div>
          <ul className="space-y-2.5 mb-6">
            {plan.features.map((f) => (
              <li key={f} className="flex items-center gap-2 text-sm">
                <CheckCircle className="h-4 w-4 text-profit shrink-0" />
                {f}
              </li>
            ))}
          </ul>
          <Link
            href="/register"
            className={cn(
              "block text-center py-3 rounded-xl font-semibold transition-all",
              plan.popular
                ? "bg-gradient-to-r from-accent-blue to-accent-purple text-white hover:shadow-[0_0_25px_rgba(59,130,246,0.4)]"
                : "border border-border hover:bg-accent",
            )}
          >
            Start Free
          </Link>
        </GlassmorphismCard>
      ))}
    </div>
  );
}
