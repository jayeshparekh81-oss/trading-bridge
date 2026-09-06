"use client";

/**
 * /analytics — round-trip summary + execution distributions.
 *
 * Wire: GET /api/users/me/trades/stats  (closed round trips; money only from
 *                                        PRICED positions — the exit rule)
 *      GET /api/users/me/trades         (executions — legs — through the same
 *                                        owner-scoped query the CSV export uses)
 *
 * Everything below the summary cards is computed client-side from the most
 * recent 100 executions / the priced round trips the server returned, and is
 * labelled as such. A human-interfered round trip is a trade with no number:
 * it is counted, never folded in as zero.
 *
 * Header comes from the ONE Pro template (ProPage): the title is the sidebar
 * label and the blurb is the sidebar blurb, both from @/lib/nav/pro-nav. The
 * money-basis caveat is NOT a subtitle — it qualifies the summary cards, so it
 * sits with them in the content.
 */

import { useMemo } from "react";
import { motion } from "framer-motion";
import { BarChart3, TrendingUp, TrendingDown, Activity, Trophy, AlertTriangle } from "lucide-react";

import { UpgradeWall } from "@/components/billing/upgrade-wall";
import { ProPage, ProEmpty } from "@/components/dashboard/pro-page";
import { GlassmorphismCard } from "@/shared/ui/glassmorphism-card";
import { useApi } from "@/shared/api/use-api";
import { cn } from "@/shared/lib/utils";

interface CurvePoint {
  position_id: string;
  symbol: string;
  closed_at: string | null;
  pnl: string;
  attribution: string | null;
}

interface TradeStats {
  total_trades: number;
  priced_trades: number;
  unpriced_trades: number;
  executions_total: number;
  total_pnl: string;
  win_rate: number;
  avg_pnl_per_trade: string;
  best_trade_pnl: string;
  worst_trade_pnl: string;
  pnl_basis: string;
  curve: CurvePoint[];
}

interface ExecutionRow {
  id: string;
  signal_id: string;
  leg_role: string;
  symbol: string;
  side: string;
  quantity: number;
  price: string | null;
  broker_status: string | null;
  error_code: string | null;
  placed_at: string | null;
}

