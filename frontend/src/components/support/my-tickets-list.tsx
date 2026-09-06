"use client";

/**
 * Caller's ticket list — newest first, expandable for full
 * description. Status badges colour-coded so the user can see
 * "open vs in_progress vs resolved" at a glance.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, ChevronDown, MessageCircle } from "lucide-react";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { GlassmorphismCard } from "@/shared/ui/glassmorphism-card";
import { useApi } from "@/shared/api/use-api";
import { cn } from "@/shared/lib/utils";

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
  const { data, isLoading, error, refetch } = useApi<TicketsResponse>(
    `/support/tickets/me?_=${refreshKey}`,
    { tickets: [], count: 0 },
  );

  // ``useApi`` keeps the fallback ({tickets: [], count: 0}) on screen when the
  // request fails, so a failed load and a genuinely empty list look identical.
  // Read ``error`` FIRST: an outage must never be reported to a customer as
  // "aapka koi ticket nahi hai".
  const tickets = data?.tickets ?? [];

  if (isLoading) {
    return (
      <GlassmorphismCard hover={false}>
        <p className="text-11 text-muted-foreground">Loading…</p>
      </GlassmorphismCard>
    );
  }

  // Nothing on screen AND the request failed — we do not know what the user
  // has. Say only that, and offer a retry.
  if (error && tickets.length === 0) {
    return (
      <GlassmorphismCard hover={false}>
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-4 w-4 text-loss mt-0.5 shrink-0" />
          <div className="space-y-1">
            <p className="text-sm font-medium text-loss">
              Ticket list load nahi ho payi.
            </p>
            <p className="text-11 text-muted-foreground leading-relaxed">
              Iska matlab yeh nahi ki aapka koi ticket nahi hai — list hum la
              hi nahi paye. Thodi der mein dobara koshish karo.
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={refetch}
              className="mt-2"
            >
              Dobara koshish karo
            </Button>
          </div>
        </div>
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
            <p className="text-11 text-muted-foreground leading-relaxed">
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
      {/* Old rows still on screen but the last refresh failed — say the list
          is stale rather than letting it pass as current. */}
      {error ? (
        <div className="flex items-start gap-2 rounded-lg border border-border bg-loss/5 px-3 py-2">
          <AlertTriangle className="h-3.5 w-3.5 text-loss mt-0.5 shrink-0" />
          <p className="text-11 text-muted-foreground leading-relaxed">
            List abhi refresh nahi ho payi — neeche jo dikh raha hai woh purana
            ho sakta hai.
          </p>
          <Button
            type="button"
            variant="ghost"
            size="xs"
            onClick={refetch}
            className="ml-auto shrink-0"
          >
            Phir se
          </Button>
        </div>
      ) : null}
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
                <Badge className="bg-white/[0.04] text-muted-foreground border-white/[0.06] text-10">
                  {humanCategory(ticket.category)}
                </Badge>
              </div>
              <p className="text-10 text-muted-foreground">
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
            <div className="rounded-md bg-black/30 border border-white/[0.04] p-3 text-11 leading-relaxed whitespace-pre-wrap">
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
    <Badge className={cn("uppercase text-10", palette[status])}>
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
    <Badge className={cn("uppercase text-10", palette[priority])}>
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
