"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import {
  History,
  Loader2,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Badge } from "@/components/ui/badge";
import { useApi } from "@/lib/use-api";
import { formatCurrency, cn } from "@/lib/utils";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.05 } } };
const fadeUp = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.3 } } };

interface Execution {
  id: string;
  signal_id: string;
  leg_number: number;
  leg_role: string;
  symbol: string;
  side: string;
  quantity: number;
  order_type: string;
  price: string | null;
  broker_order_id: string | null;
  broker_status: string | null;
  error_code: string | null;
  error_message: string | null;
  placed_at: string;
  completed_at: string | null;
}

interface ExecutionsResponse {
  executions: Execution[];
  count: number;
}

type LegFilter = "all" | "entry" | "direct_partial" | "direct_exit" | "direct_sl" | "partial_target" | "trailing_sl" | "hard_sl";

const LEG_ROLE_LABEL: Record<string, { label: string; cls: string }> = {
  entry: { label: "ENTRY", cls: "bg-accent-blue/15 text-accent-blue border-accent-blue/30" },
  direct_partial: { label: "PARTIAL", cls: "bg-yellow-500/15 text-yellow-500 border-yellow-500/30" },
  direct_exit: { label: "EXIT", cls: "bg-profit/15 text-profit border-profit/30" },
  direct_sl: { label: "SL_HIT", cls: "bg-loss/15 text-loss border-loss/30" },
  partial_target: { label: "PARTIAL", cls: "bg-yellow-500/15 text-yellow-500 border-yellow-500/30" },
  trailing_sl: { label: "TRAIL_SL", cls: "bg-orange-500/15 text-orange-500 border-orange-500/30" },
  hard_sl: { label: "HARD_SL", cls: "bg-loss/15 text-loss border-loss/30" },
  circuit_breaker: { label: "BREAKER", cls: "bg-loss/15 text-loss border-loss/30" },
  kill_switch: { label: "KILL_SW", cls: "bg-loss/15 text-loss border-loss/30" },
};

