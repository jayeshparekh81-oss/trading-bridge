"use client";

import { useState } from "react";
import Link from "next/link";
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
  Settings,
} from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ModeSelector, type StrategyMode } from "@/components/strategies/mode-selector";
import { TrustScoreBadge } from "@/components/strategies/trust-score-badge";
import { KillSwitchSummary } from "@/components/strategies/kill-switch-summary";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

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
  const { data, isLoading, error, refetch } = useApi<StrategyListResponse>(
    "/strategies",
    null,
    60_000,
  );
  const [mode, setMode] = useState<StrategyMode>("beginner");

  const strategies = data?.strategies ?? [];

  function handleCreate() {
    toast.info(
      "Strategy builder ships Wednesday. For now, POST a StrategyJSON " +
        "directly to /api/strategies via the API.",
    );
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
            <GlowButton size="sm" onClick={handleCreate}>
              <Plus className="h-4 w-4 mr-2" />
              Create New Strategy
            </GlowButton>
          </div>
        </div>
        <ModeSelector value={mode} onChange={setMode} />
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
            <div className="text-center py-12">
              <Bot className="h-12 w-12 text-muted-foreground mx-auto mb-3 opacity-50" />
              <h3 className="font-semibold mb-1">No strategies yet</h3>
              <p className="text-sm text-muted-foreground max-w-sm mx-auto mb-4">
                Build your first strategy and run a backtest before going live.
              </p>
              <GlowButton size="sm" onClick={handleCreate}>
                <Plus className="h-4 w-4 mr-2" />
                Create New Strategy
              </GlowButton>
            </div>
          </GlassmorphismCard>
        </motion.div>
      ) : (
        <motion.div variants={fadeUp} className="space-y-4">
          {strategies.map((strategy) => (
            <StrategyCard key={strategy.id} strategy={strategy} mode={mode} />
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
}

function StrategyCard({ strategy, mode }: StrategyCardProps) {
  const indicatorCount = countIndicators(strategy.strategy_json);
  const updated = formatDate(strategy.updated_at);

  return (
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
            <TrustScoreBadge strategyJson={strategy.strategy_json} />
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

        <StrategyCardActions strategy={strategy} mode={mode} />
      </div>
    </GlassmorphismCard>
  );
}


// ─── Per-card action buttons (View Backtest / Configure) ─────────────


function StrategyCardActions({
  strategy,
  mode,
}: {
  strategy: Strategy;
  mode: StrategyMode;
}) {
  const canBacktest = !!strategy.strategy_json;
  const backtestLabel = mode === "beginner" ? "Run Backtest" : "View Backtest";

  function handleConfigure() {
    toast.info("Strategy configure flow ships with the Wednesday builder.");
  }

  if (!canBacktest) {
    return (
      <div className="flex items-center justify-end">
        <Button variant="outline" size="sm" disabled type="button">
          <PlayCircle className="h-4 w-4" />
          Backtest unavailable (no DSL)
        </Button>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-end gap-2 flex-wrap">
      {mode === "expert" ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={handleConfigure}
          type="button"
        >
          <Settings className="h-4 w-4" />
          Configure
        </Button>
      ) : null}
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
    </div>
  );
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
