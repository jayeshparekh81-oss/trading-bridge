"use client";

import { cn } from "@/lib/utils";
import type { Trade } from "@/lib/mock-data";

interface TradeRowProps {
  trade: Trade;
  isLatest?: boolean;
}

export function TradeRow({ trade, isLatest = false }: TradeRowProps) {
  const isProfit = trade.pnl >= 0;
  const time = new Date(trade.time).toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <tr
      className={cn(
        "border-b border-white/[0.04] transition-colors hover:bg-white/[0.03]",
        isLatest && "animate-pulse bg-profit/[0.03]"
      )}
    >
      <td className="py-3 px-4 text-sm text-muted-foreground">{time}</td>
      <td className="py-3 px-4">
        <span
          className={cn(
            "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold",
            trade.action === "BUY"
              ? "bg-profit/10 text-profit"
              : "bg-loss/10 text-loss"
          )}
        >
          {trade.action}
        </span>
      </td>
      <td className="py-3 px-4 text-sm font-medium">{trade.symbol}</td>
      <td className="py-3 px-4 text-sm text-right">
        {"\u20B9"}
        {trade.price.toLocaleString("en-IN")}
      </td>
      <td
        className={cn(
          "py-3 px-4 text-sm text-right font-semibold",
          isProfit ? "text-profit" : "text-loss"
        )}
      >
        {isProfit ? "+" : ""}
        {"\u20B9"}
        {Math.abs(trade.pnl).toLocaleString("en-IN")}
        <span className="ml-1">{isProfit ? "\uD83D\uDFE2" : "\uD83D\uDD34"}</span>
      </td>
    </tr>
  );
}
