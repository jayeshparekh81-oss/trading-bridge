"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { TrendingUp, Trophy, Calendar, Zap, Target, BarChart3, Flame } from "lucide-react";
import { Area, AreaChart, Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { StatCard } from "@/components/ui/stat-card";
import { AnimatedNumber } from "@/components/ui/animated-number";
import { mockDashboard } from "@/lib/mock-data";
import { formatCurrency, cn } from "@/lib/utils";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.06 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

const periods = ["Today", "7D", "30D", "90D", "1Y", "All"] as const;

export default function AnalyticsPage() {
  const [period, setPeriod] = useState<string>("30D");
  const a = mockDashboard.analytics30d;
  const d = mockDashboard;

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <motion.div variants={fadeUp} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <TrendingUp className="h-6 w-6 text-accent-blue" /> Analytics
        </h1>
        <div className="flex gap-1 bg-muted/50 rounded-lg p-1">
          {periods.map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                period === p ? "bg-accent-blue text-white" : "text-muted-foreground hover:text-foreground"
              )}
            >
              {p}
            </button>
          ))}
        </div>
      </motion.div>

      {/* Stat cards */}
      <motion.div variants={fadeUp} className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard icon={Target} label="Win Rate" value={a.winRate} suffix="%" iconColor="text-profit" />
        <StatCard icon={TrendingUp} label="Total P&L" value={`${formatCurrency(a.totalPnl, { compact: true })}`} iconColor="text-profit" />
        <StatCard icon={BarChart3} label="Sharpe Ratio" value={String(a.sharpe)} iconColor="text-accent-purple" />
        <StatCard icon={Calendar} label="Total Trades" value={a.totalTrades} iconColor="text-accent-blue" />
        <StatCard icon={Trophy} label="Best Day" value={`${formatCurrency(a.bestDay.pnl, { showSign: true })}`} iconColor="text-accent-gold" />
        <StatCard icon={Zap} label="Avg P&L/Trade" value={`${formatCurrency(a.avgTradesPnl, { showSign: true })}`} iconColor="text-accent-blue" />
      </motion.div>

      {/* Equity Curve */}
      <motion.div variants={fadeUp}>
        <GlassmorphismCard hover={false}>
          <h2 className="text-lg font-semibold mb-4">Equity Curve (30 Days)</h2>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={a.equityCurve} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
              <defs>
                <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00FF88" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#00FF88" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "#64748B", fontSize: 10 }} interval={4} />
              <YAxis axisLine={false} tickLine={false} tick={{ fill: "#64748B", fontSize: 10 }} tickFormatter={(v) => `\u20B9${(v/1000).toFixed(0)}K`} width={50} />
              <Tooltip contentStyle={{ background: "rgba(17,24,39,0.9)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "8px", color: "#F8FAFC", fontSize: "12px" }} formatter={(v) => [`\u20B9${Number(v).toLocaleString("en-IN")}`, "P&L"]} />
              <Area type="monotone" dataKey="value" stroke="#00FF88" strokeWidth={2} fill="url(#eqGrad)" animationDuration={1500} />
            </AreaChart>
          </ResponsiveContainer>
        </GlassmorphismCard>
      </motion.div>

      {/* Daily P&L Distribution */}
      <motion.div variants={fadeUp}>
        <GlassmorphismCard hover={false}>
          <h2 className="text-lg font-semibold mb-4">Daily P&amp;L Distribution</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={a.dailyPnl} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
              <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "#64748B", fontSize: 10 }} />
              <YAxis axisLine={false} tickLine={false} tick={{ fill: "#64748B", fontSize: 10 }} tickFormatter={(v) => `\u20B9${(v/1000).toFixed(0)}K`} width={50} />
              <Tooltip contentStyle={{ background: "rgba(17,24,39,0.9)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "8px", color: "#F8FAFC", fontSize: "12px" }} formatter={(v) => [`\u20B9${Number(v).toLocaleString("en-IN")}`, "P&L"]} />
              <Bar dataKey="pnl" radius={[4, 4, 0, 0]} animationDuration={1200}>
                {a.dailyPnl.map((entry, i) => (
                  <rect key={i} fill={entry.pnl >= 0 ? "#00FF88" : "#FF4D6A"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </GlassmorphismCard>
      </motion.div>

      {/* Latency + Slippage */}
      <motion.div variants={fadeUp} className="grid md:grid-cols-2 gap-4">
        <GlassmorphismCard>
          <h3 className="font-semibold mb-3 flex items-center gap-2"><Zap className="h-4 w-4 text-accent-blue" />Latency Report</h3>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-xs text-muted-foreground">P50</div>
              <div className="text-2xl font-bold text-profit">{a.latency.p50}ms</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">P95</div>
              <div className="text-2xl font-bold text-accent-blue">{a.latency.p95}ms</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">P99</div>
              <div className="text-2xl font-bold text-accent-gold">{a.latency.p99}ms</div>
            </div>
          </div>
          <p className="text-xs text-muted-foreground mt-3 text-center">Faster than 99% of trading platforms</p>
        </GlassmorphismCard>

        <GlassmorphismCard>
          <h3 className="font-semibold mb-3">Slippage Analysis</h3>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-xs text-muted-foreground">Average</div>
              <div className="text-2xl font-bold">{a.slippage.avg}%</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Best</div>
              <div className="text-2xl font-bold text-profit">{a.slippage.best}%</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Worst</div>
              <div className="text-2xl font-bold text-loss">{a.slippage.worst}%</div>
            </div>
          </div>
        </GlassmorphismCard>
      </motion.div>

      {/* Strategy Comparison */}
      <motion.div variants={fadeUp}>
        <GlassmorphismCard hover={false}>
          <h2 className="text-lg font-semibold mb-4">Strategy Comparison</h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/[0.08]">
                  {["Strategy", "Win %", "P&L (Month)", "Trades", "Today"].map((h) => (
                    <th key={h} className="text-left py-2 px-4 text-xs font-medium text-muted-foreground uppercase">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {d.strategies.map((s) => (
                  <tr key={s.id} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                    <td className="py-3 px-4 font-medium">{s.name}</td>
                    <td className="py-3 px-4">{s.winRate}%</td>
                    <td className={cn("py-3 px-4 font-medium", s.monthPnl >= 0 ? "text-profit" : "text-loss")}>{formatCurrency(s.monthPnl, { showSign: true })}</td>
                    <td className="py-3 px-4">{s.totalTrades}</td>
                    <td className={cn("py-3 px-4 font-medium", s.todayPnl >= 0 ? "text-profit" : "text-loss")}>{formatCurrency(s.todayPnl, { showSign: true })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassmorphismCard>
      </motion.div>

      {/* Highlights */}
      <motion.div variants={fadeUp} className="flex flex-wrap justify-center gap-6 py-4 text-sm text-muted-foreground">
        <span className="flex items-center gap-1.5"><Trophy className="h-4 w-4 text-accent-gold" />Best Day: {formatCurrency(a.bestDay.pnl, { showSign: true })} ({a.bestDay.date})</span>
        <span className="flex items-center gap-1.5 text-loss">Worst Day: {formatCurrency(a.worstDay.pnl, { showSign: true })} ({a.worstDay.date})</span>
        <span className="flex items-center gap-1.5"><Flame className="h-4 w-4 text-accent-gold" />Streak: {d.winStreak} days profit</span>
      </motion.div>
    </motion.div>
  );
}
