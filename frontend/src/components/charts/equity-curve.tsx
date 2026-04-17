"use client";

import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useTheme } from "next-themes";

interface EquityCurveProps {
  data: { time: string; value: number }[];
}

export function EquityCurve({ data }: EquityCurveProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const isProfit = (data[data.length - 1]?.value ?? 0) >= 0;
  const color = isProfit
    ? (isDark ? "#00FF88" : "#16A34A")
    : (isDark ? "#FF4D6A" : "#E5484D");

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
          tick={{ fill: "#64748B", fontSize: 11 }}
          interval="preserveStartEnd"
        />
        <YAxis
          axisLine={false}
          tickLine={false}
          tick={{ fill: "#64748B", fontSize: 11 }}
          tickFormatter={(v: number) =>
            `\u20B9${(v / 1000).toFixed(1)}K`
          }
          width={55}
        />
        <Tooltip
          contentStyle={{
            background: "rgba(17, 24, 39, 0.9)",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: "8px",
            color: "#F8FAFC",
            fontSize: "13px",
          }}
          formatter={(value) => [
            `\u20B9${Number(value).toLocaleString("en-IN")}`,
            "P&L",
          ]}
          labelFormatter={(label) => `Time: ${label}`}
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
