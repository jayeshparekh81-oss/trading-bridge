"use client";

import { useState } from "react";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  TrendingUp,
  TrendingDown,
  Activity,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { AnimatedNumber } from "@/components/ui/animated-number";
import { cn } from "@/lib/utils";

/**
 * Wire shape from POST /api/strategies/{id}/backtest. The backend's
 * BacktestResult uses camelCase aliases at the top level; the nested
 * Trade and EquityPoint Pydantic models do not have aliases, so their
 * keys arrive snake_case.
 */
export interface BacktestTrade {
  entry_time: string;
  exit_time: string;
  side: "BUY" | "SELL";
  entry_price: number;
  exit_price: number;
  quantity: number;
  pnl: number;
  exit_reason: string;
  entry_reasons: string[];
}

export interface BacktestEquityPoint {
  timestamp: string;
  equity: number;
}

export interface BacktestResultPayload {
  totalPnl: number;
  totalReturnPercent: number;
  winRate: number;
  lossRate: number;
  totalTrades: number;
  averageWin: number;
  averageLoss: number;
  largestWin: number;
  largestLoss: number;
  maxDrawdown: number;
  profitFactor: number;
  expectancy: number;
  equityCurve: BacktestEquityPoint[];
  trades: BacktestTrade[];
  warnings: string[];
}

interface Props {
  result: BacktestResultPayload;
}

const TRADES_PAGE_SIZE = 50;


export function BacktestResultPanel({ result }: Props) {
  const isProfit = result.totalPnl >= 0;

  return (
    <div className="space-y-6">
      <MetricsGrid result={result} isProfit={isProfit} />
      <EquityCurveCard result={result} isProfit={isProfit} />
      <TradesTable trades={result.trades} />
      {result.warnings.length > 0 ? <WarningsCard warnings={result.warnings} /> : null}
    </div>
  );
}


// ─── Metrics grid ─────────────────────────────────────────────────────


function MetricsGrid({
  result,
  isProfit,
}: {
  result: BacktestResultPayload;
  isProfit: boolean;
}) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      <PnlStat totalPnl={result.totalPnl} isProfit={isProfit} />
      <Stat
        label="Return %"
        value={`${result.totalReturnPercent >= 0 ? "+" : ""}${result.totalReturnPercent.toFixed(2)}%`}
        accent={isProfit ? "profit" : "loss"}
      />
      <Stat
        label="Win Rate"
        value={`${(result.winRate * 100).toFixed(1)}%`}
      />
      <Stat label="Trades" value={`${result.totalTrades}`} />
      <Stat
        label="Max Drawdown"
        value={`${(result.maxDrawdown * 100).toFixed(1)}%`}
        accent={result.maxDrawdown > 0.2 ? "loss" : "neutral"}
      />
      <Stat
        label="Profit Factor"
        value={
          Number.isFinite(result.profitFactor)
            ? `${result.profitFactor.toFixed(2)}x`
            : "∞"
        }
      />
      <Stat
        label="Expectancy"
        value={formatRupee(result.expectancy, true)}
        accent={result.expectancy >= 0 ? "profit" : "loss"}
      />
      <Stat label="Avg Win" value={formatRupee(result.averageWin, false)} />
      <Stat label="Avg Loss" value={formatRupee(result.averageLoss, false)} />
      <Stat
        label="Largest Win"
        value={formatRupee(result.largestWin, false)}
        accent="profit"
      />
      <Stat
        label="Largest Loss"
        value={formatRupee(result.largestLoss, false)}
        accent="loss"
      />
      <Stat label="Loss Rate" value={`${(result.lossRate * 100).toFixed(1)}%`} />
    </div>
  );
}


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


// ─── P&L stat (AnimatedNumber) ────────────────────────────────────────


/**
 * Total P&L tile that count-ups from 0 to the actual figure on first
 * mount. Uses the existing :class:`AnimatedNumber` (en-IN locale,
 * 2 decimals) and prepends a leading sign so the parity with
 * :func:`formatRupee` rendering of the rest of the metrics grid stays
 * intact.
 */
function PnlStat({ totalPnl, isProfit }: { totalPnl: number; isProfit: boolean }) {
  const sign = totalPnl > 0 ? "+" : totalPnl < 0 ? "-" : "";
  return (
    <GlassmorphismCard hover={false} className="!p-3">
      <div className="text-[11px] text-muted-foreground uppercase tracking-wide">
        Total P&amp;L
      </div>
      <div
        className={cn(
          "mt-1 text-base font-semibold tabular-nums",
          isProfit ? "text-profit" : "text-loss",
        )}
      >
        {sign}
        <AnimatedNumber
          value={Math.abs(totalPnl)}
          duration={1.5}
          prefix="₹"
          decimals={2}
        />
      </div>
    </GlassmorphismCard>
  );
}


// ─── Equity curve ─────────────────────────────────────────────────────