export default function TradesPage() {
  const [legFilter, setLegFilter] = useState<LegFilter>("all");

  const { data, isLoading, error, refetch } = useApi<ExecutionsResponse>(
    "/strategies/executions?limit=200",
    null,
    60_000,
  );

  const all = data?.executions ?? [];
  const filtered = useMemo(
    () => (legFilter === "all" ? all : all.filter((e) => e.leg_role === legFilter)),
    [all, legFilter],
  );

  const stats = useMemo(() => {
    const entries = all.filter((e) => e.leg_role === "entry").length;
    const exits = all.filter((e) =>
      ["direct_exit", "direct_partial", "direct_sl", "partial_target", "trailing_sl", "hard_sl"].includes(e.leg_role),
    ).length;
    return { total: all.length, entries, exits };
  }, [all]);

  const filterChips: LegFilter[] = ["all", "entry", "direct_partial", "direct_exit", "direct_sl"];

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto space-y-6"
    >
      <motion.div variants={fadeUp} className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <History className="h-6 w-6 text-accent-blue" /> Trade History
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Strategy-engine executions: every entry-leg + every exit (PARTIAL / EXIT / SL_HIT). Auto-refresh 60s.
          </p>
        </div>
        <GlowButton size="sm" onClick={refetch}>
          <RefreshCw className={cn("h-4 w-4 mr-2", isLoading && "animate-spin")} /> Refresh
        </GlowButton>
      </motion.div>

      <motion.div variants={fadeUp} className="grid grid-cols-3 gap-3">
        <div className="rounded-lg border border-white/[0.05] bg-white/[0.02] p-4">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">Total executions</div>
          <div className="text-2xl font-bold mt-1">{stats.total}</div>
        </div>
        <div className="rounded-lg border border-white/[0.05] bg-white/[0.02] p-4">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">Entry legs</div>
          <div className="text-2xl font-bold mt-1 text-accent-blue">{stats.entries}</div>
        </div>
        <div className="rounded-lg border border-white/[0.05] bg-white/[0.02] p-4">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">Exits</div>
          <div className="text-2xl font-bold mt-1 text-profit">{stats.exits}</div>
        </div>
      </motion.div>

      <motion.div variants={fadeUp} className="flex flex-wrap gap-2">
        {filterChips.map((f) => (
          <button
            key={f}
            onClick={() => setLegFilter(f)}
            className={cn(
              "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
              legFilter === f
                ? "bg-accent-blue/15 border-accent-blue/40 text-accent-blue"
                : "bg-white/[0.02] border-white/[0.05] text-muted-foreground hover:bg-white/[0.04]",
            )}
          >
            {f === "all" ? "All" : LEG_ROLE_LABEL[f]?.label ?? f}
          </button>
        ))}
      </motion.div>

      <motion.div variants={fadeUp}>
        <GlassmorphismCard hover={false} className="p-0 overflow-hidden">
          {error && !data ? (
            <div className="p-8 text-center">
              <AlertTriangle className="h-10 w-10 text-loss mx-auto mb-3" />
              <h3 className="font-semibold mb-1">Could not load trade history</h3>
              <p className="text-sm text-muted-foreground mb-4">{error}</p>
              <GlowButton onClick={refetch} size="sm">Retry</GlowButton>
            </div>
          ) : isLoading && !data ? (
            <div className="p-12 flex justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="p-12 text-center">
              <History className="h-10 w-10 text-muted-foreground mx-auto mb-3 opacity-50" />
              <h3 className="font-semibold mb-1">No executions{legFilter !== "all" ? ` (${LEG_ROLE_LABEL[legFilter]?.label ?? legFilter})` : ""}</h3>
              <p className="text-sm text-muted-foreground">
                Executions appear here as Pine signals are processed and orders placed.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-white/[0.02] text-xs text-muted-foreground uppercase">
                  <tr>
                    <th className="text-left p-3 font-medium">Placed</th>
                    <th className="text-left p-3 font-medium">Type</th>
                    <th className="text-left p-3 font-medium">Symbol</th>
                    <th className="text-left p-3 font-medium">Side</th>
                    <th className="text-right p-3 font-medium">Qty</th>
                    <th className="text-right p-3 font-medium">Price</th>
                    <th className="text-left p-3 font-medium">Broker order</th>
                    <th className="text-left p-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((e) => {
                    const role = LEG_ROLE_LABEL[e.leg_role] ?? { label: e.leg_role, cls: "bg-muted text-muted-foreground" };
                    const isError = !!e.error_code;
                    return (
                      <tr key={e.id} className={cn("border-t border-white/[0.04] hover:bg-white/[0.02]", isError && "bg-loss/5")}>
                        <td className="p-3 text-xs text-muted-foreground whitespace-nowrap">
                          {new Date(e.placed_at).toLocaleString("en-IN", {
                            dateStyle: "short",
                            timeStyle: "medium",
                          })}
                        </td>
                        <td className="p-3">
                          <Badge className={cn("uppercase text-xs", role.cls)}>{role.label}</Badge>
                        </td>
                        <td className="p-3 font-mono text-xs">{e.symbol}</td>
                        <td className="p-3">
                          <span
                            className={cn(
                              "uppercase text-xs font-medium",
                              e.side.toLowerCase() === "buy" ? "text-profit" : "text-loss",
                            )}
                          >
                            {e.side}
                          </span>
                        </td>
                        <td className="p-3 text-right tabular-nums">{e.quantity}</td>
                        <td className="p-3 text-right tabular-nums">
                          {e.price ? formatCurrency(Number(e.price)) : "—"}
                        </td>
                        <td className="p-3 font-mono text-xs text-muted-foreground max-w-[200px] truncate">
                          {e.broker_order_id ?? "—"}
                        </td>
                        <td className="p-3">
                          {isError ? (
                            <Badge className="uppercase text-xs bg-loss/15 text-loss border-loss/30">
                              {e.error_code}
                            </Badge>
                          ) : e.broker_status ? (
                            <Badge className="uppercase text-xs bg-profit/15 text-profit border-profit/30">
                              {e.broker_status}
                            </Badge>
                          ) : (
                            <span className="text-xs text-muted-foreground">pending</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </GlassmorphismCard>
      </motion.div>
    </motion.div>
  );
}
