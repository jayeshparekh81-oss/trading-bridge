"use client";

/**
 * Two-Door entry for "Create new strategy".
 *
 * Replaces the previous smart-default redirector. The old behaviour
 * silently routed users to /strategies/new/{beginner,intermediate,expert}
 * based on ``localStorage["tb_strategy_mode"]`` (last-used mode) or a
 * count heuristic — which meant a returning power user landed straight
 * in the 230-indicator Expert screen, but a brand-new user could too if
 * the storage key got set by other UI surfaces.
 *
 * This page asks one question — "How do you want to start?" — and offers
 * four doors:
 *
 *   * "Use a proven strategy" → /marketplace (visually emphasized,
 *     marked recommended for first-timers — the only accented card).
 *   * "Build my own" → existing beginner builder
 *     (/strategies/new/beginner).
 *   * "Intermediate" → /strategies/new/intermediate.
 *   * "Expert" → /strategies/new/expert.
 *
 * Direct routes /strategies/new/{beginner,intermediate,expert} still
 * work for explicit navigation (e.g. the mode selector in builders) and
 * ``?edit=<id>`` deep links continue to land on
 * /strategies/new/expert?edit=<id> as before — that path never went
 * through this redirector even in the old design (see
 * src/components/strategies/strategy-actions-menu.tsx).
 */

import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowRight,
  ArrowLeft,
  Code2,
  SlidersHorizontal,
  Sparkles,
  Store,
  Wrench,
} from "lucide-react";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { cn } from "@/lib/utils";

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.25 } },
};

interface DoorProps {
  href: string;
  icon: typeof Store;
  eyebrow?: string;
  title: string;
  blurb: string;
  cta: string;
  recommended?: boolean;
  testId: string;
}

function Door({
  href,
  icon: Icon,
  eyebrow,
  title,
  blurb,
  cta,
  recommended,
  testId,
}: DoorProps) {
  return (
    <Link
      href={href}
      data-testid={testId}
      className={cn(
        "group block focus-visible:outline-none focus-visible:ring-2",
        "focus-visible:ring-accent-blue/40 rounded-2xl",
      )}
    >
      <GlassmorphismCard
        hover
        className={cn(
          "relative h-full p-6 md:p-7 transition-all",
          recommended
            ? "border-emerald-400/40 ring-1 ring-emerald-400/20 shadow-[0_0_45px_-12px_rgba(52,211,153,0.35)]"
            : "border-white/[0.06]",
        )}
      >
        {recommended ? (
          <span
            className={cn(
              "absolute -top-2 left-6 inline-flex items-center gap-1",
              "rounded-full border border-emerald-400/40 bg-emerald-400/15",
              "px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
              "text-emerald-300",
            )}
          >
            <Sparkles className="h-3 w-3" />
            Recommended for first-timers
          </span>
        ) : null}
        <div className="flex items-start gap-4">
          <span
            className={cn(
              "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl",
              recommended
                ? "bg-emerald-400/15 text-emerald-300"
                : "bg-accent-blue/15 text-accent-blue",
            )}
          >
            <Icon className="h-5 w-5" />
          </span>
          <div className="space-y-1">
            {eyebrow ? (
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {eyebrow}
              </p>
            ) : null}
            <h2 className="text-lg font-semibold leading-tight">{title}</h2>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {blurb}
            </p>
          </div>
        </div>
        <div
          className={cn(
            "mt-6 inline-flex items-center gap-1.5 text-sm font-medium",
            recommended ? "text-emerald-300" : "text-accent-blue",
            "group-hover:gap-2.5 transition-all",
          )}
        >
          {cta}
          <ArrowRight className="h-4 w-4" />
        </div>
      </GlassmorphismCard>
    </Link>
  );
}

export default function StrategiesNewEntryPage() {
  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={fadeUp}
      className="p-4 md:p-6 lg:p-8 max-w-4xl mx-auto space-y-6"
    >
      <div className="space-y-2">
        <Link
          href="/strategies"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-3 w-3" />
          Back to strategies
        </Link>
        <h1 className="text-2xl md:text-3xl font-bold">
          How do you want to start?
        </h1>
        <p className="text-sm md:text-base text-muted-foreground max-w-2xl">
          Pick a battle-tested strategy from the marketplace, or build your
          own from scratch with a simple step-by-step wizard.
        </p>
      </div>

      <div
        role="group"
        aria-label="Strategy creation entry"
        className="grid gap-4 md:gap-6 sm:grid-cols-2"
      >
        <Door
          testId="two-door-marketplace"
          href="/marketplace"
          icon={Store}
          eyebrow="Fastest path"
          title="Use a proven strategy"
          blurb="Browse strategies that are already running. Clone one with a click and tune later."
          cta="Browse marketplace"
          recommended
        />
        <Door
          testId="two-door-build"
          href="/strategies/new/beginner"
          icon={Wrench}
          eyebrow="Hands on"
          title="Build my own"
          blurb="5 simple steps. Pick a goal, set risk, name it, run a backtest. No jargon."
          cta="Open beginner builder"
        />
        <Door
          testId="two-door-intermediate"
          href="/strategies/new/intermediate"
          icon={SlidersHorizontal}
          eyebrow="More control"
          title="Intermediate"
          blurb="Pick your own indicators, with guardrails."
          cta="Open intermediate builder"
        />
        <Door
          testId="two-door-expert"
          href="/strategies/new/expert"
          icon={Code2}
          eyebrow="Full control"
          title="Expert"
          blurb="Full DSL — bring your own conditions."
          cta="Open expert builder"
        />
      </div>
    </motion.div>
  );
}
