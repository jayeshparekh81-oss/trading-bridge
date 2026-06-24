"use client";

import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface EquityCurveProps {
  data: { time: string; value: number }[];
  /**
   * Value unit for the Y axis + tooltip. Default "inr" preserves the original
   * ₹ P&L formatting for existing callers (e.g. the dashboard hero). Use "pct"
   * for percentage-point series (e.g. the non-compounded showcase curve), so
   * the axis/tooltip never imply rupees on percentage data.
   */
  unit?: "inr" | "pct";
  /** Tooltip series label. Defaults to "P&L" (inr) / "Cumulative net %" (pct). */
  valueLabel?: string;
}

export function EquityCurve({ data, unit = "inr", valueLabel }: EquityCurveProps) {
  const isProfit = (data[data.length - 1]?.value ?? 0) >= 0;
  const color = isProfit ? "var(--profit)" : "var(--loss)";
  const isPct = unit === "pct";

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
        <defs>
          <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="time"
          axisLine={false}
          tickLine={false}
          tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
          interval="preserveStartEnd"
        />
        <YAxis
          axisLine={false}
          tickLine={false}
          tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
          tickFormatter={(v: number) =>
            isPct
              ? `${v > 0 ? "+" : ""}${v.toFixed(0)}%`
              : `\u20B9${(v / 1000).toFixed(1)}K`
          }
          width={55}
        />
        <Tooltip
          contentStyle={{
            background: "var(--card)",
            border: "1px solid var(--border)",
            borderRadius: "8px",
            color: "var(--foreground)",
            fontSize: "13px",
          }}
          formatter={(value) =>
            isPct
              ? [
                  `${Number(value) > 0 ? "+" : ""}${Number(value).toFixed(2)}%`,
                  valueLabel ?? "Cumulative net %",
                ]
              : [
                  `\u20B9${Number(value).toLocaleString("en-IN")}`,
                  valueLabel ?? "P&L",
                ]
          }
          labelFormatter={(label) => (isPct ? `${label}` : `Time: ${label}`)}
        />
        <Area
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={2}
          fill="url(#pnlGradient)"
          animationDuration={1500}
          animationEasing="ease-out"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
