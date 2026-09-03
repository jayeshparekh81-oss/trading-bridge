"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { CheckCircle, XCircle, ChevronDown } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { cn } from "@/lib/utils";
import { useApi } from "@/lib/use-api";
import { TENORS, TENOR_LABELS, priceForTenor, type PlansResponse, type Tenor } from "@/lib/billing/plans";
import { OptionsMetricsNote } from "@/components/billing/options-metrics-note";
import { PlanCheckoutButton } from "@/components/billing/plan-checkout-button";

const stagger = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

// Feature-comparison table rows. UI metadata (labels + which feature_limits
// key drives the cell); the per-plan values are DB-sourced (B1).
const featureRows = [
  // `brokers` removed by migration 041 — the differentiator is SEGMENT +
  // STRATEGY COUNT, not broker caps. Leaving it would render an empty column.
  { label: "Strategies", key: "strategies" },
  { label: "Segments", key: "segments", list: true },
  // Its OWN row, and labelled "not included", so a roadmap promise can never
  // be read as part of the plan (042).
  { label: "Coming soon (not included)", key: "comingSoon", list: true },
  { label: "Direction", key: "directions", list: true },
  { label: "Kill Switch", key: "killSwitch", bool: true },
  { label: "Analytics Dashboard", key: "analytics", bool: true },
  { label: "Telegram Alerts", key: "telegram", bool: true },
  { label: "CSV Export", key: "csv", bool: true },
  // NOT "AI Smart Signals" — that reads as a gate that filters your trades.
  // The validator has rejected 0 of 40 signals on the live strategy; it is an
  // advisory score and the label now says so (042).
  { label: "AI conviction score (advisory)", key: "ai", bool: true },
  // `shadowSl` removed by 042 — it had NO backend implementation at all.
  // Left in place it would render a row that is empty on every tier, exactly
  // the reason 041 removed `brokers`.
  { label: "Support", key: "support" },
];

const faqs = [
  {
    q: "Is there a free trial?",
    a: "No — there is no free trial on the paid plans today, and we would rather say so than promise one we do not run. Signing up costs nothing and needs no credit card. When you do subscribe, the plan bills from the first payment, and you can cancel anytime.",
  },
  {
    q: "Can I switch plans later?",
    a: "Absolutely. Upgrade or downgrade anytime. Changes take effect immediately.",
  },
  {
    q: "What payment methods do you accept?",
    a: "UPI, credit/debit cards, net banking via Razorpay. All payments are secure.",
  },
  {
    q: "Do I need coding knowledge?",
    a: "No! TRADETRI is designed for non-coders. Set up in 3 minutes with visual tools.",
  },
  {
    // MUST track the DB blob (042). This answer restates the tier matrix in
    // prose a few hundred pixels below the comparison table that renders the
    // same facts from the database — so a data change that skips this string
    // makes the page contradict itself. Deliberately does NOT enumerate
    // Telegram alerts or CSV export: both are advertised in the table but
    // neither currently reaches a customer, and restating them here would
    // spread a claim rather than merely inherit it.
    q: "What does each plan actually unlock?",
    a: "Strategy count and support, not segments: every tier trades FUTURES today — cash and options are coming, and no plan includes them yet. Starter runs 1 strategy, long only. Pro runs 3, long and short. Premium runs all of them, with direct founder support.",
  },
  {
    q: "Is my data secure?",
    a: "Yes. AES-256 encryption, HMAC-signed webhooks, and SEBI-aware practices. Your credentials are encrypted at rest.",
  },
  {
    q: "What if I exceed my strategy limit?",
    a: "You'll be prompted to upgrade. Active strategies continue working.",
  },
];

