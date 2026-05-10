"use client";

import Link from "next/link";
import { ShieldCheck, ShieldX, ArrowUpRight } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

/**
 * READ-ONLY summary of the user's auto kill switch. Mirrors the
 * status the dedicated /kill-switch page renders, links over to it
 * for any action. This component DOES NOT trip / reset the switch —
 * those flows live solely in /kill-switch.
 */

interface KillSwitchStatus {
  state: "ACTIVE" | "TRIPPED";
  daily_pnl: string;
  max_daily_loss_inr: string;
  remaining_loss_budget: string;
  trades_today: number;
  max_daily_trades: number;
  remaining_trades: number;
  enabled: boolean;
  tripped_at: string | null;
  trip_reason: string | null;
}

export function KillSwitchSummary({ className }: { className?: string }) {
  const { data, isLoading, error } = useApi<KillSwitchStatus>(
    "/kill-switch/status",
    null,
    30_000,
  );

  return (
    <GlassmorphismCard hover={false} className={className}>
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1.5 min-w-0">
          <div className="flex items-center gap-2">
            {data?.state === "TRIPPED" ? (
              <ShieldX className="h-4 w-4 text-loss" />
            ) : (
              <ShieldCheck className="h-4 w-4 text-profit" />
            )}
            <h3 className="text-sm font-semibold">Auto Kill Switch</h3>
          </div>
          {isLoading && !data ? (
            <p className="text-xs text-muted-foreground">Loading status…</p>
          ) : error && !data ? (
            <p className="text-xs text-loss">Could not load status: {error}</p>
          ) : data ? (
            <KillSwitchStatusLine status={data} />
          ) : (
            <p className="text-xs text-muted-foreground">
              No kill switch configured.
            </p>
          )}
        </div>
        <Link
          href="/kill-switch"
          className={cn(
            "inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-md",
            "bg-white/[0.04] border border-white/[0.06] text-muted-foreground",
            "hover:bg-white/[0.07] hover:text-foreground transition-colors shrink-0",
          )}
        >
          Manage
          <ArrowUpRight className="h-3 w-3" />
        </Link>
      </div>
    </GlassmorphismCard>
  );
}

function KillSwitchStatusLine({ status }: { status: KillSwitchStatus }) {
  if (status.state === "TRIPPED") {
    return (
      <p className="text-xs text-loss leading-relaxed">
        TRIPPED{status.trip_reason ? ` — ${status.trip_reason}` : ""}. Reset on
        the kill switch page before live trading resumes.
      </p>
    );
  }
  if (!status.enabled) {
    return (
      <p className="text-xs text-muted-foreground leading-relaxed">
        Disabled. Configure daily loss + trade caps to protect your capital.
      </p>
    );
  }
  return (
    <p className="text-xs text-muted-foreground leading-relaxed">
      Active. ₹{status.remaining_loss_budget} loss budget left,{" "}
      {status.remaining_trades} of {status.max_daily_trades} trades remaining.
    </p>
  );
}
