"use client";

/**
 * /analytics — trade stats summary + recent-trades distribution.
 *
 * Wire: GET /api/users/me/trades/stats (existing summary)
 *      GET /api/users/me/trades       (existing paginated list)
 *
 * SCOPE NOTE: this build shows summary cards + recent-trades-window
 * distributions ONLY (computed client-side from the last 100 trades).
 * A proper full-history daily P&L aggregation needs a new backend
 * endpoint (``/me/trades/daily`` bucket-by-date) — flagged inline +
 * in QUEUE_HHH_SUMMARY for the next sprint.
 */

import { useMemo } from "react";
import { motion } from "framer-motion";
import { BarChart3, TrendingUp, TrendingDown, Activity, Trophy, AlertTriangle } from "lucide-react";

import { UpgradeWall } from "@/components/billing/upgrade-wall";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

interface TradeStats {
  total_trades: number;
  total_pnl: string;
  win_rate: number;
  avg_pnl_per_trade: string;
  best_trade_pnl: string;
  worst_trade_pnl: string;
}

interface TradeRow {
  id: string;
  symbol: string;
  side: string;
  pnl_realized: string | null;
  created_at: string | null;
  strategy_id: string | null;
}

interface TradeListResponse {
  trades: TradeRow[];
  total: number;
}

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

