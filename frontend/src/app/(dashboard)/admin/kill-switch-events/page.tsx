"use client";

/**
 * /admin/kill-switch-events — platform-wide kill-switch trip timeline.
 *
 * Wire: GET /api/admin/kill-switch-events (existing). Paginated, 50/page.
 */

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { ShieldAlert, AlertTriangle, CheckCircle2 } from "lucide-react";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { useApi } from "@/lib/use-api";
import { relativeTime, cn } from "@/lib/utils";

interface KsEvent {
  id: string;
  user_id: string;
  reason: string;
  daily_pnl_at_trigger: string;
  triggered_at: string | null;
  reset_at: string | null;
}

interface KsEventList {
  total: number;
  skip: number;
  limit: number;
  events: KsEvent[];
}

const PAGE_SIZE = 50;
const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

function formatRupees(s: string): string {
  const n = Number.parseFloat(s);
  if (!Number.isFinite(n)) return s;
  const sign = n < 0 ? "-" : n > 0 ? "+" : "";
  const abs = Math.abs(n).toLocaleString("en-IN", {
    maximumFractionDigits: 2,
  });
  return `${sign}₹${abs}`;
}

export default function AdminKsEventsPage() {
  const [page, setPage] = useState(0);

  const url = useMemo(() => {
    const qs = new URLSearchParams();
    qs.set("skip", String(page * PAGE_SIZE));
    qs.set("limit", String(PAGE_SIZE));
    return `/admin/kill-switch-events?${qs.toString()}`;
  }, [page]);

  const { data, isLoading } = useApi<KsEventList>(url);
  const events = data?.events ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const stillActive = events.filter((e) => !e.reset_at).length;

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={fadeUp}
      className="p-4 md:p-6 lg:p-8 max-w-6xl mx-auto space-y-5"
    >
      <header className="space-y-1">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <ShieldAlert className="h-6 w-6 text-loss" /> Kill-switch events
        </h1>
        <p className="text-muted-foreground text-sm">
          Every kill-switch trip across the platform. Per-user history lives on{" "}
          <code className="text-xs bg-white/[0.05] px-1 py-0.5 rounded">/kill-switch</code>; this
          admin view is the ops-scale superset.
        </p>
      </header>

      {!isLoading && events.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <GlassmorphismCard className="p-4">
            <div className="text-xs text-muted-foreground">Total events shown</div>
            <div className="text-2xl font-semibold">{events.length}</div>
          </GlassmorphismCard>
          <GlassmorphismCard className="p-4">
            <div className="text-xs text-muted-foreground">Still active</div>
            <div className={cn("text-2xl font-semibold", stillActive > 0 && "text-loss")}>
              {stillActive}
            </div>
          </GlassmorphismCard>
          <GlassmorphismCard className="p-4">
            <div className="text-xs text-muted-foreground">All-time total</div>
            <div className="text-2xl font-semibold">{total.toLocaleString()}</div>
          </GlassmorphismCard>
        </div>
      )}

      <GlassmorphismCard className="overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-muted-foreground">Loading events…</div>
        ) : events.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground">
            No kill-switch events recorded.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-xs text-muted-foreground uppercase tracking-wider">
              <tr className="border-b border-border">
                <th className="text-left px-4 py-3">Triggered</th>
                <th className="text-left px-4 py-3">User</th>
                <th className="text-left px-4 py-3">Reason</th>
                <th className="text-right px-4 py-3">P&amp;L at trigger</th>
                <th className="text-left px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => {
                const isActive = !e.reset_at;
                return (
                  <tr
                    key={e.id}
                    className={cn(
                      "border-b border-border/40 hover:bg-white/[0.02]",
                      isActive && "bg-loss/[0.04]",
                    )}
                  >
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {e.triggered_at ? relativeTime(e.triggered_at) : "—"}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                      {e.user_id.slice(0, 8)}…
                    </td>
                    <td className="px-4 py-3 text-xs">{e.reason}</td>
                    <td className="px-4 py-3 text-right font-mono text-xs">
                      <span
                        className={cn(
                          Number.parseFloat(e.daily_pnl_at_trigger) < 0 ? "text-loss" : "",
                        )}
                      >
                        {formatRupees(e.daily_pnl_at_trigger)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {isActive ? (
                        <Badge className="bg-loss/15 text-loss border-loss/30 flex items-center gap-1 w-fit">
                          <AlertTriangle className="h-3 w-3" />
                          Still tripped
                        </Badge>
                      ) : (
                        <Badge className="bg-profit/15 text-profit border-profit/30 flex items-center gap-1 w-fit">
                          <CheckCircle2 className="h-3 w-3" />
                          Reset {relativeTime(e.reset_at!)}
                        </Badge>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </GlassmorphismCard>

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {total.toLocaleString()} events · page {page + 1} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0 || isLoading}
              className="px-3 py-1.5 rounded-lg border border-border hover:bg-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1 || isLoading}
              className="px-3 py-1.5 rounded-lg border border-border hover:bg-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </motion.div>
  );
}
