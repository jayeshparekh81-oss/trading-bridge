"use client";

/**
 * DRAFT customer-facing strategy showcase. Honest, size-independent backtest
 * metrics + 4-state live labelling (see SHOWCASE_BACKEND_DESIGN.md).
 *
 * Honesty guardrails baked in:
 *  - Every strategy labelled "In-sample backtest — not a guarantee".
 *  - NO compounded totals, NO INR P&L, NO cumulative-return curve (F3).
 *  - NO live P&L numbers (none reconciled yet) — only the tracking note (F1).
 *  - Live-status: BSE = LIVE (real), CDSL = FORWARD-TEST (paper), ANGELONE = PAPER.
 *
 * DRAFT for review — not wired to the prod data pipeline (reads a copied static
 * artifact). Not deployed.
 */
import { motion } from "framer-motion";
import { Activity, TrendingUp, Gauge, ArrowDownRight, Hash, Info } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { cn } from "@/lib/utils";
import {
  showcaseStrategies,
  showcaseCaveats,
  showcaseVersion,
  LIVE_BADGE,
  type ShowcaseStrategy,
} from "@/lib/showcase/data";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

const pct = (v: number, sign = false) => `${sign && v > 0 ? "+" : ""}${v.toFixed(2)}%`;
const num = (v: number) => v.toLocaleString("en-IN");

const TONE: Record<"profit" | "gold" | "muted", string> = {
  profit: "text-profit bg-profit/10 border-profit/25",
  gold: "text-accent-gold bg-accent-gold/10 border-accent-gold/25",
  muted: "text-muted-foreground bg-muted/40 border-border",
};

// Per-state tracking note — honest per the live-status (PAPER is NOT live-tracked).
const trackingNote = (t: ShowcaseStrategy["live_status"]["track_type"]) =>
  t === "PAPER"
    ? "Paper / backtest-only candidate — not deployed live. No real-money results exist."
    : "Live forward-tracking is being recorded; results will be published as they accumulate. No live P&L is shown yet — none reconciled.";

function MetricTile({
  icon: Icon,
  label,
  value,
  tone = "text-foreground",
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-white/[0.02] p-3">
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className={cn("mt-1.5 text-xl font-bold font-mono tabular-nums tracking-tight", tone)}>
        {value}
      </div>
    </div>
  );
}

function StrategyCard({ s }: { s: ShowcaseStrategy }) {
  const m = s.backtest.metrics;
  const live = LIVE_BADGE[s.live_status.track_type];
  return (
    <motion.div variants={fadeUp}>
      <GlassmorphismCard hover={false} className="h-full">
        {/* Header: instrument + live-status badge */}
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold">{s.display_name}</h3>
            <p className="text-xs text-muted-foreground font-mono">{s.instrument}</p>
          </div>
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold",
              TONE[live.tone],
            )}
          >
            <span className={cn("h-1.5 w-1.5 rounded-full", live.dot)} />
            {live.text}
          </span>
        </div>

        {/* In-sample disclaimer — on every strategy */}
        <div className="mt-3 flex items-center gap-1.5 rounded-md bg-accent-blue/[0.07] border border-accent-blue/15 px-2.5 py-1.5">
          <Info className="h-3.5 w-3.5 text-accent-blue shrink-0" />
          <p className="text-[11px] text-muted-foreground">
            <span className="text-accent-blue font-medium">In-sample backtest</span> — not a
            guarantee of live results.
          </p>
        </div>

        {/* The 5 size-independent headline metrics */}
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-2.5">
          <MetricTile icon={Activity} label="Win rate" value={pct(m.win_rate_pct)} tone="text-accent-blue" />
          <MetricTile icon={TrendingUp} label="Avg net / trade" value={pct(m.avg_net_pct_per_trade, true)} tone="text-profit" />
          <MetricTile icon={Gauge} label="Profit factor" value={m.profit_factor.toFixed(2)} tone="text-accent-gold" />
          <MetricTile icon={ArrowDownRight} label="Max drawdown" value={pct(m.max_drawdown_pct)} tone="text-loss" />
          <MetricTile icon={Hash} label="Trades (sample)" value={num(m.closed_trades)} />
          <MetricTile icon={Activity} label="In-sample" value={`${s.backtest.in_sample_range.from} → ${s.backtest.in_sample_range.to}`} tone="text-foreground text-sm" />
        </div>

        {/* Secondary context (honest, size-independent) */}
        <p className="mt-3 text-[11px] text-muted-foreground">
          {m.wins}W / {m.losses}L · longest losing streak {m.longest_losing_streak} ·
          best {pct(m.best_trade_pct, true)} / worst {pct(m.worst_trade_pct, true)} ·
          net of estimated charges (slippage excluded)
        </p>

        {/* Live-status note — NO P&L numbers (F1) */}
        <div className="mt-4 rounded-lg border border-border bg-white/[0.015] p-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold">
            <span className={cn("h-1.5 w-1.5 rounded-full", live.dot)} />
            <span className={cn(TONE[live.tone], "bg-transparent border-0 px-0")}>{live.text}</span>
            <span className="text-muted-foreground font-normal">· {live.sub}</span>
          </div>
          <p className="mt-1.5 text-[11px] text-muted-foreground leading-relaxed">
            {trackingNote(s.live_status.track_type)}
          </p>
        </div>
      </GlassmorphismCard>
    </motion.div>
  );
}

