"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  Activity,
  Landmark,
  ShieldCheck,
  Flame,
  Zap,
  BarChart3,
  Trophy,
  Brain,
} from "lucide-react";
import { AiGreeting } from "@/components/dashboard/ai-greeting";
import { HeroPnl } from "@/components/dashboard/hero-pnl";
import { StatCard } from "@/components/ui/stat-card";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { StreakBadge } from "@/components/dashboard/streak-badge";
import { TradeRow } from "@/components/ui/trade-row";
import { DashboardSkeleton } from "@/components/ui/skeleton-loader";
import { useApi } from "@/lib/use-api";
import { useAuth } from "@/lib/auth";
import { mockDashboard } from "@/lib/mock-data";
import { formatCurrency } from "@/lib/utils";

const stagger = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08 },
  },
};

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};

export default function DashboardPage() {
  const { user } = useAuth();
  const { data: stats } = useApi<{ total_trades: number; total_pnl: string; win_rate: number }>("/users/me/trades/stats", null, 30000);
  const { data: tradesResp } = useApi<{ trades: Array<{ id: string; symbol: string; exchange: string; side: string; quantity: number; price: string | null; pnl_realized: string | null; created_at: string }> }>("/users/me/trades?limit=5", null, 30000);

  // Merge real data with mock fallback
  const d = {
    ...mockDashboard,
    user: { ...mockDashboard.user, name: user?.full_name || user?.email || mockDashboard.user.name },
    todayPnl: stats ? Number(stats.total_pnl) : mockDashboard.todayPnl,
    winRate: stats ? stats.win_rate : mockDashboard.winRate,
    totalTradesToday: stats ? stats.total_trades : mockDashboard.totalTradesToday,
    recentTrades: tradesResp?.trades?.map((t) => ({
      id: t.id,
      time: t.created_at,
      action: (t.side === "buy" ? "BUY" : "SELL") as "BUY" | "SELL",
      symbol: t.symbol,
      quantity: t.quantity,
      price: Number(t.price || 0),
      pnl: Number(t.pnl_realized || 0),
      status: "complete" as const,
      broker: "",
      strategy: "",
    })) || mockDashboard.recentTrades,
  };

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto space-y-6"
    >
      {/* 1. AI Greeting */}
      <motion.div variants={fadeUp}>
        <AiGreeting name={d.user.name} todayPnl={d.todayPnl} />
      </motion.div>

      {/* 2. Hero P&L Card */}
      <motion.div variants={fadeUp}>
        <HeroPnl
          todayPnl={d.todayPnl}
          realizedPnl={d.realizedPnl}
          unrealizedPnl={d.unrealizedPnl}
          pnlPercent={d.pnlPercent}
          equityCurve={d.equityCurve}
        />
      </motion.div>

      {/* 3. Stat Cards Row */}
      <motion.div variants={fadeUp} className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Link
          href="/trades?filter=active"
          aria-label="View active trades"
          className="block rounded-xl transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg active:scale-[0.98] focus:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
        >
          <StatCard
            icon={Activity}
            label="Active Trades"
            value={d.activeTrades}
            iconColor="text-profit"
          />
        </Link>
        <Link
          href="/brokers"
          aria-label="Manage broker connections"
          className="block rounded-xl transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg active:scale-[0.98] focus:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
        >
          <StatCard
            icon={Landmark}
            label="Brokers Online"
            value={d.brokersOnline}
            iconColor="text-accent-blue"
          />
        </Link>
        <Link
          href="/kill-switch"
          aria-label="Kill switch settings"
          className="block rounded-xl transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg active:scale-[0.98] focus:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
        >
          <GlassmorphismCard
            glow={d.killSwitchStatus === "ACTIVE" ? "profit" : "none"}
            className="p-5"
          >
            <div className="flex items-start justify-between">
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">Kill Switch</p>
                <div className="text-2xl font-bold">
                  <span className={d.killSwitchStatus === "ACTIVE" ? "text-profit" : "text-loss"}>
                    {d.killSwitchStatus === "ACTIVE" ? "SAFE" : "TRIPPED"}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">
                  {formatCurrency(d.killSwitchRemaining)} remaining
                </p>
              </div>
              <div className="rounded-lg p-2.5 bg-white/[0.05] text-profit">
                <ShieldCheck className="h-5 w-5" />
              </div>
            </div>
          </GlassmorphismCard>
        </Link>
        <Link
          href="/analytics?tab=streak"
          aria-label="Win streak analytics"
          className="block rounded-xl transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg active:scale-[0.98] focus:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
        >
          <GlassmorphismCard className="p-5">
            <div className="flex items-start justify-between">
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">Win Streak</p>
                <div className="text-2xl font-bold">
                  {d.winStreak}-Day
                </div>
                <StreakBadge streak={d.winStreak} />
              </div>
              <div className="rounded-lg p-2.5 bg-white/[0.05] text-accent-gold">
                <Flame className="h-5 w-5" />
              </div>
            </div>
          </GlassmorphismCard>
        </Link>
      </motion.div>

      {/* 4. Recent Trades Table */}
      <motion.div variants={fadeUp}>
        <GlassmorphismCard hover={false} className="overflow-hidden">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Recent Trades</h2>
            <a href="/trades" className="text-sm text-accent-blue hover:underline">
              View all &rarr;
            </a>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/[0.08]">
                  <th className="text-left py-2 px-4 text-xs font-medium text-muted-foreground uppercase">
                    Time
                  </th>
                  <th className="text-left py-2 px-4 text-xs font-medium text-muted-foreground uppercase">
                    Action
                  </th>
                  <th className="text-left py-2 px-4 text-xs font-medium text-muted-foreground uppercase">
                    Symbol
                  </th>
                  <th className="text-right py-2 px-4 text-xs font-medium text-muted-foreground uppercase">
                    Price
                  </th>
                  <th className="text-right py-2 px-4 text-xs font-medium text-muted-foreground uppercase">
                    P&amp;L
                  </th>
                </tr>
              </thead>
              <tbody>
                {d.recentTrades.map((trade, i) => (
                  <TradeRow key={trade.id} trade={trade} isLatest={i === 0} />
                ))}
              </tbody>
            </table>
          </div>
        </GlassmorphismCard>
      </motion.div>

      {/* 5. Bottom Row: AI Insights + Top Strategy */}
      <motion.div variants={fadeUp} className="grid md:grid-cols-2 gap-4">
        <GlassmorphismCard className="flex items-start gap-4">
          <div className="rounded-lg p-3 bg-accent-purple/10 text-accent-purple shrink-0">
            <Brain className="h-6 w-6" />
          </div>
          <div>
            <h3 className="font-semibold mb-1">AI Insights</h3>
            <p className="text-sm text-muted-foreground">
              Market showing strong momentum today. Your strategies are well-aligned
              with the current trend. Consider tightening stop-losses for overnight positions.
            </p>
          </div>
        </GlassmorphismCard>

        <GlassmorphismCard className="flex items-start gap-4">
          <div className="rounded-lg p-3 bg-accent-gold/10 text-accent-gold shrink-0">
            <Trophy className="h-6 w-6" />
          </div>
          <div>
            <h3 className="font-semibold mb-1">Top Strategy</h3>
            <p className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">
                {d.strategies[0].name}
              </span>{" "}
              &mdash; Win Rate: {d.strategies[0].winRate}% | Today:{" "}
              <span className="text-profit font-medium">
                {formatCurrency(d.strategies[0].todayPnl, { showSign: true })}
              </span>
            </p>
          </div>
        </GlassmorphismCard>
      </motion.div>

      {/* 6. Footer Stats Bar */}
      <motion.div
        variants={fadeUp}
        className="flex flex-wrap items-center justify-center gap-6 py-4 text-sm text-muted-foreground"
      >
        <span className="flex items-center gap-1.5">
          <Zap className="h-4 w-4 text-accent-blue" />
          Avg Latency: {d.avgLatencyMs}ms
        </span>
        <span className="flex items-center gap-1.5">
          <BarChart3 className="h-4 w-4 text-accent-purple" />
          Today: {d.totalTradesToday} trades
        </span>
        <span className="flex items-center gap-1.5">
          <Activity className="h-4 w-4 text-profit" />
          Win Rate: {d.winRate}%
        </span>
      </motion.div>
    </motion.div>
  );
}
