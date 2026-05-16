/**
 * MetricsHeader — dense report-card grid for the Phase B strategy
 * tester metrics. Mirrors the visual conventions of
 * :mod:`@/components/strategies/backtest-result-panel` (Stat tile
 * pattern, ``text-profit``/``text-loss`` colour tokens,
 * ``tabular-nums``) but reads directly from the Phase B aggregator
 * response shape (snake_case → camelCase parse upstream in the hook).
 *
 * Null handling:
 *   - ``profitFactor === null`` → render ``∞`` (no losers; ratio is
 *     mathematically infinite per backend doc).
 *   - ``sharpeRatioProxy === null`` → render ``—`` (fewer than 2
 *     closed trades OR zero variance). Labelled "Sharpe (per-trade)"
 *     because the backend's proxy is NOT annualised.
 */

"use client";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { cn } from "@/lib/utils";
import type { StrategyTesterMetrics } from "@/lib/strategy-tester/types";

interface MetricsHeaderProps {
  metrics: StrategyTesterMetrics;
  className?: string;
}

export function MetricsHeader({ metrics, className }: MetricsHeaderProps) {
  const isProfit = metrics.totalPnl >= 0;

  return (
    <div
      data-testid="metrics-header"
      className={cn(
        "grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3",
        className,
      )}
    >
      <Stat
        label="Total P&L"
        value={formatRupee(metrics.totalPnl, true)}
        accent={isProfit ? "profit" : "loss"}
      />
      <Stat
        label="Win Rate"
        value={`${metrics.winRatePct.toFixed(1)}%`}
      />
      <Stat
        label="Profit Factor"
        value={formatProfitFactor(metrics.profitFactor)}
      />
      <Stat
        label="Trades"
        value={`${metrics.totalTrades}`}
      />
      <Stat
        label="Max Drawdown"
        value={`${metrics.maxDrawdownPct.toFixed(1)}%`}
        accent={metrics.maxDrawdownPct > 20 ? "loss" : "neutral"}
      />
      <Stat
        label="Sharpe (per-trade)"
        value={
          metrics.sharpeRatioProxy === null
            ? "—"
            : metrics.sharpeRatioProxy.toFixed(2)
        }
      />
      <Stat
        label="Expectancy"
        value={formatRupee(metrics.expectancy, true)}
        accent={metrics.expectancy >= 0 ? "profit" : "loss"}
      />
      <Stat
        label="Avg Win"
        value={formatRupee(metrics.avgWin, false)}
      />
      <Stat
        label="Avg Loss"
        value={formatRupee(metrics.avgLoss, false)}
      />
      <Stat
        label="Largest Win"
        value={formatRupee(metrics.largestWin, false)}
        accent="profit"
      />
      <Stat
        label="Largest Loss"
        value={formatRupee(metrics.largestLoss, false)}
        accent="loss"
      />
      <Stat
        label="Profitable"
        value={`${metrics.profitableTrades}/${metrics.totalTrades}`}
      />
    </div>
  );
}

// ─── Stat tile ────────────────────────────────────────────────────────

function Stat({
  label,
  value,
  accent = "neutral",
}: {
  label: string;
  value: string;
  accent?: "profit" | "loss" | "neutral";
}) {
  return (
    <GlassmorphismCard hover={false} className="!p-3">
      <div className="text-[11px] text-muted-foreground uppercase tracking-wide">
        {label}
      </div>
      <div
        className={cn(
          "mt-1 text-base font-semibold tabular-nums",
          accent === "profit" && "text-profit",
          accent === "loss" && "text-loss",
        )}
      >
        {value}
      </div>
    </GlassmorphismCard>
  );
}

// ─── Formatters ───────────────────────────────────────────────────────

function formatRupee(value: number, withSign: boolean): string {
  const sign = value > 0 && withSign ? "+" : value < 0 ? "-" : "";
  const magnitude = Math.abs(value).toLocaleString("en-IN", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  });
  return `${sign}₹${magnitude}`;
}

function formatProfitFactor(pf: number | null): string {
  if (pf === null) return "∞";
  if (!Number.isFinite(pf)) return "∞";
  return `${pf.toFixed(2)}x`;
}