function EquityCurveCard({
  result,
  isProfit,
}: {
  result: BacktestResultPayload;
  isProfit: boolean;
}) {
  const data = result.equityCurve.map((p, i) => ({
    index: i,
    timestamp: p.timestamp,
    equity: p.equity,
  }));
  const color = isProfit ? "var(--profit)" : "var(--loss)";

  return (
    <GlassmorphismCard hover={false}>
      <div className="flex items-center gap-2 mb-3">
        {isProfit ? (
          <TrendingUp className="h-4 w-4 text-profit" />
        ) : (
          <TrendingDown className="h-4 w-4 text-loss" />
        )}
        <h3 className="font-semibold text-sm">Equity curve</h3>
        <Badge className="bg-white/[0.03] border-white/[0.06] text-muted-foreground">
          {data.length} bars
        </Badge>
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 5, right: 8, left: 8, bottom: 5 }}>
            <defs>
              <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
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
              formatter={(value) => [
                `₹${Number(value).toLocaleString("en-IN", {
                  maximumFractionDigits: 2,
                })}`,
                "Equity",
              ]}
              labelFormatter={(label) => `Bar ${label}`}
            />
            <Area
              type="monotone"
              dataKey="equity"
              stroke={color}
              strokeWidth={2}
              fill="url(#equityGradient)"
              animationDuration={800}
              animationEasing="ease-out"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </GlassmorphismCard>
  );
}


// ─── Trades table ─────────────────────────────────────────────────────


function TradesTable({ trades }: { trades: BacktestTrade[] }) {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(0);
  const visible = trades.slice(
    page * TRADES_PAGE_SIZE,
    (page + 1) * TRADES_PAGE_SIZE,
  );
  const totalPages = Math.max(1, Math.ceil(trades.length / TRADES_PAGE_SIZE));

  return (
    <GlassmorphismCard hover={false}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-2"
        aria-expanded={open}
      >
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-accent-blue" />
          <h3 className="font-semibold text-sm">Trade log</h3>
          <Badge className="bg-white/[0.03] border-white/[0.06] text-muted-foreground">
            {trades.length} {trades.length === 1 ? "trade" : "trades"}
          </Badge>
        </div>
        {open ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        )}
      </button>
      {open ? (
        trades.length === 0 ? (
          <p className="mt-3 text-xs text-muted-foreground text-center py-6">
            No trades closed during this run.
          </p>
        ) : (
          <div className="mt-3 space-y-2">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="text-muted-foreground uppercase tracking-wide">
                  <tr className="border-b border-white/[0.06]">
                    <th className="text-left py-1.5 pr-3">#</th>
                    <th className="text-left py-1.5 pr-3">Side</th>
                    <th className="text-right py-1.5 pr-3">Entry</th>
                    <th className="text-right py-1.5 pr-3">Exit</th>
                    <th className="text-right py-1.5 pr-3">Qty</th>
                    <th className="text-right py-1.5 pr-3">P&L</th>
                    <th className="text-left py-1.5">Reason</th>
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {visible.map((trade, idx) => (
                    <tr
                      key={`${trade.entry_time}-${idx}`}
                      className="border-b border-white/[0.04] last:border-0"
                    >
                      <td className="py-1.5 pr-3 text-muted-foreground">
                        {page * TRADES_PAGE_SIZE + idx + 1}
                      </td>
                      <td
                        className={cn(
                          "py-1.5 pr-3 font-semibold",
                          trade.side === "BUY" ? "text-profit" : "text-loss",
                        )}
                      >
                        {trade.side}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {trade.entry_price.toFixed(2)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {trade.exit_price.toFixed(2)}
                      </td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">
                        {trade.quantity}
                      </td>
                      <td
                        className={cn(
                          "py-1.5 pr-3 text-right tabular-nums font-semibold",
                          trade.pnl >= 0 ? "text-profit" : "text-loss",
                        )}
                      >
                        {formatRupee(trade.pnl, true)}
                      </td>
                      <td className="py-1.5 text-muted-foreground">
                        {trade.exit_reason}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {totalPages > 1 ? (
              <div className="flex items-center justify-between text-xs text-muted-foreground pt-2">
                <span>
                  Page {page + 1} of {totalPages}
                </span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={page === 0}
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    className="px-2 py-1 rounded border border-white/[0.06] bg-white/[0.02] disabled:opacity-40"
                  >
                    Prev
                  </button>
                  <button
                    type="button"
                    disabled={page >= totalPages - 1}
                    onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                    className="px-2 py-1 rounded border border-white/[0.06] bg-white/[0.02] disabled:opacity-40"
                  >
                    Next
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        )
      ) : null}
    </GlassmorphismCard>
  );
}


// ─── Warnings ─────────────────────────────────────────────────────────


function WarningsCard({ warnings }: { warnings: string[] }) {
  return (
    <GlassmorphismCard hover={false}>
      <div className="flex items-center gap-2 mb-2">
        <AlertTriangle className="h-4 w-4 text-loss" />
        <h3 className="font-semibold text-sm">Warnings</h3>
        <Badge className="bg-loss/10 border-loss/30 text-loss">
          {warnings.length}
        </Badge>
      </div>
      <ul className="space-y-1 text-xs text-muted-foreground list-disc pl-5">
        {warnings.map((w, i) => (
          <li key={i} className="leading-relaxed">
            {w}
          </li>
        ))}
      </ul>
    </GlassmorphismCard>
  );
}


// ─── Helpers ─────────────────────────────────────────────────────────


function formatRupee(value: number, withSign: boolean): string {
  const sign = value > 0 && withSign ? "+" : value < 0 ? "-" : "";
  const magnitude = Math.abs(value).toLocaleString("en-IN", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  });
  return `${sign}₹${magnitude}`;
}
