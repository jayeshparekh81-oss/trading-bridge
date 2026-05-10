"use client";

/**
 * Strategy detail placeholder.
 *
 * Renders identity (name, status, indicator count, timestamps) plus a
 * "View Backtest" link to the existing ``/strategies/[id]/backtest``
 * page. The Edit affordance is intentionally a toast for now — the
 * three new builder routes (``/new/{beginner|intermediate|expert}``)
 * always create a fresh strategy id; in-place editing is a separate
 * phase that needs PUT-on-existing wiring.
 */

import { use, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Bot,
  AlertTriangle,
  ArrowLeft,
  Layers,
  Clock,
  Sparkles,
  PlayCircle,
  Pencil,
  Rocket,
} from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { TrustScoreBadge } from "@/components/strategies/trust-score-badge";
import { VersionHistoryPanel } from "@/components/strategies/version-history-panel";
import {
  SafetyPreFlightPanel,
  type SafetyChainResult,
} from "@/components/strategies/safety-pre-flight-panel";
import { GoLiveButton } from "@/components/strategies/go-live-button";
import {
  GoLiveModal,
  type LiveOrderResult,
} from "@/components/strategies/go-live-modal";
import { OrderResultCard } from "@/components/strategies/order-result-card";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { toast } from "sonner";


interface Strategy {
  id: string;
  name: string;
  is_active: boolean;
  strategy_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.25 } },
};


export default function StrategyDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data, isLoading, error, refetch } = useApi<Strategy>(
    `/strategies/${id}`,
    null,
  );

  function handleEdit() {
    toast.info(
      "In-place edit aata hai next phase mein. Abhi ek nayi strategy bana lo.",
    );
  }

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={fadeUp}
      className="p-4 md:p-6 lg:p-8 max-w-4xl mx-auto space-y-6"
    >
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div className="space-y-1">
          <Link
            href="/strategies"
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-3 w-3" />
            Back to strategies
          </Link>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Bot className="h-6 w-6 text-accent-blue" />
            Strategy Detail
          </h1>
          <p className="text-xs text-muted-foreground font-mono">{id}</p>
        </div>
      </header>

      {error && !data ? (
        <GlassmorphismCard hover={false}>
          <div className="text-center py-10">
            <AlertTriangle className="h-10 w-10 text-loss mx-auto mb-3" />
            <h3 className="font-semibold mb-1">Strategy load nahi hui</h3>
            <p className="text-sm text-muted-foreground mb-4">{error}</p>
            <GlowButton size="sm" onClick={refetch}>
              Retry
            </GlowButton>
          </div>
        </GlassmorphismCard>
      ) : isLoading && !data ? (
        <GlassmorphismCard hover={false}>
          <div className="animate-pulse space-y-3">
            <div className="h-5 w-1/3 bg-white/[0.05] rounded" />
            <div className="h-3 w-1/2 bg-white/[0.04] rounded" />
            <div className="h-3 w-2/3 bg-white/[0.04] rounded" />
          </div>
        </GlassmorphismCard>
      ) : data ? (
        <>
          <DetailBody strategy={data} onEdit={handleEdit} />
          <VersionHistoryPanel strategyId={data.id} onChanged={refetch} />
          <LiveTradingSection strategy={data} />
        </>
      ) : null}
    </motion.div>
  );
}


function LiveTradingSection({ strategy }: { strategy: Strategy }) {
  const [preflight, setPreflight] = useState<SafetyChainResult | null>(null);
  const [preflightLoaded, setPreflightLoaded] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [latestResult, setLatestResult] = useState<LiveOrderResult | null>(null);

  function handlePreflight(result: SafetyChainResult) {
    setPreflight(result);
    setPreflightLoaded(true);
  }

  function handleResult(result: LiveOrderResult) {
    setLatestResult(result);
  }

  function handlePlaceAnother() {
    setLatestResult(null);
    setModalOpen(true);
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <Rocket className="h-4 w-4 text-accent-purple" />
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Live Trading
        </h2>
      </div>

      <SafetyPreFlightPanel
        strategyId={strategy.id}
        onResult={handlePreflight}
      />

      <div className="flex justify-end">
        <GoLiveButton
          preflight={preflight}
          isPreflightLoading={!preflightLoaded}
          onClick={() => setModalOpen(true)}
        />
      </div>

      {latestResult ? (
        <OrderResultCard
          result={latestResult}
          strategyId={strategy.id}
          onPlaceAnother={handlePlaceAnother}
        />
      ) : null}

      <GoLiveModal
        open={modalOpen}
        onOpenChange={setModalOpen}
        strategyId={strategy.id}
        strategyName={strategy.name}
        preflight={preflight}
        onResult={handleResult}
      />
    </section>
  );
}


function DetailBody({
  strategy,
  onEdit,
}: {
  strategy: Strategy;
  onEdit: () => void;
}) {
  const indicatorCount = countIndicators(strategy.strategy_json);
  const created = formatDate(strategy.created_at);
  const updated = formatDate(strategy.updated_at);
  const hasDsl = !!strategy.strategy_json;

  return (
    <>
      <GlassmorphismCard hover={false}>
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div className="min-w-0">
              <h2 className="text-lg font-semibold truncate">
                {strategy.name}
              </h2>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                Created {created}
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
            <Stat
              icon={<Layers className="h-3.5 w-3.5 text-accent-blue" />}
              label="Indicators"
              value={indicatorCount === null ? "—" : `${indicatorCount} configured`}
            />
            <Stat
              icon={
                <Sparkles
                  className={cn(
                    "h-3.5 w-3.5",
                    hasDsl ? "text-profit" : "text-muted-foreground",
                  )}
                />
              }
              label="DSL"
              value={hasDsl ? "Ready" : "Legacy / not set"}
            />
            <Stat
              icon={<Clock className="h-3.5 w-3.5 text-muted-foreground" />}
              label="Updated"
              value={updated}
            />
          </div>

          {!hasDsl ? (
            <div className="rounded-lg bg-white/[0.02] border border-white/[0.04] p-3 text-xs text-muted-foreground leading-relaxed">
              Yeh strategy Phase 5 builder se pehle bani thi. Backtest
              chalane ke liye ek nayi strategy bana lo.
            </div>
          ) : null}

          <div className="flex items-center justify-end gap-2 pt-1 flex-wrap">
            <Button variant="ghost" size="sm" onClick={onEdit} type="button">
              <Pencil className="h-3.5 w-3.5" />
              Edit
            </Button>
            {hasDsl ? (
              <Link
                href={`/strategies/${strategy.id}/backtest`}
                className={cn(
                  "inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md",
                  "bg-accent-blue/15 border border-accent-blue/30 text-accent-blue",
                  "hover:bg-accent-blue/25 transition-colors font-medium",
                )}
              >
                <PlayCircle className="h-3.5 w-3.5" />
                View Backtest
              </Link>
            ) : (
              <Button variant="outline" size="sm" disabled type="button">
                <PlayCircle className="h-3.5 w-3.5" />
                Backtest unavailable (no DSL)
              </Button>
            )}
          </div>
        </div>
      </GlassmorphismCard>
    </>
  );
}


function Stat({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div>
      <div className="text-xs text-muted-foreground uppercase tracking-wide">
        {label}
      </div>
      <div className="mt-1 font-medium flex items-center gap-1">
        {icon}
        {value}
      </div>
    </div>
  );
}


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