interface ExecutionListResponse {
  trades: ExecutionRow[];
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
    data: execResp,
    isLoading: execLoading,
    paywalled: execPaywalled,
    paywallUrl: execPaywallUrl,
  } = useApi<ExecutionListResponse>("/users/me/trades?limit=100");

  const executions = useMemo(() => execResp?.trades ?? [], [execResp]);
  const curvePoints = useMemo(() => stats?.curve ?? [], [stats]);

  // ─── Client-side aggregations ──
  // Executions per symbol (legs placed, last 100). A leg has no P&L, so this
  // is a COUNT — never a money figure.
  const symbolDistribution = useMemo(() => {
    const map = new Map<string, { count: number; failed: number }>();
    for (const e of executions) {
      const entry = map.get(e.symbol) ?? { count: 0, failed: 0 };
      entry.count += 1;
      if (e.error_code) entry.failed += 1;
      map.set(e.symbol, entry);
    }
    return [...map.entries()]
      .map(([symbol, agg]) => ({ symbol, ...agg }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [executions]);

  // Priced round trips oldest-first → cumulate. Reduce into a fresh array
  // (no reassigned closure accumulator) — satisfies react-hooks/immutability.
  const equityCurve = useMemo(
    () =>
      curvePoints.reduce<number[]>((curve, p) => {
        const pnl = Number.parseFloat(p.pnl);
        const prev = curve.length > 0 ? curve[curve.length - 1] : 0;
        curve.push(prev + (Number.isFinite(pnl) ? pnl : 0));
        return curve;
      }, []),
    [curvePoints],
  );

  const equityMin = Math.min(0, ...equityCurve);
  const equityMax = Math.max(0, ...equityCurve);
  const equityRange = equityMax - equityMin || 1;
  const unpriced = stats?.unpriced_trades ?? 0;

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={fadeUp}
      className="p-4 md:p-6 lg:p-8 max-w-6xl mx-auto"
      data-testid="analytics-page"
    >
      <ProPage>
        {/* ── Summary cards ── */}
        <div className="space-y-3">
          <p className="text-muted-foreground text-sm">
            Money figures are net of estimated costs and count only round trips the bot closed on
            its own.{" "}
            {unpriced > 0 && (
              <span className="text-amber-300" data-testid="unpriced-note">
                {unpriced} round trip{unpriced > 1 ? "s" : ""} human-interfered — counted, not priced.
              </span>
            )}
          </p>
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
            <SummaryCard
              label="Round trips"
              value={statsLoading ? "…" : (stats?.total_trades ?? 0).toLocaleString()}
              icon={Activity}
              tone="text-muted-foreground"
            />
            <SummaryCard
              label="Total P&L (priced)"
              value={statsLoading ? "…" : rupees(stats?.total_pnl ?? "0")}
              icon={stats && Number.parseFloat(stats.total_pnl) >= 0 ? TrendingUp : TrendingDown}
              tone={stats && Number.parseFloat(stats.total_pnl) >= 0 ? "text-profit" : "text-loss"}
            />
            <SummaryCard
              label="Win rate (priced)"
              value={statsLoading ? "…" : `${stats?.win_rate ?? 0}%`}
              icon={TrendingUp}
              tone={stats && stats.win_rate >= 50 ? "text-profit" : "text-muted-foreground"}
            />
            <SummaryCard
              label="Avg P&L / round trip"
              value={statsLoading ? "…" : rupees(stats?.avg_pnl_per_trade ?? "0")}
              icon={BarChart3}
              tone="text-muted-foreground"
            />
            <SummaryCard
              label="Best round trip"
              value={statsLoading ? "…" : rupees(stats?.best_trade_pnl ?? "0")}
              icon={Trophy}
              tone="text-profit"
            />
            <SummaryCard
              label="Worst round trip"
              value={statsLoading ? "…" : rupees(stats?.worst_trade_pnl ?? "0")}
              icon={AlertTriangle}
              tone="text-loss"
            />
          </div>
        </div>

        {/* Premium charts/list — partial wall. Summary cards above stay free
            (they read /me/trades/stats, ungated); these read /me/trades. */}
        {execPaywalled ? (
          <UpgradeWall
            feature="Full analytics"
            description="The equity curve and symbol breakdown are premium. Your summary stats above stay free."
            upgradeUrl={execPaywallUrl ?? undefined}
          />
        ) : (
          <>
            {/* ── Equity curve (priced round trips, client-cumulated) ── */}
            <GlassmorphismCard className="p-5 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="font-medium">Equity curve (priced round trips)</h2>
                <span className="text-xs text-muted-foreground">Client-cumulated · net of estimated costs</span>
              </div>
              {statsLoading ? (
                <div className="h-32 grid place-items-center text-muted-foreground text-sm">
                  Loading…
                </div>
              ) : equityCurve.length === 0 ? (
                <ProEmpty
                  headline="Abhi koi priced round trip nahi hai"
                  next="Curve tab banna shuru hota hai jab bot khud pehla round trip band karta hai. Ek strategy chalu karo."
                  action={{ label: "Strategies", href: "/strategies" }}
                />
              ) : (
                <Sparkline values={equityCurve} min={equityMin} range={equityRange} />
              )}
            </GlassmorphismCard>

            {/* ── Symbol distribution (executions = legs placed) ── */}
            <GlassmorphismCard className="p-5 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="font-medium">Top symbols (last 100 executions)</h2>
                <span className="text-xs text-muted-foreground">Client-counted · legs, not P&amp;L</span>
              </div>
              {execLoading ? (
                <div className="text-muted-foreground text-sm">Loading…</div>
              ) : symbolDistribution.length === 0 ? (
                <ProEmpty
                  headline="Abhi tak koi execution nahi hui"
                  next="Aapki strategies ka har entry aur exit leg yahan aata hai. Ek strategy chalu karo, ya apna TradingView alert webhook URL par bhejo."
                />
              ) : (
                <div className="space-y-2">
                  {symbolDistribution.map((row) => {
                    const maxCount = symbolDistribution[0]?.count ?? 1;
                    const widthPct = (row.count / maxCount) * 100;
                    return (
                      <div key={row.symbol} className="space-y-1">
                        <div className="flex items-center justify-between text-sm">
                          <span className="font-mono">{row.symbol}</span>
                          <span className="text-xs text-muted-foreground">
                            {row.count} execution{row.count > 1 ? "s" : ""}
                            {row.failed > 0 && (
                              <>
                                {" "}· <span className="text-loss">{row.failed} failed</span>
                              </>
                            )}
                          </span>
                        </div>
                        <div className="h-1.5 rounded-full bg-white/[0.03] overflow-hidden">
                          <div
                            className={cn("h-full transition-all", row.failed === 0 ? "bg-profit/70" : "bg-amber-400/70")}
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
      </ProPage>
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
          stroke="var(--border)"
          strokeDasharray="4 4"
        />
      )}
      <polyline fill="none" strokeWidth="2" className={tone} points={points} />
    </svg>
  );
}
