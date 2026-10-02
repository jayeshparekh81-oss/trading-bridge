"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { CheckCircle, XCircle, ChevronDown } from "lucide-react";
import { GlassmorphismCard } from "@/shared/ui/glassmorphism-card";
import { cn } from "@/shared/lib/utils";
import { useApi } from "@/shared/api/use-api";
import { TENORS, TENOR_LABELS, priceForTenor, type PlansResponse, type Tenor } from "@/lib/billing/plans";
import { OptionsMetricsNote } from "@/components/billing/options-metrics-note";
import { PlanCheckoutButton } from "@/components/billing/plan-checkout-button";
import { publicCopy } from "@/lib/i18n/copy/public";
import { fill, useCopy } from "@/lib/i18n/core";

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
// `brokers` removed by migration 041 — the differentiator is SEGMENT + STRATEGY COUNT. The
// "coming soon" row is its OWN row labelled "not included" (042). The score row says "advisory"
// (0 of 40 signals rejected on the live strategy). `shadowSl` removed by 042 (no backend).
type C = Record<keyof typeof publicCopy.dicts.en, string>;
const featureRows = (c: C) => [
  { label: c.pr_row_strategies, key: "strategies" },
  { label: c.pr_row_segments, key: "segments", list: true },
  { label: c.pr_row_coming, key: "comingSoon", list: true },
  { label: c.pr_row_directions, key: "directions", list: true },
  { label: c.pr_row_kill, key: "killSwitch", bool: true },
  { label: c.pr_row_analytics, key: "analytics", bool: true },
  { label: c.pr_row_telegram, key: "telegram", bool: true },
  { label: c.pr_row_csv, key: "csv", bool: true },
  { label: c.pr_row_ai, key: "ai", bool: true },
  { label: c.pr_row_support, key: "support" },
];

// MUST track the DB blob (042): faq5 restates the tier matrix in prose beside the table that renders
// the same facts from the database. Deliberately does NOT enumerate Telegram/CSV (neither reaches a
// customer yet).
const faqs = (c: C) => [
  { q: c.faq1_q, a: c.faq1_a }, { q: c.faq2_q, a: c.faq2_a }, { q: c.faq3_q, a: c.faq3_a }, { q: c.faq4_q, a: c.faq4_a },
  { q: c.faq5_q, a: c.faq5_a }, { q: c.faq6_q, a: c.faq6_a }, { q: c.faq7_q, a: c.faq7_a },
];

export default function PricingPage() {
  const [tenor, setTenor] = useState<Tenor>("yearly");
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const { c } = useCopy(publicCopy);
  const rows = featureRows(c);
  const faqList = faqs(c);

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
          {c.pr_h1_a}{" "}
          <span className="bg-gradient-to-b from-brand-gold to-brand-green bg-clip-text text-transparent">
            {c.pr_h1_b}
          </span>{" "}
          {c.pr_h1_c}
        </h1>
        <p className="text-muted-foreground max-w-lg mx-auto">{c.pricing_sub}</p>
        {/* 4-way tenor selector (migration 041). The discount shown per tenor
            is computed server-side from that tier's OWN monthly price, so the
            ladder can never drift from the numbers on the card. */}
        <div
          role="group"
          aria-label={c.pr_tenor_aria}
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
                  <span className="ml-1 text-profit text-xs">−{off}%</span>
                )}
              </button>
            );
          })}
        </div>
      </motion.div>

      {/* Plan cards — DB-sourced (B1) with honest loading / error / empty states */}
      {isLoading ? (
        <p className="max-w-5xl mx-auto px-4 mb-16 text-center text-sm text-muted-foreground">
          {c.pr_loading}
        </p>
      ) : error ? (
        <p className="max-w-5xl mx-auto px-4 mb-16 text-center text-sm text-loss">
          {c.pr_error}
        </p>
      ) : !hasPlans ? (
        <p className="max-w-5xl mx-auto px-4 mb-16 text-center text-sm text-muted-foreground">
          {c.pr_empty}
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
                    {c.pr_popular}
                  </div>
                )}
                <div className="text-center mb-6">
                  <h3 className="font-bold text-xl mb-2">{plan.name}</h3>
                  <div className="text-4xl font-bold">
                    {"₹"}
                    {plan.price.price_per_month_inr}
                    <span className="text-base font-normal text-muted-foreground">{c.pr_per_month}</span>
                  </div>
                  {plan.price.months_billed > 1 && (
                    <p className="text-xs text-profit mt-1">
                      {fill(c.pr_billed, { months: plan.price.months_billed, total: plan.price.total_billed_inr })}
                      {plan.price.discount_pct > 0 ? fill(c.pr_saving, { pct: plan.price.discount_pct }) : ""}
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
          <h2 className="text-2xl font-bold text-center mb-8">{c.pr_compare_h2}</h2>
          <GlassmorphismCard hover={false} className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.08]">
                    <th className="text-left py-3 px-4 text-xs text-muted-foreground uppercase">
                      {c.pr_col_what}
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
                  {rows.map((row) => (
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
                                {Array.isArray(val) && val.length ? val.join(" + ") : c.pr_none}
                              </span>
                            ) : (
                              <span className="font-medium">
                                {row.key === "strategies"
                                  ? val === "all"
                                    ? c.pr_all
                                    : fill(c.pr_upto, { n: String(val) })
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
        <h2 className="text-2xl font-bold text-center mb-8">{c.pr_faq_h2}</h2>
        <div className="space-y-3">
          {faqList.map((faq, i) => (
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
