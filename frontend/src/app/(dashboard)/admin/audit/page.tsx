"use client";

/**
 * /admin/audit — paginated audit-log viewer.
 *
 * Wire: GET /api/admin/audit-logs (existing). Filter by action + user_id.
 */

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { History, Search } from "lucide-react";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useApi } from "@/lib/use-api";
import { relativeTime, cn } from "@/lib/utils";

interface AuditEntry {
  id: string;
  user_id: string | null;
  actor: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  ip_address: string | null;
  created_at: string | null;
}

interface AuditList {
  total: number;
  skip: number;
  limit: number;
  logs: AuditEntry[];
}

const PAGE_SIZE = 50;
const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

const ACTION_TONE: Record<string, string> = {
  login: "bg-accent-blue/15 text-accent-blue border-accent-blue/30",
  logout: "bg-white/[0.03] text-muted-foreground",
  kill_switch_trip: "bg-loss/15 text-loss border-loss/30",
  kill_switch_reset: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  config_change: "bg-amber-500/10 text-amber-300 border-amber-500/30",
  broker_connect: "bg-profit/15 text-profit border-profit/30",
};

export default function AdminAuditPage() {
  const [actionFilter, setActionFilter] = useState("");
  const [userIdFilter, setUserIdFilter] = useState("");
  const [page, setPage] = useState(0);

  const url = useMemo(() => {
    const qs = new URLSearchParams();
    qs.set("skip", String(page * PAGE_SIZE));
    qs.set("limit", String(PAGE_SIZE));
    if (actionFilter.trim()) qs.set("action", actionFilter.trim());
    if (userIdFilter.trim()) qs.set("user_id", userIdFilter.trim());
    return `/admin/audit-logs?${qs.toString()}`;
  }, [page, actionFilter, userIdFilter]);

  const { data, isLoading } = useApi<AuditList>(url);
  const logs = data?.logs ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={fadeUp}
      className="p-4 md:p-6 lg:p-8 max-w-6xl mx-auto space-y-5"
    >
      <header className="space-y-1">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <History className="h-6 w-6 text-accent-blue" /> Audit logs
        </h1>
        <p className="text-muted-foreground text-sm">
          Platform-wide audit trail. Filter by action token or user UUID.
        </p>
      </header>

      <GlassmorphismCard className="p-3 grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Action token (e.g., login, kill_switch_trip)"
            value={actionFilter}
            onChange={(e) => {
              setActionFilter(e.target.value);
              setPage(0);
            }}
            className="pl-9"
          />
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="User UUID (full)"
            value={userIdFilter}
            onChange={(e) => {
              setUserIdFilter(e.target.value);
              setPage(0);
            }}
            className="pl-9 font-mono"
          />
        </div>
      </GlassmorphismCard>

      <GlassmorphismCard className="overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-muted-foreground">Loading audit logs…</div>
        ) : logs.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground">
            No audit entries match these filters.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-xs text-muted-foreground uppercase tracking-wider">
              <tr className="border-b border-border">
                <th className="text-left px-4 py-3">When</th>
                <th className="text-left px-4 py-3">Action</th>
                <th className="text-left px-4 py-3">Actor / User</th>
                <th className="text-left px-4 py-3">Resource</th>
                <th className="text-left px-4 py-3">IP</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className="border-b border-border/40 hover:bg-white/[0.02]">
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {log.created_at ? relativeTime(log.created_at) : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <Badge
                      className={cn(
                        ACTION_TONE[log.action] ??
                          "bg-white/[0.03] text-muted-foreground border-border",
                      )}
                    >
                      {log.action}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-xs">
                    <div>{log.actor}</div>
                    {log.user_id && (
                      <div className="font-mono text-muted-foreground">
                        {log.user_id.slice(0, 8)}…
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs">
                    {log.resource_type ? (
                      <>
                        <div>{log.resource_type}</div>
                        {log.resource_id && (
                          <div className="font-mono text-muted-foreground">
                            {log.resource_id.length > 12
                              ? `${log.resource_id.slice(0, 12)}…`
                              : log.resource_id}
                          </div>
                        )}
                      </>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                    {log.ip_address ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </GlassmorphismCard>

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {total.toLocaleString()} entries · page {page + 1} of {totalPages}
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