export default function PricingPage() {
  const [tenor, setTenor] = useState<Tenor>("yearly");
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  // B1 — pricing is DB-sourced (GET /api/pricing/plans), no longer hardcoded.
  // Public endpoint; the api client sends no auth header when unauthenticated.
  const { data, isLoading, error } = useApi<PlansResponse>("/pricing/plans");
  const plans = (data?.plans ?? []).map((p) => ({
    id: p.id,
    name: p.name,
    monthly: p.price_monthly_inr,
    yearly: p.price_yearly_inr,
    popular: p.feature_limits.popular,
    features: p.feature_limits,
    price: priceForTenor(p, tenor),
    raw: p,
  }));
  const hasPlans = plans.length > 0;

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="pt-24 pb-16">
      <motion.div variants={fadeUp} className="text-center px-4 mb-10">
        <h1 className="text-4xl md:text-5xl font-bold mb-4">
          Simple,{" "}
          <span className="bg-gradient-to-b from-[#FFD700] to-[#00FF88] bg-clip-text text-transparent">
            Transparent
          </span>{" "}
          Pricing
        </h1>
        <p className="text-muted-foreground max-w-lg mx-auto">
          Signing up needs no credit card. Paid plans bill from the first
          payment — cancel anytime.
        </p>
        {/* 4-way tenor selector (migration 041). The discount shown per tenor
            is computed server-side from that tier's OWN monthly price, so the
            ladder can never drift from the numbers on the card. */}
        <div
          role="group"
          aria-label="Billing period"
          className="inline-flex flex-wrap items-center justify-center gap-1 mt-6 p-1 rounded-xl border border-border bg-white/[0.02]"
        >
          {TENORS.map((t) => {
            const sample = plans[0] ? priceForTenor(plans[0].raw, t) : null;
            const off = sample?.discount_pct ?? 0;
            return (
              <button
                key={t}
                type="button"
                onClick={() => setTenor(t)}
                aria-pressed={tenor === t}
                data-testid={`tenor-${t}`}
                className={cn(
                  "px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors",
                  tenor === t
                    ? "bg-primary/15 text-primary"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {TENOR_LABELS[t]}
                {off > 0 && (
                  <span className="ml-1 text-profit text-[10px]">−{off}%</span>
                )}
              </button>
            );
          })}
        </div>
      </motion.div>

      {/* Plan cards — DB-sourced (B1) with honest loading / error / empty states */}
      {isLoading ? (
        <p className="max-w-5xl mx-auto px-4 mb-16 text-center text-sm text-muted-foreground">
          Loading plans…
        </p>
      ) : error ? (
        <p className="max-w-5xl mx-auto px-4 mb-16 text-center text-sm text-loss">
          Couldn&apos;t load pricing — please refresh.
        </p>
      ) : !hasPlans ? (
        <p className="max-w-5xl mx-auto px-4 mb-16 text-center text-sm text-muted-foreground">
          No plans available right now.
        </p>
      ) : (
        <div className="max-w-5xl mx-auto px-4 grid md:grid-cols-3 gap-6 mb-16">
          {plans.map((plan) => (
            <motion.div key={plan.name} variants={fadeUp}>
              <GlassmorphismCard
                glow={plan.popular ? "blue" : "none"}
                className={cn("relative", plan.popular && "border-accent-blue/40 scale-[1.02]")}
              >
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full bg-accent-blue text-white text-xs font-bold">
                    Most Popular
                  </div>
                )}
                <div className="text-center mb-6">
                  <h3 className="font-bold text-xl mb-2">{plan.name}</h3>
                  <div className="text-4xl font-bold">
                    {"₹"}
                    {plan.price.price_per_month_inr}
                    <span className="text-base font-normal text-muted-foreground">/mo</span>
                  </div>
                  {plan.price.months_billed > 1 && (
                    <p className="text-xs text-profit mt-1">
                      Billed {"₹"}
                      {plan.price.total_billed_inr} every{" "}
                      {plan.price.months_billed} months
                      {plan.price.discount_pct > 0
                        ? ` · save ${plan.price.discount_pct}%`
                        : ""}
                    </p>
                  )}
                </div>
                {/* Mandatory: options carry no verified metrics of their own.
                    Fed the SEGMENTS list as well as the bullets: 042 moved the
                    segment truth into `segments`, so keying off prose alone
                    would go blind if a future tier gains OPTIONS there without
                    the bullet being reworded. */}
                <OptionsMetricsNote
                  features={[
                    ...(plan.features?.segments ?? []),
                    ...(plan.features?.bullets ?? []),
                  ]}
                  className="mb-4"
                />
                <PlanCheckoutButton
                  planId={plan.id}
                  planName={plan.name}
                  popular={plan.popular}
                />
              </GlassmorphismCard>
            </motion.div>
          ))}
        </div>
      )}

      {/* Feature comparison table */}
      {hasPlans && (
        <motion.div variants={fadeUp} className="max-w-5xl mx-auto px-4 mb-16">
          <h2 className="text-2xl font-bold text-center mb-8">Feature Comparison</h2>
          <GlassmorphismCard hover={false} className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.08]">
                    <th className="text-left py-3 px-4 text-xs text-muted-foreground uppercase">
                      Feature
                    </th>
                    {plans.map((p) => (
                      <th
                        key={p.name}
                        className={cn(
                          "text-center py-3 px-4 text-xs uppercase",
                          p.popular ? "text-accent-blue font-bold" : "text-muted-foreground",
                        )}
                      >
                        {p.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {featureRows.map((row) => (
                    <tr key={row.key} className="border-b border-white/[0.04]">
                      <td className="py-3 px-4">{row.label}</td>
                      {plans.map((p) => {
                        const val = p.features[row.key as keyof typeof p.features];
                        return (
                          <td key={p.name} className="py-3 px-4 text-center">
                            {row.bool ? (
                              val ? (
                                <CheckCircle className="h-4 w-4 text-profit mx-auto" />
                              ) : (
                                <XCircle className="h-4 w-4 text-muted-foreground/40 mx-auto" />
                              )
                            ) : row.list ? (
                              <span className="font-medium text-xs">
                                {Array.isArray(val) ? val.join(" + ") : "—"}
                              </span>
                            ) : (
                              <span className="font-medium">
                                {row.key === "strategies"
                                  ? val === "all"
                                    ? "All"
                                    : `up to ${val}`
                                  : String(val)}
                              </span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassmorphismCard>
        </motion.div>
      )}

      {/* FAQ */}
      <motion.div variants={fadeUp} className="max-w-3xl mx-auto px-4">
        <h2 className="text-2xl font-bold text-center mb-8">Frequently Asked Questions</h2>
        <div className="space-y-3">
          {faqs.map((faq, i) => (
            <GlassmorphismCard key={i} hover={false} className="p-0 overflow-hidden">
              <button
                onClick={() => setOpenFaq(openFaq === i ? null : i)}
                className="flex items-center justify-between w-full p-4 text-left"
              >
                <span className="font-medium text-sm">{faq.q}</span>
                <ChevronDown
                  className={cn(
                    "h-4 w-4 text-muted-foreground transition-transform shrink-0 ml-4",
                    openFaq === i && "rotate-180",
                  )}
                />
              </button>
              {openFaq === i && (
                <motion.div
                  initial={{ height: 0 }}
                  animate={{ height: "auto" }}
                  className="overflow-hidden"
                >
                  <p className="px-4 pb-4 text-sm text-muted-foreground">{faq.a}</p>
                </motion.div>
              )}
            </GlassmorphismCard>
          ))}
        </div>
      </motion.div>
    </motion.div>
  );
}
