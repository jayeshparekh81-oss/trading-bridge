"use client";

/**
 * Caller's ticket list — newest first, expandable for full
 * description. Status badges colour-coded so the user can see
 * "open vs in_progress vs resolved" at a glance.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import { ChevronDown, MessageCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

interface SupportTicket {
  id: string;
  user_id: string;
  category: string;
  subject: string;
  description: string;
  status: "open" | "in_progress" | "awaiting_user" | "resolved" | "closed";
  priority: "low" | "medium" | "high" | "critical";
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

interface TicketsResponse {
  tickets: SupportTicket[];
  count: number;
}

interface MyTicketsListProps {
  refreshKey: number;
}

export function MyTicketsList({ refreshKey }: MyTicketsListProps) {
  // Mount ``refreshKey`` into the URL so the useApi hook re-fetches
  // when the parent bumps the key after a fresh ticket submission.
  const { data, isLoading } = useApi<TicketsResponse>(
    `/support/tickets/me?_=${refreshKey}`,
    { tickets: [], count: 0 },
  );

  if (isLoading) {
    return (
      <GlassmorphismCard hover={false}>
        <p className="text-[11px] text-muted-foreground">Loading…</p>
      </GlassmorphismCard>
    );
  }

  if (!data || data.count === 0) {
    return (
      <GlassmorphismCard hover={false}>
        <div className="flex items-start gap-3">
          <MessageCircle className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
          <div className="space-y-1">
            <p className="text-sm font-medium">Abhi tak koi ticket nahi.</p>
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              Koi issue ho ya question ho? Naya Ticket tab pe ja ke
              file kar do — admin team check karegi.
            </p>
          </div>
        </div>
      </GlassmorphismCard>
    );
  }

  return (
    <div className="space-y-2">
      {data.tickets.map((ticket) => (
        <TicketRow key={ticket.id} ticket={ticket} />
      ))}
    </div>
  );
}

function TicketRow({ ticket }: { ticket: SupportTicket }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <motion.div
      whileHover={{ scale: 1.005 }}
      transition={{ type: "spring", stiffness: 400, damping: 30 }}
    >
      <GlassmorphismCard hover={false}>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="w-full text-left space-y-2"
        >
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div className="space-y-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-sm font-semibold truncate min-w-0">
                  {ticket.subject}
                </h3>
                <StatusBadge status={ticket.status} />
                <PriorityBadge priority={ticket.priority} />
                <Badge className="bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
                  {humanCategory(ticket.category)}
                </Badge>
              </div>
              <p className="text-[10px] text-muted-foreground">
                {new Date(ticket.created_at).toLocaleString("en-IN")}
                {ticket.resolved_at != null
                  ? ` · resolved ${new Date(ticket.resolved_at).toLocaleDateString("en-IN")}`
                  : null}
              </p>
            </div>
            <ChevronDown
              className={cn(
                "h-3.5 w-3.5 text-muted-foreground shrink-0 transition-transform",
                expanded && "rotate-180",
              )}
            />
          </div>
          {expanded ? (
            <div className="rounded-md bg-black/30 border border-white/[0.04] p-3 text-[11px] leading-relaxed whitespace-pre-wrap">
              {ticket.description}
            </div>
          ) : null}
        </button>
      </GlassmorphismCard>
    </motion.div>
  );
}

function StatusBadge({ status }: { status: SupportTicket["status"] }) {
  const palette: Record<SupportTicket["status"], string> = {
    open: "bg-accent-blue/15 text-accent-blue border-accent-blue/30",
    in_progress: "bg-amber-400/15 text-amber-300 border-amber-300/30",
    awaiting_user: "bg-amber-400/15 text-amber-300 border-amber-300/30",
    resolved: "bg-profit/15 text-profit border-profit/30",
    closed: "bg-white/[0.04] text-muted-foreground border-white/[0.06]",
  };
  return (
    <Badge className={cn("uppercase text-[10px]", palette[status])}>
      {status.replace("_", " ")}
    </Badge>
  );
}

function PriorityBadge({ priority }: { priority: SupportTicket["priority"] }) {
  if (priority === "low" || priority === "medium") return null;
  const palette: Record<"high" | "critical", string> = {
    high: "bg-amber-400/15 text-amber-300 border-amber-300/30",
    critical: "bg-loss/15 text-loss border-loss/30",
  };
  return (
    <Badge className={cn("uppercase text-[10px]", palette[priority])}>
      {priority}
    </Badge>
  );
}

function humanCategory(c: string): string {
  return c
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
