"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { CheckCircle, XCircle, ChevronDown } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { cn } from "@/lib/utils";
import { useApi } from "@/lib/use-api";
import type { PlansResponse } from "@/lib/billing/plans";
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
  { label: "Brokers", key: "brokers" },
  { label: "Strategies", key: "strategies" },
  { label: "Kill Switch", key: "killSwitch", bool: true },
  { label: "Analytics Dashboard", key: "analytics", bool: true },
  { label: "Telegram Alerts", key: "telegram", bool: true },
  { label: "CSV Export", key: "csv", bool: true },
  { label: "AI Smart Signals", key: "ai", bool: true },
  { label: "Shadow Stop-Loss", key: "shadowSl", bool: true },
  { label: "Support", key: "support" },
];

const faqs = [
  {
    q: "Is there a free trial?",
    a: "Yes! All plans come with a 7-day free trial. No credit card required.",
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
    q: "Is there a refund policy?",
    a: "Yes, 7-day money-back guarantee. If you're not satisfied, full refund, no questions asked.",
  },
  {
    q: "Do I need coding knowledge?",
    a: "No! TRADETRI is designed for non-coders. Set up in 3 minutes with visual tools.",
  },
  {
    q: "How many brokers can I connect?",
    a: "Depends on your plan: Starter (1), Pro (3), Premium (all 6).",
  },
  {
    q: "Is my data secure?",
    a: "Yes. AES-256 encryption, 15 security layers, SEBI-compliant practices. Your credentials are encrypted at rest.",
  },
  {
    q: "What if I exceed my strategy limit?",
    a: "You'll be prompted to upgrade. Active strategies continue working.",
  },
];

export default function PricingPage() {
  const [yearly, setYearly] = useState(true);
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
  }));
  const hasPlans = plans.length > 0;

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="pt-24 pb-16">
      {/* Banner */}
      <motion.div variants={fadeUp} className="text-center px-4 mb-4">
        <div className="inline-block px-4 py-1.5 rounded-full bg-accent-gold/10 text-accent-gold text-sm font-medium mb-6">
          First 3 months FREE for early adopters!
        </div>
      </motion.div>

      <motion.div variants={fadeUp} className="text-center px-4 mb-10">
        <h1 className="text-4xl md:text-5xl font-bold mb-4">Simple, Transparent Pricing</h1>
        <p className="text-muted-foreground max-w-lg mx-auto">
          All plans include 7-day free trial. No credit card required. Cancel anytime.
        </p>
        <div className="flex items-center justify-center gap-3 mt-6">
          <span className={cn("text-sm", !yearly && "text-foreground font-medium")}>Monthly</span>
          <button
            onClick={() => setYearly(!yearly)}
            className={cn(
              "h-6 w-11 rounded-full relative transition-colors",
              yearly ? "bg-accent-blue" : "bg-muted",
            )}
          >
            <div
              className={cn(
                "h-5 w-5 rounded-full bg-white absolute top-0.5 transition-all",
                yearly ? "left-5" : "left-0.5",
              )}
            />
          </button>
          <span className={cn("text-sm", yearly && "text-foreground font-medium")}>
            Yearly <span className="text-profit text-xs">Save 20%</span>
          </span>
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
                    {yearly ? plan.yearly : plan.monthly}
                    <span className="text-base font-normal text-muted-foreground">/mo</span>
                  </div>
                  {yearly && (
                    <p className="text-xs text-profit mt-1">
                      Billed {"₹"}
                      {plan.yearly * 12}/year
                    </p>
                  )}
                </div>
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
                            ) : (
                              <span className="font-medium">
                                {String(val)}
                                {row.key === "strategies" ? "+" : ""}
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