function rupees(s: string | null | undefined): string {
  if (!s) return "₹0";
  const n = Number.parseFloat(s);
  if (!Number.isFinite(n)) return "₹0";
  const sign = n < 0 ? "-" : n > 0 ? "+" : "";
  return `${sign}₹${Math.abs(n).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

export default function AnalyticsPage() {
  const { data: stats, isLoading: statsLoading } = useApi<TradeStats>("/users/me/trades/stats");
  const {
    data: tradesResp,
    isLoading: tradesLoading,
    paywalled: tradesPaywalled,
    paywallUrl: tradesPaywallUrl,
  } = useApi<TradeListResponse>("/users/me/trades?limit=100");

  const trades = tradesResp?.trades ?? [];

  // ─── Client-side aggregations (within the recent 100-trade window) ──
  const symbolDistribution = useMemo(() => {
    const map = new Map<string, { count: number; pnl: number }>();
    for (const t of trades) {
      const entry = map.get(t.symbol) ?? { count: 0, pnl: 0 };
      entry.count += 1;
      const pnl = Number.parseFloat(t.pnl_realized ?? "0");
      if (Number.isFinite(pnl)) entry.pnl += pnl;
      map.set(t.symbol, entry);
    }
    return [...map.entries()]
      .map(([symbol, agg]) => ({ symbol, ...agg }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [trades]);

  const equityCurve = useMemo(() => {
    // Recent trades reverse-chronological → flip and cumulate. Build the
    // cumulative series via reduce into a fresh array (no reassigned closure
    // accumulator) — identical output, satisfies react-hooks/immutability.
    const sorted = [...trades].reverse();
    return sorted.reduce<number[]>((curve, t) => {
      const pnl = Number.parseFloat(t.pnl_realized ?? "0");
      const prev = curve.length > 0 ? curve[curve.length - 1] : 0;
      curve.push(prev + (Number.isFinite(pnl) ? pnl : 0));
      return curve;
    }, []);
  }, [trades]);

  const equityMin = Math.min(0, ...equityCurve);
  const equityMax = Math.max(0, ...equityCurve);
  const equityRange = equityMax - equityMin || 1;

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={fadeUp}
      className="p-4 md:p-6 lg:p-8 max-w-6xl mx-auto space-y-5"
    >
      <header className="space-y-1">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <BarChart3 className="h-6 w-6 text-accent-blue" /> Analytics
        </h1>
        <p className="text-muted-foreground text-sm">
          P&amp;L stats summary + recent-window distributions.{" "}
          <span className="text-amber-300">
            Full-history daily aggregation arrives in a future sprint.
          </span>
        </p>
      </header>

      {/* ── Summary cards ── */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <SummaryCard
          label="Total trades"
          value={statsLoading ? "…" : (stats?.total_trades ?? 0).toLocaleString()}
          icon={Activity}
          tone="text-muted-foreground"
        />
        <SummaryCard
          label="Total P&L"
          value={statsLoading ? "…" : rupees(stats?.total_pnl ?? "0")}
          icon={stats && Number.parseFloat(stats.total_pnl) >= 0 ? TrendingUp : TrendingDown}
          tone={stats && Number.parseFloat(stats.total_pnl) >= 0 ? "text-profit" : "text-loss"}
        />
        <SummaryCard
          label="Win rate"
          value={statsLoading ? "…" : `${stats?.win_rate ?? 0}%`}
          icon={TrendingUp}
          tone={stats && stats.win_rate >= 50 ? "text-profit" : "text-muted-foreground"}
        />
        <SummaryCard
          label="Avg P&L / trade"
          value={statsLoading ? "…" : rupees(stats?.avg_pnl_per_trade ?? "0")}
          icon={BarChart3}
          tone="text-muted-foreground"
        />
        <SummaryCard
          label="Best trade"
          value={statsLoading ? "…" : rupees(stats?.best_trade_pnl ?? "0")}
          icon={Trophy}
          tone="text-profit"
        />
        <SummaryCard
          label="Worst trade"
          value={statsLoading ? "…" : rupees(stats?.worst_trade_pnl ?? "0")}
          icon={AlertTriangle}
          tone="text-loss"
        />
      </div>

      {/* Premium charts/list — partial wall. Summary cards above stay free
          (they read /me/trades/stats, ungated); these read /me/trades. */}
      {tradesPaywalled ? (
        <UpgradeWall
          feature="Full analytics"
          description="The equity curve and symbol breakdown are premium. Your summary stats above stay free."
          upgradeUrl={tradesPaywallUrl ?? undefined}
        />
      ) : (
        <>
          {/* ── Equity curve (last 100 trades, client-cumulated) ── */}
          <GlassmorphismCard className="p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-medium">Equity curve (recent 100 trades)</h2>
              <span className="text-xs text-muted-foreground">
                Client-cumulated · not full history
              </span>
            </div>
            {tradesLoading ? (
              <div className="h-32 grid place-items-center text-muted-foreground text-sm">
                Loading…
              </div>
            ) : equityCurve.length === 0 ? (
              <div className="h-32 grid place-items-center text-muted-foreground text-sm">
                No trades yet.
              </div>
            ) : (
              <Sparkline values={equityCurve} min={equityMin} range={equityRange} />
            )}
          </GlassmorphismCard>

          {/* ── Symbol distribution ── */}
          <GlassmorphismCard className="p-5 space-y-3">
            <h2 className="font-medium">Top symbols (recent 100 trades)</h2>
            {tradesLoading ? (
              <div className="text-muted-foreground text-sm">Loading…</div>
            ) : symbolDistribution.length === 0 ? (
              <div className="text-muted-foreground text-sm">No trades yet.</div>
            ) : (
              <div className="space-y-2">
                {symbolDistribution.map((row) => {
                  const maxCount = symbolDistribution[0]?.count ?? 1;
                  const widthPct = (row.count / maxCount) * 100;
                  const pnlPositive = row.pnl >= 0;
                  return (
                    <div key={row.symbol} className="space-y-1">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-mono">{row.symbol}</span>
                        <span className="text-xs text-muted-foreground">
                          {row.count} trade{row.count > 1 ? "s" : ""} ·{" "}
                          <span className={pnlPositive ? "text-profit" : "text-loss"}>
                            {rupees(row.pnl.toString())}
                          </span>
                        </span>
                      </div>
                      <div className="h-1.5 rounded-full bg-white/[0.03] overflow-hidden">
                        <div
                          className={cn(
                            "h-full transition-all",
                            pnlPositive ? "bg-profit/70" : "bg-loss/70",
                          )}
                          style={{ width: `${widthPct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </GlassmorphismCard>
        </>
      )}

      {/* ── Scope note ── */}
      <GlassmorphismCard className="p-4 text-sm text-muted-foreground">
        <div className="font-medium text-foreground mb-1">
          What&apos;s next (scheduled, not built tonight)
        </div>
        <ul className="list-disc list-inside text-xs space-y-1">
          <li>Full-history daily P&amp;L aggregation (needs new backend endpoint)</li>
          <li>Per-strategy comparison + drawdown</li>
          <li>Sharpe ratio · Calmar ratio · best/worst day</li>
          <li>Date-range filters</li>
        </ul>
      </GlassmorphismCard>
    </motion.div>
  );
}

function SummaryCard({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  tone: string;
}) {
  return (
    <GlassmorphismCard className="p-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs text-muted-foreground">{label}</div>
          <div className={cn("text-xl font-semibold mt-1", tone)}>{value}</div>
        </div>
        <Icon className={cn("h-5 w-5", tone)} />
      </div>
    </GlassmorphismCard>
  );
}

function Sparkline({ values, min, range }: { values: number[]; min: number; range: number }) {
  const width = 800;
  const height = 120;
  const step = values.length > 1 ? width / (values.length - 1) : width;

  const points = values
    .map((v, i) => {
      const x = i * step;
      const y = height - ((v - min) / range) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const lastValue = values[values.length - 1] ?? 0;
  const tone = lastValue >= 0 ? "stroke-profit" : "stroke-loss";

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-32">
      {/* Zero line */}
      {min < 0 && (
        <line
          x1="0"
          x2={width}
          y1={height - (-min / range) * height}
          y2={height - (-min / range) * height}
          stroke="rgba(255,255,255,0.08)"
          strokeDasharray="4 4"
        />
      )}
      <polyline fill="none" strokeWidth="2" className={tone} points={points} />
    </svg>
  );
}
