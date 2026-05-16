/**
 * StrategyTesterPanel — Phase D top-level component.
 *
 * Composes three sub-views vertically:
 *   1. ``<MetricsHeader />``     — report-card stats grid
 *   2. ``<EquityCurveChart />``  — recharts area chart
 *   3. ``<TradeListTable />``    — sortable trade log
 *
 * Drives them from a single :func:`useStrategyTester` invocation —
 * one ``(strategyId, mode)`` pair, three endpoints fetched in
 * parallel. The panel owns loading / empty / error rendering so the
 * sub-components remain pure presenters.
 *
 * The ``mode`` prop is currently caller-supplied; a mode toggle UI is
 * deferred to the next phase (see PATCH_INSTRUCTIONS_PHASE_D.md).
 */

"use client";

import { AlertCircle, RotateCw } from "lucide-react";

import { EquityCurveChart } from "@/components/strategy-tester/EquityCurveChart";
import { MetricsHeader } from "@/components/strategy-tester/MetricsHeader";
import { TradeListTable } from "@/components/strategy-tester/TradeListTable";
import { Badge } from "@/components/ui/badge";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { useStrategyTester } from "@/hooks/useStrategyTester";
import { cn } from "@/lib/utils";
import type { Mode } from "@/lib/strategy-tester/types";

export interface StrategyTesterPanelProps {
  strategyId: string;
  mode: Mode;
  /** ISO 8601 with tz offset. ``null`` = no lower bound. */
  fromIso?: string | null;
  /** ISO 8601 with tz offset. ``null`` = no upper bound. */
  toIso?: string | null;
  /** Override of the backend's default 100000 starting equity. */
  startingEquity?: number;
  /** Trade-list page size. Backend default 100, max 500. */
  tradeLimit?: number;
  className?: string;
}

export function StrategyTesterPanel(props: StrategyTesterPanelProps) {
  const {
    strategyId,
    mode,
    fromIso,
    toIso,
    startingEquity,
    tradeLimit,
    className,
  } = props;

  const { metrics, equity, trades, isLoading, hasLoaded, error, refetch } =
    useStrategyTester({
      strategyId,
      mode,
      fromIso,
      toIso,
      startingEquity,
      limit: tradeLimit,
    });

  return (
    <div
      data-testid="strategy-tester-panel"
      className={cn("space-y-4", className)}
    >
      <PanelHeader mode={mode} isLoading={isLoading} onRefetch={refetch} />

      {error ? (
        <ErrorBanner message={error.message} onRetry={refetch} />
      ) : null}

      {!hasLoaded && isLoading ? (
        <LoadingSkeleton />
      ) : (
        <>
          {metrics ? (
            <MetricsHeader metrics={metrics} />
          ) : (
            <EmptyMetricsState />
          )}
          <EquityCurveChart equity={equity} />
          <TradeListTable trades={trades?.trades ?? []} />
        </>
      )}
    </div>
  );
}

// ─── Header ───────────────────────────────────────────────────────────

function PanelHeader({
  mode,
  isLoading,
  onRefetch,
}: {
  mode: Mode;
  isLoading: boolean;
  onRefetch: () => void;
}) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <h2 className="text-base font-semibold">Strategy Tester</h2>
        <Badge
          className={cn(
            "border",
            mode === "LIVE" &&
              "bg-loss/10 border-loss/30 text-loss",
            mode === "PAPER" &&
              "bg-accent-blue/10 border-accent-blue/30 text-accent-blue",
            mode === "BACKTEST" &&
              "bg-white/[0.03] border-white/[0.06] text-muted-foreground",
          )}
        >
          {mode}
        </Badge>
      </div>
      <button
        type="button"
        onClick={onRefetch}
        disabled={isLoading}
        aria-label="Refresh"
        className={cn(
          "p-1.5 rounded border border-white/[0.06] bg-white/[0.02]",
          "hover:bg-white/[0.05] disabled:opacity-40 transition-colors",
        )}
      >
        <RotateCw
          className={cn("h-4 w-4", isLoading && "animate-spin")}
        />
      </button>
    </div>
  );
}

// ─── States ───────────────────────────────────────────────────────────

function ErrorBanner({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <GlassmorphismCard
      hover={false}
      className="border-loss/30 bg-loss/[0.04]"
    >
      <div className="flex items-start gap-2">
        <AlertCircle className="h-4 w-4 text-loss mt-0.5 shrink-0" />
        <div className="flex-1 text-sm">
          <p className="font-semibold text-loss">Failed to load data</p>
          <p className="text-muted-foreground text-xs mt-1">{message}</p>
        </div>
        <button
          type="button"
          onClick={onRetry}
          className="text-xs px-2 py-1 rounded border border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.05]"
        >
          Retry
        </button>
      </div>
    </GlassmorphismCard>
  );
}

function LoadingSkeleton() {
  return (
    <div data-testid="strategy-tester-skeleton" className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="rounded-xl bg-white/[0.03] border border-white/[0.06] p-3 h-[68px] animate-pulse"
          />
        ))}
      </div>
      <div className="rounded-xl bg-white/[0.03] border border-white/[0.06] h-[280px] animate-pulse" />
      <div className="rounded-xl bg-white/[0.03] border border-white/[0.06] h-[200px] animate-pulse" />
    </div>
  );
}

function EmptyMetricsState() {
  return (
    <GlassmorphismCard hover={false}>
      <p
        data-testid="metrics-empty-state"
        className="text-xs text-muted-foreground text-center py-8"
      >
        No metrics yet for this strategy.
      </p>
    </GlassmorphismCard>
  );
}
