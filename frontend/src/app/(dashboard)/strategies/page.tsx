"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  Bot,
  AlertTriangle,
  RefreshCw,
  Plus,
  Sparkles,
  Layers,
  Clock,
  PlayCircle,
  ShieldCheck,
  Activity,
  FileCode2,
} from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AnimatedNumber } from "@/components/ui/animated-number";
import {
  ModeSelector,
  STRATEGY_MODE_STORAGE_KEY,
  type StrategyMode,
} from "@/components/strategies/mode-selector";
import { TrustScoreBadge } from "@/components/strategies/trust-score-badge";
import { KillSwitchSummary } from "@/components/strategies/kill-switch-summary";
import { StrategyActionsMenu } from "@/components/strategies/strategy-actions-menu";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

const stagger = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.05 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

/**
 * Phase 5 backend response shape (``GET /api/strategies``).
 *
 * ``strategy_json`` is the user-built DSL blob. Legacy rows (created
 * before Phase 5) carry ``null`` here and get a "not rated" trust
 * badge plus a placeholder indicators count.
 */
interface Strategy {
  id: string;
  name: string;
  is_active: boolean;
  strategy_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

interface StrategyListResponse {
  strategies: Strategy[];
  count: number;
}

export default function StrategiesPage() {
  const router = useRouter();
  const { data, isLoading, error, refetch } = useApi<StrategyListResponse>(
    "/strategies",
    null,
    60_000,
  );
  const [mode, setMode] = useState<StrategyMode>("beginner");

  const strategies = data?.strategies ?? [];
  // Single ``refetch`` reference threaded into every action menu so a
  // Duplicate/Archive/Delete updates the list without a manual refresh.
  const handleChanged = refetch;

  function handleCreate() {
    // ``mode`` lags one render behind localStorage on first paint
    // (ModeSelector hydrates in useEffect and only calls onChange on
    // user click), so read the persisted key directly. Selector state
    // is the secondary source, "beginner" the final fallback.
    const persisted =
      typeof window !== "undefined"
        ? window.localStorage.getItem(STRATEGY_MODE_STORAGE_KEY)
        : null;
    const target: StrategyMode =
      persisted === "beginner" ||
      persisted === "intermediate" ||
      persisted === "expert"
        ? persisted
        : mode;
    router.push(`/strategies/new/${target}`);
  }

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="p-4 md:p-6 lg:p-8 max-w-5xl mx-auto space-y-6"
    >
      {/* ── Header ───────────────────────────────────────────────────── */}
      <motion.div variants={fadeUp} className="space-y-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Bot className="h-6 w-6 text-accent-blue" /> Strategies
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Build, backtest, and deploy. Auto-refresh every 60s.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={refetch} type="button">
              <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
              Refresh
            </Button>
            <Button
              variant="outline"
              size="sm"
              type="button"
              onClick={() => router.push("/strategies/import-pine")}
            >
              <FileCode2 className="h-4 w-4" />
              Import Pine Script
            </Button>
            <GlowButton size="sm" onClick={handleCreate}>
              <Plus className="h-4 w-4 mr-2" />
              Create New Strategy
            </GlowButton>
          </div>
        </div>
        <ModeSelector value={mode} onChange={setMode} />
      </motion.div>

      {/* ── Hero stats (animated count-ups) ──────────────────────── */}
      <motion.div variants={fadeUp}>
        <HeroStats strategies={strategies} />
      </motion.div>

      {/* ── Kill Switch summary (read-only, links to /kill-switch) ─── */}
      <motion.div variants={fadeUp}>
        <KillSwitchSummary />
      </motion.div>

      {/* ── Strategies list ──────────────────────────────────────── */}
      {error && !data ? (
        <motion.div variants={fadeUp}>
          <GlassmorphismCard hover={false}>
            <div className="text-center py-8">
              <AlertTriangle className="h-10 w-10 text-loss mx-auto mb-3" />
              <h3 className="font-semibold mb-1">Could not load strategies</h3>
              <p className="text-sm text-muted-foreground mb-4">{error}</p>
              <GlowButton onClick={refetch} size="sm">
                Retry
              </GlowButton>
            </div>
          </GlassmorphismCard>
        </motion.div>
      ) : isLoading && !data ? (
        <motion.div variants={fadeUp} className="space-y-4">
          {[0, 1].map((i) => (
            <GlassmorphismCard key={i} hover={false}>
              <div className="animate-pulse space-y-3">
                <div className="h-5 w-1/3 bg-white/[0.05] rounded" />
                <div className="h-3 w-1/2 bg-white/[0.04] rounded" />
                <div className="h-3 w-2/3 bg-white/[0.04] rounded" />
              </div>
            </GlassmorphismCard>
          ))}
        </motion.div>
      ) : strategies.length === 0 ? (
        <motion.div variants={fadeUp}>
          <GlassmorphismCard hover={false}>
            <div className="text-center py-12 max-w-md mx-auto space-y-4">
              <div className="text-5xl" aria-hidden="true">
                🚀
              </div>
              <h3 className="font-semibold text-lg">
                Apni pehli strategy banao
              </h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Backtest karo, Trust Score paao, paper trade karo, phir
                live jao.
              </p>
              <div className="pt-2">
                <GlowButton size="sm" onClick={handleCreate}>
                  <Plus className="h-4 w-4 mr-2" />
                  Create New Strategy
                </GlowButton>
              </div>
            </div>
          </GlassmorphismCard>
        </motion.div>
      ) : (
        <motion.div variants={fadeUp} className="space-y-4">
          {strategies.map((strategy) => (
            <StrategyCard
              key={strategy.id}
              strategy={strategy}
              mode={mode}
              onChanged={handleChanged}
            />
          ))}
        </motion.div>
      )}
    </motion.div>
  );
}

