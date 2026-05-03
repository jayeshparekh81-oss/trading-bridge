"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { Activity, Loader2, AlertTriangle, RefreshCw } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Badge } from "@/components/ui/badge";
import { useApi } from "@/lib/use-api";
import { formatCurrency, cn } from "@/lib/utils";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.05 } } };
const fadeUp = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.3 } } };

interface Position {
  id: string;
  strategy_id: string;
  symbol: string;
  side: string;
  total_quantity: number;
  remaining_quantity: number;
  avg_entry_price: string | null;
  target_price: string | null;
  stop_loss_price: string | null;
  highest_price_seen: string | null;
  status: string;
  opened_at: string;
  closed_at: string | null;
  final_pnl: string | null;
}

interface PositionsResponse {
  positions: Position[];
  count: number;
}

type StatusFilter = "all" | "open" | "partial" | "closed";

export default function PositionsPage() {
  const [filter, setFilter] = useState<StatusFilter>("all");
  const url =
    filter === "all"
      ? "/strategies/positions?limit=100"
      : `/strategies/positions?status=${filter}&limit=100`;

  const { data, isLoading, error, refetch } = useApi<PositionsResponse>(url, null, 15_000);

  const positions = data?.positions ?? [];
  const stats = useMemo(() => {
    const open = positions.filter((p) => p.status === "open").length;
    const partial = positions.filter((p) => p.status === "partial").length;
    const closed = positions.filter((p) => p.status === "closed").length;
    return { open, partial, closed, total: positions.length };
  }, [positions]);

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto space-y-6"
    >
      <motion.div
        variants={fadeUp}
        className="flex items-center justify-between flex-wrap gap-4"
      >
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Activity className="h-6 w-6 text-accent-blue" /> Live Positions
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Auto-refreshes every 15s. For direct-exit strategies, position-loop
            does not autonomously trigger — exits arrive as Pine
            PARTIAL/EXIT/SL_HIT webhooks.
          </p>
        </div>
        <GlowButton size="sm" onClick={refetch}>
          <RefreshCw className={cn("h-4 w-4 mr-2", isLoading && "animate-spin")} />
          Refresh
        </GlowButton>
      </motion.div>

      <motion.div variants={fadeUp} className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {(["all", "open", "partial", "closed"] as StatusFilter[]).map((s) => {
          const count =
            s === "all"
              ? stats.total
              : s === "open"
              ? stats.open
              : s === "partial"
              ? stats.partial
              : stats.closed;
          return (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={cn(
                "rounded-lg border px-4 py-3 text-left transition-colors",
                filter === s
                  ? "bg-accent-blue/10 border-accent-blue/40 text-accent-blue"
                  : "bg-white/[0.02] border-white/[0.05] text-muted-foreground hover:bg-white/[0.04]",
              )}
            >
              <div className="text-xs uppercase tracking-wide">{s}</div>
              <div className="text-2xl font-bold mt-1">{count}</div>
            </button>
          );
        })}
      </motion.div>

      <motion.div variants={fadeUp}>
        <GlassmorphismCard hover={false} className="p-0 overflow-hidden">
          {error && !data ? (
            <div className="p-8 text-center">
              <AlertTriangle className="h-10 w-10 text-loss mx-auto mb-3" />
              <h3 className="font-semibold mb-1">Could not load positions</h3>
              <p className="text-sm text-muted-foreground mb-4">{error}</p>
              <GlowButton onClick={refetch} size="sm">Retry</GlowButton>
            </div>
          ) : isLoading && !data ? (
            <div className="p-12 flex justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : positions.length === 0 ? (
            <div className="p-12 text-center">
              <Activity className="h-10 w-10 text-muted-foreground mx-auto mb-3 opacity-50" />
              <h3 className="font-semibold mb-1">
                No positions{filter !== "all" ? ` (${filter})` : ""}
              </h3>
              <p className="text-sm text-muted-foreground">
                TRADETRI is ready to fire on Pine signals. Open positions appear here
                within seconds of a webhook being accepted.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-white/[0.02] text-xs text-muted-foreground uppercase">
                  <tr>
                    <th className="text-left p-3 font-medium">Symbol</th>
                    <th className="text-left p-3 font-medium">Side</th>
                    <th className="text-right p-3 font-medium">Total</th>
                    <th className="text-right p-3 font-medium">Remaining</th>
                    <th className="text-right p-3 font-medium">Entry</th>
                    <th className="text-right p-3 font-medium">Target</th>
                    <th className="text-right p-3 font-medium">SL</th>
                    <th className="text-left p-3 font-medium">Status</th>
                    <th className="text-left p-3 font-medium">Opened</th>
                    <th className="text-right p-3 font-medium">Final P&amp;L</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((p) => (
                    <tr key={p.id} className="border-t border-white/[0.04] hover:bg-white/[0.02]">
                      <td className="p-3 font-mono text-xs">{p.symbol}</td>
                      <td className="p-3">
                        <Badge
                          className={cn(
                            "uppercase text-xs",
                            p.side.toLowerCase() === "buy"
                              ? "bg-profit/15 text-profit border-profit/30"
                              : "bg-loss/15 text-loss border-loss/30",
                          )}
                        >
                          {p.side}
                        </Badge>
                      </td>
                      <td className="p-3 text-right tabular-nums">{p.total_quantity}</td>
                      <td className="p-3 text-right tabular-nums">
                        {p.remaining_quantity}
                        {p.remaining_quantity !== p.total_quantity && (
                          <span className="text-muted-foreground text-xs ml-1">
                            (-{p.total_quantity - p.remaining_quantity})
                          </span>
                        )}
                      </td>
                      <td className="p-3 text-right tabular-nums">
                        {p.avg_entry_price ? formatCurrency(Number(p.avg_entry_price)) : "—"}
                      </td>
                      <td className="p-3 text-right tabular-nums text-muted-foreground">
                        {p.target_price ? formatCurrency(Number(p.target_price)) : "—"}
                      </td>
                      <td className="p-3 text-right tabular-nums text-muted-foreground">
                        {p.stop_loss_price ? formatCurrency(Number(p.stop_loss_price)) : "—"}
                      </td>
                      <td className="p-3">
                        <Badge
                          className={cn(
                            "uppercase text-xs",
                            p.status === "open"
                              ? "bg-accent-blue/15 text-accent-blue border-accent-blue/30"
                              : p.status === "partial"
                              ? "bg-yellow-500/15 text-yellow-500 border-yellow-500/30"
                              : "bg-muted text-muted-foreground border-border",
                          )}
                        >
                          {p.status}
                        </Badge>
                      </td>
                      <td className="p-3 text-xs text-muted-foreground whitespace-nowrap">
                        {new Date(p.opened_at).toLocaleString("en-IN", {
                          dateStyle: "short",
                          timeStyle: "short",
                        })}
                      </td>
                      <td className="p-3 text-right tabular-nums">
                        {p.final_pnl !== null && p.final_pnl !== undefined ? (
                          <span className={Number(p.final_pnl) >= 0 ? "text-profit" : "text-loss"}>
                            {formatCurrency(Number(p.final_pnl), { showSign: true })}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </GlassmorphismCard>
      </motion.div>
    </motion.div>
  );
}
