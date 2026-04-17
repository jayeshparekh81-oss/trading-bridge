"use client";

import { motion } from "framer-motion";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { ProfitLossText } from "@/components/ui/profit-loss-text";
import { EquityCurve } from "@/components/charts/equity-curve";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";

interface HeroPnlProps {
  todayPnl: number;
  realizedPnl: number;
  unrealizedPnl: number;
  pnlPercent: number;
  equityCurve: { time: string; value: number }[];
}

export function HeroPnl({
  todayPnl,
  realizedPnl,
  unrealizedPnl,
  pnlPercent,
  equityCurve,
}: HeroPnlProps) {
  const isProfit = todayPnl >= 0;

  return (
    <GlassmorphismCard
      glow={isProfit ? "profit" : "none"}
      hover={false}
      className="overflow-hidden"
    >
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.1 }}
      >
        <p className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-2">
          Today&apos;s P&amp;L
        </p>

        <div className="flex items-end gap-4 mb-4">
          <ProfitLossText value={todayPnl} size="hero" glow={isProfit} />
          <span
            className={`text-lg font-semibold flex items-center gap-1 mb-2 ${isProfit ? "text-profit" : "text-loss"}`}
          >
            {isProfit ? (
              <ArrowUpRight className="h-5 w-5" />
            ) : (
              <ArrowDownRight className="h-5 w-5" />
            )}
            {formatPercent(pnlPercent)}
          </span>
        </div>

        {/* Progress bar */}
        <div className="h-2 rounded-full bg-white/[0.05] mb-4 overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${Math.min(Math.abs(pnlPercent) * 20, 100)}%` }}
            transition={{ duration: 1.2, ease: "easeOut" }}
            className={`h-full rounded-full ${isProfit ? "bg-gradient-to-r from-emerald-500 to-profit" : "bg-gradient-to-r from-red-500 to-loss"}`}
          />
        </div>

        {/* Realized / Unrealized */}
        <div className="flex gap-6 text-sm mb-6">
          <div>
            <span className="text-muted-foreground">Realized </span>
            <span className={isProfit ? "text-profit font-medium" : "text-loss font-medium"}>
              {formatCurrency(realizedPnl, { showSign: true })}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground">Unrealized </span>
            <span className={unrealizedPnl >= 0 ? "text-profit font-medium" : "text-loss font-medium"}>
              {formatCurrency(unrealizedPnl, { showSign: true })}
            </span>
          </div>
        </div>

        {/* Equity curve chart */}
        <EquityCurve data={equityCurve} />
      </motion.div>
    </GlassmorphismCard>
  );
}