// ─── Strategy card ─────────────────────────────────────────────────────


interface StrategyCardProps {
  strategy: Strategy;
  mode: StrategyMode;
  onChanged: () => void;
}

function StrategyCard({ strategy, mode, onChanged }: StrategyCardProps) {
  const indicatorCount = countIndicators(strategy.strategy_json);
  const updated = formatDate(strategy.updated_at);

  return (
    <motion.div
      whileHover={{ y: -3, scale: 1.005 }}
      transition={{ type: "spring", stiffness: 320, damping: 22 }}
    >
      <GlassmorphismCard hover={false}>
      <div className="space-y-4">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold truncate">{strategy.name}</h2>
            <p className="text-xs text-muted-foreground font-mono mt-0.5">
              {strategy.id}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <TrustScoreBadge strategyJson={strategy.strategy_json} pulseOnA />
            <Badge
              className={cn(
                "uppercase text-xs",
                strategy.is_active
                  ? "bg-profit/15 text-profit border-profit/30"
                  : "bg-muted text-muted-foreground border-border",
              )}
            >
              {strategy.is_active ? "Active" : "Inactive"}
            </Badge>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wide">
              Indicators
            </div>
            <div className="mt-1 font-medium flex items-center gap-1">
              <Layers className="h-3.5 w-3.5 text-accent-blue" />
              {indicatorCount === null ? "—" : `${indicatorCount} configured`}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wide">
              Status
            </div>
            <div className="mt-1 font-medium flex items-center gap-1">
              <Sparkles
                className={cn(
                  "h-3.5 w-3.5",
                  strategy.strategy_json
                    ? "text-profit"
                    : "text-muted-foreground",
                )}
              />
              {strategy.strategy_json ? "DSL ready" : "Legacy / no DSL"}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wide">
              Updated
            </div>
            <div className="mt-1 font-medium flex items-center gap-1">
              <Clock className="h-3.5 w-3.5 text-muted-foreground" />
              {updated}
            </div>
          </div>
        </div>

        {mode === "beginner" && !strategy.strategy_json ? (
          <div className="rounded-lg bg-white/[0.02] border border-white/[0.04] p-3 text-xs text-muted-foreground leading-relaxed">
            This strategy was created before the new builder. Migrate it
            via the upcoming Wednesday builder to get backtest, trust,
            and truth scoring.
          </div>
        ) : null}

        <StrategyCardActions
          strategy={strategy}
          mode={mode}
          onChanged={onChanged}
        />
      </div>
      </GlassmorphismCard>
    </motion.div>
  );
}


// ─── Per-card action buttons (Backtest + 3-dot menu) ─────────────────


