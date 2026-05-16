/**
 * EquityCurveChart — recharts AreaChart of the Phase B equity curve.
 *
 * Renders one area per equity-by-trade time series. Colour switches
 * to profit-green when ending equity ≥ starting, loss-red when below
 * — matches the visual convention in
 * :mod:`@/components/charts/equity-curve` and the
 * BacktestResultPanel equity card.
 *
 * X-axis uses the point index (trade number) rather than wall-clock
 * time: equity-by-trade is event-indexed, not time-indexed, and the
 * gap between trades is irrelevant to the curve's shape.
 *
 * Tooltip surfaces the ISO timestamp + drawdown so users can drill
 * into a specific trade by inspection. The ``tradeId`` is carried on
 * each point for future click-to-drill (deferred to next phase).
 */

"use client";

import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { TrendingDown, TrendingUp } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { cn } from "@/lib/utils";
import type { EquityCurveResponse } from "@/lib/strategy-tester/types";

interface EquityCurveChartProps {
  equity: EquityCurveResponse | null;
  className?: string;
}

export function EquityCurveChart({ equity, className }: EquityCurveChartProps) {
  if (!equity || equity.points.length === 0) {
    return (
      <GlassmorphismCard
        hover={false}
        className={cn(className)}
      >
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp className="h-4 w-4 text-muted-foreground" />
          <h3 className="font-semibold text-sm">Equity curve</h3>
        </div>
        <p
          data-testid="equity-empty-state"
          className="text-xs text-muted-foreground text-center py-12"
        >
          No equity data yet — once trades close, the curve will populate here.
        </p>
      </GlassmorphismCard>
    );
  }

  const isProfit = equity.endingEquity >= equity.startingEquity;
  const color = isProfit ? "var(--profit)" : "var(--loss)";

  const data = equity.points.map((p, i) => ({
    index: i,
    timestamp: p.timestamp,
    equity: p.equity,
    drawdown: p.drawdownPct,
  }));

  return (
    <GlassmorphismCard
      hover={false}
      className={cn(className)}
    >
      <div className="flex items-center gap-2 mb-3">
        {isProfit ? (
          <TrendingUp className="h-4 w-4 text-profit" />
        ) : (
          <TrendingDown className="h-4 w-4 text-loss" />
        )}
        <h3 className="font-semibold text-sm">Equity curve</h3>
        <Badge className="bg-white/[0.03] border-white/[0.06] text-muted-foreground">
          {data.length} {data.length === 1 ? "point" : "points"}
        </Badge>
      </div>
      <div
        data-testid="equity-chart-canvas"
        className="h-64"
      >
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={data}
            margin={{ top: 5, right: 8, left: 8, bottom: 5 }}
          >
            <defs>
              <linearGradient
                id="strategy-tester-equity-gradient"
                x1="0"
                y1="0"
                x2="0"
                y2="1"
              >
                <stop offset="0%" stopColor={color} stopOpacity={0.3} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="index"
              axisLine={false}
              tickLine={false}
              tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
              interval="preserveStartEnd"
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
              tickFormatter={(v: number) => `₹${(v / 1000).toFixed(0)}K`}
              width={60}
              domain={["auto", "auto"]}
            />
            <Tooltip
              contentStyle={{
                background: "var(--card)",
                border: "1px solid var(--border)",
                borderRadius: "8px",
                color: "var(--foreground)",
                fontSize: "13px",
              }}
              formatter={(value: number, name: string) =>
                name === "equity"
                  ? [
                      `₹${value.toLocaleString("en-IN", {
                        maximumFractionDigits: 2,
                      })}`,
                      "Equity",
                    ]
                  : [`${value.toFixed(2)}%`, "Drawdown"]
              }
              labelFormatter={(label: number) => `Trade ${label}`}
            />
            <Area
              type="monotone"
              dataKey="equity"
              stroke={color}
              strokeWidth={2}
              fill="url(#strategy-tester-equity-gradient)"
              animationDuration={800}
              animationEasing="ease-out"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </GlassmorphismCard>
  );
}
