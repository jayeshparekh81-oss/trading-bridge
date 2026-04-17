"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { FileText, Search, Download, ChevronDown, Clock, Shield, User, Bot } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { adminMockData, type AuditLogEntry } from "@/lib/admin-mock-data";
import { cn, relativeTime } from "@/lib/utils";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.04 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

const actorStyles = {
  system: { color: "text-accent-blue border-accent-blue/30", icon: Bot },
  user: { color: "text-profit border-profit/30", icon: User },
  admin: { color: "text-accent-purple border-accent-purple/30", icon: Shield },
};

export default function AuditLogsPage() {
  const [actionFilter, setActionFilter] = useState("all");
  const [expanded, setExpanded] = useState<string | null>(null);

  const logs = adminMockData.auditLogs.filter((l) =>
    actionFilter === "all" || l.action.includes(actionFilter)
  );

  const uniqueActions = [...new Set(adminMockData.auditLogs.map((l) => l.action))];

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto space-y-6">
      <motion.div variants={fadeUp} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2"><FileText className="h-6 w-6 text-accent-purple" /> Audit Logs</h1>
          <p className="text-muted-foreground text-sm mt-1">{logs.length} entries</p>
        </div>
        <div className="flex gap-2">
          <Badge variant="outline" className="text-xs text-muted-foreground">Immutable &mdash; logs cannot be modified</Badge>
          <button className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border hover:bg-accent transition-colors text-sm">
            <Download className="h-4 w-4" />Export
          </button>
        </div>
      </motion.div>

      {/* Filters */}
      <motion.div variants={fadeUp} className="flex flex-wrap gap-3">
        <select value={actionFilter} onChange={(e) => setActionFilter(e.target.value)} className="h-9 px-3 rounded-lg bg-muted/50 border border-border text-sm">
          <option value="all">All Actions</option>
          {uniqueActions.map((a) => <option key={a} value={a}>{a.replace(/_/g, " ")}</option>)}
        </select>
      </motion.div>

      {/* Log Table */}
      <motion.div variants={fadeUp}>
        <GlassmorphismCard hover={false} className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/[0.08]">
                  {["Time", "Actor", "Action", "Resource", "IP", ""].map((h) => (
                    <th key={h} className="text-left py-2.5 px-4 text-xs font-medium text-muted-foreground uppercase">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => {
                  const style = actorStyles[log.actor];
                  const Icon = style.icon;
                  const isExpanded = expanded === log.id;
                  return (
                    <motion.tr
                      key={log.id}
                      variants={fadeUp}
                      className="border-b border-white/[0.04] cursor-pointer hover:bg-white/[0.02]"
                      onClick={() => setExpanded(isExpanded ? null : log.id)}
                    >
                      <td className="py-3 px-4 text-xs text-muted-foreground whitespace-nowrap">
                        <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{new Date(log.time).toLocaleTimeString("en-IN")}</span>
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant="outline" className={cn("text-xs capitalize", style.color)}>
                          <Icon className="h-3 w-3 mr-1" />{log.actor}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 text-sm font-mono">{log.action}</td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">{log.resource} {log.resourceId && `#${log.resourceId}`}</td>
                      <td className="py-3 px-4 text-xs font-mono text-muted-foreground">{log.ip || "—"}</td>
                      <td className="py-3 px-4">
                        <ChevronDown className={cn("h-4 w-4 transition-transform text-muted-foreground", isExpanded && "rotate-180")} />
                      </td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Expanded metadata */}
          <AnimatePresence>
            {expanded && (() => {
              const log = logs.find((l) => l.id === expanded);
              if (!log) return null;
              return (
                <motion.div
                  key={expanded}
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="border-t border-white/[0.08] overflow-hidden"
                >
                  <div className="p-4">
                    <p className="text-xs text-muted-foreground mb-2">Metadata</p>
                    <pre className="text-xs bg-white/[0.03] rounded-lg p-3 font-mono overflow-x-auto">
                      {JSON.stringify(log.metadata, null, 2)}
                    </pre>
                  </div>
                </motion.div>
              );
            })()}
          </AnimatePresence>
        </GlassmorphismCard>
      </motion.div>
    </motion.div>
  );
}