export default function ShowcasePage() {
  return (
    <div className="dark bg-background text-foreground min-h-screen">
      <motion.div variants={stagger} initial="hidden" animate="show" className="pt-24 pb-16">
        {/* DRAFT ribbon */}
        <motion.div variants={fadeUp} className="text-center px-4 mb-4">
          <span className="inline-block px-3 py-1 rounded-full bg-accent-gold/10 text-accent-gold text-xs font-semibold">
            DRAFT — for review · not final
          </span>
        </motion.div>

        {/* Header */}
        <motion.div variants={fadeUp} className="text-center px-4 mb-6">
          <h1 className="text-4xl md:text-5xl font-bold mb-3">Strategy Performance</h1>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            Honest, size-independent backtest results — measured per trade, never compounded.
            Live forward-tracking is published as it accumulates.
          </p>
          <p className="text-xs text-muted-foreground/70 mt-2 font-mono">
            v{showcaseVersion} · in-sample backtest
          </p>
        </motion.div>

        {/* Global honesty banner */}
        <motion.div variants={fadeUp} className="max-w-5xl mx-auto px-4 mb-8">
          <div className="rounded-xl border border-accent-blue/20 bg-accent-blue/[0.06] px-4 py-3 flex items-start gap-2.5">
            <Info className="h-4 w-4 text-accent-blue shrink-0 mt-0.5" />
            <p className="text-xs text-muted-foreground leading-relaxed">
              These are <span className="text-foreground font-medium">in-sample backtests</span> — a
              hypothesis about edge, <span className="text-foreground font-medium">not a guarantee of
              future results</span>. Figures are size-independent per-trade metrics, net of estimated
              charges (slippage excluded). We deliberately do <span className="text-foreground font-medium">not</span> show
              compounded totals or rupee P&amp;L. Backtest is separate from live — live/forward records
              are shown only as they are reconciled.
            </p>
          </div>
        </motion.div>

        {/* Per-strategy cards */}
        <div className="max-w-5xl mx-auto px-4 grid md:grid-cols-3 gap-5">
          {showcaseStrategies.map((s) => (
            <StrategyCard key={s.key} s={s} />
          ))}
        </div>

        {/* Caveats */}
        <motion.div variants={fadeUp} className="max-w-5xl mx-auto px-4 mt-10">
          <GlassmorphismCard hover={false}>
            <h2 className="text-sm font-semibold mb-3 flex items-center gap-1.5">
              <Info className="h-4 w-4 text-muted-foreground" /> How to read these numbers
            </h2>
            <ul className="space-y-1.5">
              {showcaseCaveats.map((c, i) => (
                <li key={i} className="text-xs text-muted-foreground flex gap-2">
                  <span className="text-accent-blue/60">•</span>
                  {c}
                </li>
              ))}
            </ul>
          </GlassmorphismCard>
        </motion.div>
      </motion.div>
    </div>
  );
}