function StrategyCardActions({
  strategy,
  mode,
  onChanged,
}: {
  strategy: Strategy;
  mode: StrategyMode;
  onChanged: () => void;
}) {
  const canBacktest = !!strategy.strategy_json;
  const backtestLabel = mode === "beginner" ? "Run Backtest" : "View Backtest";

  return (
    <div className="flex items-center justify-end gap-2 flex-wrap">
      {canBacktest ? (
        <Link
          href={`/strategies/${strategy.id}/backtest`}
          className={cn(
            "inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md",
            "bg-accent-blue/15 border border-accent-blue/30 text-accent-blue",
            "hover:bg-accent-blue/25 transition-colors font-medium",
          )}
        >
          <PlayCircle className="h-3.5 w-3.5" />
          {backtestLabel}
        </Link>
      ) : (
        <Button variant="outline" size="sm" disabled type="button">
          <PlayCircle className="h-4 w-4" />
          Backtest unavailable (no DSL)
        </Button>
      )}
      <StrategyActionsMenu
        strategy={strategy}
        variant="card"
        onChanged={onChanged}
      />
    </div>
  );
}

// ─── Hero stats ────────────────────────────────────────────────────────


/**
 * Three animated count-up cards above the strategy list.
 *
 *   * "Saved Strategies"  — ``strategies.length``
 *   * "Backtest Ready"    — strategies with a ``strategy_json`` blob
 *                           (proxy for "runnable" until backtest history
 *                           lands as its own endpoint)
 *   * "Avg Trust"         — mean of ``trust_score`` across strategies
 *                           that carry one; "—" when the population is
 *                           empty (placeholder per spec)
 */
function HeroStats({ strategies }: { strategies: Strategy[] }) {
  const saved = strategies.length;
  const backtestReady = strategies.filter((s) => !!s.strategy_json).length;
  const trustScores = strategies
    .map((s) => extractTrustScore(s.strategy_json))
    .filter((n): n is number => n !== null);
  const avgTrust = trustScores.length
    ? Math.round(trustScores.reduce((a, b) => a + b, 0) / trustScores.length)
    : null;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      <StatCard
        icon={<Bot className="h-4 w-4 text-accent-blue" />}
        label="Saved Strategies"
        value={saved}
      />
      <StatCard
        icon={<Activity className="h-4 w-4 text-accent-blue" />}
        label="Backtest Ready"
        value={backtestReady}
        helper={
          saved === 0
            ? "Save karo, phir backtest"
            : `${backtestReady}/${saved} ready`
        }
      />
      <StatCard
        icon={<ShieldCheck className="h-4 w-4 text-accent-blue" />}
        label="Avg Trust Score"
        value={avgTrust}
        helper={
          avgTrust === null ? "Backtest karne ke baad milega" : "out of 100"
        }
        emphasizeGradeA={avgTrust !== null && avgTrust >= 90}
      />
    </div>
  );
}


interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: number | null;
  helper?: string;
  emphasizeGradeA?: boolean;
}


function StatCard({
  icon,
  label,
  value,
  helper,
  emphasizeGradeA = false,
}: StatCardProps) {
  return (
    <GlassmorphismCard
      hover={false}
      className={cn(
        "gradient-border-stat",
        emphasizeGradeA && "pulse-grade-a",
      )}
    >
      <div className="space-y-1.5">
        <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-muted-foreground">
          {icon}
          {label}
        </div>
        <div className="text-3xl font-bold tabular-nums">
          {value === null ? (
            <span className="text-muted-foreground/60">—</span>
          ) : (
            <AnimatedNumber value={value} duration={1.5} decimals={0} />
          )}
        </div>
        {helper ? (
          <p className="text-[11px] text-muted-foreground">{helper}</p>
        ) : null}
      </div>
    </GlassmorphismCard>
  );
}


/**
 * Lifted from ``trust-score-badge.tsx`` so the hero stat card can pick
 * up the same numeric extraction without a circular import. Kept as a
 * local helper rather than re-exporting so the badge stays the canonical
 * consumer of this shape.
 */
function extractTrustScore(blob: Record<string, unknown> | null): number | null {
  if (!blob) return null;
  const raw = blob["trust_score"];
  if (typeof raw === "number" && Number.isFinite(raw)) {
    return Math.max(0, Math.min(100, Math.round(raw)));
  }
  const nested = blob["reliability"];
  if (nested && typeof nested === "object") {
    const n = (nested as Record<string, unknown>)["trust_score"];
    if (typeof n === "number" && Number.isFinite(n)) {
      return Math.max(0, Math.min(100, Math.round(n)));
    }
  }
  return null;
}


// ─── Helpers ───────────────────────────────────────────────────────────


function countIndicators(blob: Record<string, unknown> | null): number | null {
  if (!blob) return null;
  const raw = blob["indicators"];
  if (Array.isArray(raw)) return raw.length;
  return null;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-IN", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return "—";
  }
}
