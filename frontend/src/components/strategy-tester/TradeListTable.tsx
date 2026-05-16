/**
 * TradeListTable — paginated, client-sortable table of Phase B trades.
 *
 * Mirrors the BacktestResultPanel trade-log table styling — same
 * column set (#/Side/Entry/Exit/Qty/P&L/Reason) plus Symbol +
 * Duration which the Phase B aggregator carries on every row.
 *
 * Open trades (exit_* and pnl_* all ``null``) render the exit-side
 * cells as ``—`` rather than blanks so the row stays visually
 * grounded. P&L cell color is suppressed for open trades.
 *
 * Sort is client-side over the rendered page. Server-side sort is
 * deferred — the Phase B route doesn't expose a ``sort`` param. The
 * sort state resets when ``trades`` identity changes (new fetch).
 */

"use client";

import { useMemo, useState } from "react";
import { Activity, ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { cn } from "@/lib/utils";
import type { TradeRecord } from "@/lib/strategy-tester/types";

type SortKey =
  | "entryTime"
  | "symbol"
  | "side"
  | "entryPrice"
  | "exitPrice"
  | "qty"
  | "pnl"
  | "durationMinutes";

type SortDir = "asc" | "desc";

interface TradeListTableProps {
  trades: TradeRecord[];
  className?: string;
}

export function TradeListTable({ trades, className }: TradeListTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("entryTime");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const sorted = useMemo(
    () => sortTrades(trades, sortKey, sortDir),
    [trades, sortKey, sortDir],
  );

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  if (trades.length === 0) {
    return (
      <GlassmorphismCard hover={false} className={cn(className)}>
        <div className="flex items-center gap-2 mb-3">
          <Activity className="h-4 w-4 text-accent-blue" />
          <h3 className="font-semibold text-sm">Trades</h3>
        </div>
        <p
          data-testid="trades-empty-state"
          className="text-xs text-muted-foreground text-center py-12"
        >
          No trades yet for this strategy — once signals fire and close,
          they will appear here.
        </p>
      </GlassmorphismCard>
    );
  }

  return (
    <GlassmorphismCard hover={false} className={cn(className)}>
      <div className="flex items-center gap-2 mb-3">
        <Activity className="h-4 w-4 text-accent-blue" />
        <h3 className="font-semibold text-sm">Trades</h3>
        <Badge className="bg-white/[0.03] border-white/[0.06] text-muted-foreground">
          {trades.length} {trades.length === 1 ? "trade" : "trades"}
        </Badge>
      </div>
      <div className="overflow-x-auto">
        <table
          data-testid="trades-table"
          className="w-full text-xs"
        >
          <thead className="text-muted-foreground uppercase tracking-wide">
            <tr className="border-b border-white/[0.06]">
              <th className="text-left py-1.5 pr-3">#</th>
              <SortableTh
                label="Time"
                colKey="entryTime"
                sortKey={sortKey}
                sortDir={sortDir}
                onClick={toggleSort}
                align="left"
              />
              <SortableTh
                label="Symbol"
                colKey="symbol"
                sortKey={sortKey}
                sortDir={sortDir}
                onClick={toggleSort}
                align="left"
              />
              <SortableTh
                label="Side"
                colKey="side"
                sortKey={sortKey}
                sortDir={sortDir}
                onClick={toggleSort}
                align="left"
              />
              <SortableTh
                label="Entry"
                colKey="entryPrice"
                sortKey={sortKey}
                sortDir={sortDir}
                onClick={toggleSort}
                align="right"
              />
              <SortableTh
                label="Exit"
                colKey="exitPrice"
                sortKey={sortKey}
                sortDir={sortDir}
                onClick={toggleSort}
                align="right"
              />
              <SortableTh
                label="Qty"
                colKey="qty"
                sortKey={sortKey}
                sortDir={sortDir}
                onClick={toggleSort}
                align="right"
              />
              <SortableTh
                label="P&L"
                colKey="pnl"
                sortKey={sortKey}
                sortDir={sortDir}
                onClick={toggleSort}
                align="right"
              />
              <SortableTh
                label="Duration"
                colKey="durationMinutes"
                sortKey={sortKey}
                sortDir={sortDir}
                onClick={toggleSort}
                align="right"
              />
              <th className="text-left py-1.5">Reason</th>
            </tr>
          </thead>
          <tbody className="font-mono">
            {sorted.map((trade, idx) => (
              <TradeRow
                key={trade.entryMarkerId}
                trade={trade}
                index={idx}
              />
            ))}
          </tbody>
        </table>
      </div>
    </GlassmorphismCard>
  );
}

// ─── Row ──────────────────────────────────────────────────────────────

function TradeRow({ trade, index }: { trade: TradeRecord; index: number }) {
  const isOpen = trade.exitTime === null;
  return (
    <tr
      data-testid="trade-row"
      className="border-b border-white/[0.04] last:border-0"
    >
      <td className="py-1.5 pr-3 text-muted-foreground">{index + 1}</td>
      <td className="py-1.5 pr-3 text-muted-foreground">
        {formatTimeShort(trade.entryTimeIso)}
      </td>
      <td className="py-1.5 pr-3">{trade.symbol}</td>
      <td
        className={cn(
          "py-1.5 pr-3 font-semibold",
          trade.side === "LONG" ? "text-profit" : "text-loss",
        )}
      >
        {trade.side}
      </td>
      <td className="py-1.5 pr-3 text-right tabular-nums">
        {trade.entryPrice.toFixed(2)}
      </td>
      <td className="py-1.5 pr-3 text-right tabular-nums">
        {trade.exitPrice !== null ? trade.exitPrice.toFixed(2) : "—"}
      </td>
      <td className="py-1.5 pr-3 text-right tabular-nums">{trade.qty}</td>
      <td
        className={cn(
          "py-1.5 pr-3 text-right tabular-nums font-semibold",
          !isOpen && trade.pnl !== null && trade.pnl >= 0 && "text-profit",
          !isOpen && trade.pnl !== null && trade.pnl < 0 && "text-loss",
          isOpen && "text-muted-foreground",
        )}
      >
        {trade.pnl !== null ? formatRupee(trade.pnl) : "—"}
      </td>
      <td className="py-1.5 pr-3 text-right tabular-nums text-muted-foreground">
        {trade.durationMinutes !== null
          ? formatDuration(trade.durationMinutes)
          : "—"}
      </td>
      <td className="py-1.5 text-muted-foreground">
        {trade.exitReason ?? (isOpen ? "OPEN" : "—")}
      </td>
    </tr>
  );
}

// ─── Sortable header cell ─────────────────────────────────────────────

function SortableTh({
  label,
  colKey,
  sortKey,
  sortDir,
  onClick,
  align,
}: {
  label: string;
  colKey: SortKey;
  sortKey: SortKey;
  sortDir: SortDir;
  onClick: (k: SortKey) => void;
  align: "left" | "right";
}) {
  const active = sortKey === colKey;
  const Icon = !active ? ArrowUpDown : sortDir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th
      className={cn(
        "py-1.5 pr-3",
        align === "left" ? "text-left" : "text-right",
      )}
    >
      <button
        type="button"
        onClick={() => onClick(colKey)}
        className={cn(
          "inline-flex items-center gap-1 hover:text-foreground transition-colors",
          active && "text-foreground",
        )}
        aria-sort={
          active ? (sortDir === "asc" ? "ascending" : "descending") : "none"
        }
      >
        <span>{label}</span>
        <Icon className="h-3 w-3 opacity-60" />
      </button>
    </th>
  );
}

// ─── Sort logic ───────────────────────────────────────────────────────

function sortTrades(
  trades: TradeRecord[],
  key: SortKey,
  dir: SortDir,
): TradeRecord[] {
  const sign = dir === "asc" ? 1 : -1;
  // Open trades (null pnl, null exitPrice, null durationMinutes) sort
  // last in BOTH directions so they don't pollute the head of the
  // list with phantom zeros.
  return [...trades].sort((a, b) => {
    const av = (a as unknown as Record<SortKey, number | string | null>)[key];
    const bv = (b as unknown as Record<SortKey, number | string | null>)[key];
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    if (typeof av === "number" && typeof bv === "number") {
      return sign * (av - bv);
    }
    return sign * String(av).localeCompare(String(bv));
  });
}

// ─── Formatters ───────────────────────────────────────────────────────

function formatRupee(value: number): string {
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  const magnitude = Math.abs(value).toLocaleString("en-IN", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  });
  return `${sign}₹${magnitude}`;
}

function formatTimeShort(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-IN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes.toFixed(0)}m`;
  const hours = minutes / 60;
  if (hours < 24) return `${hours.toFixed(1)}h`;
  return `${(hours / 24).toFixed(1)}d`;
}
