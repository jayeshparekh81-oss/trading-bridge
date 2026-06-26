"use client";

/**
 * ConvictionSignals — REAL AI conviction view for the authenticated dashboard.
 *
 * Consumes the EXISTING user-scoped endpoint GET /api/strategies/signals
 * (read-only) — which returns ONLY the caller's own signals (WHERE
 * user_id = current_user). So this is private: zero public/cross-user
 * exposure. (The PUBLIC ConvictionPanel on /login + /home stays a labeled
 * EXAMPLE and is untouched.)
 *
 * Per signal: symbol, action, the conviction score (ai_confidence) with a
 * score bar + threshold reference, the engine's verdict (ai_decision), the
 * lifecycle status, the timestamp, and the AI reasoning (expandable).
 *
 * Threshold reference: the validator approves LONG ≥ 0.51 / SHORT ≥ 0.55
 * (regime-adjusted ×1.00–1.15), so we draw a reference marker at 0.51 and
 * label it — but the ✓/✕ verdict shown is the engine's REAL ai_decision,
 * not a re-derivation in the UI.
 */

import { useState } from "react";
import Link from "next/link";
import {
  Loader2,
  ChevronDown,
  CheckCircle2,
  XCircle,
  AlertCircle,
} from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

const THRESHOLD_REF = 0.51; // base LONG approval; SHORT base 0.55; regime-adjusted

interface Signal {
  id: string;
  symbol: string;
  action: string;
  status: string;
  ai_decision: string | null;
  ai_confidence: string | number | null;
  ai_reasoning: string | null;
  received_at: string;
}

interface SignalsResponse {
  signals: Signal[];
  count: number;
}

function statusClass(status: string): string {
  switch (status) {
    case "executed":
      return "text-profit border-profit/30 bg-profit/10";
    case "failed":
    case "rejected":
      return "text-loss border-loss/30 bg-loss/10";
    case "ignored":
      return "text-muted-foreground border-border bg-muted/40";
    default: // received | validating | executing
      return "text-accent-blue border-accent-blue/30 bg-accent-blue/10";
  }
}

function SignalRow({ s }: { s: Signal }) {
  const [open, setOpen] = useState(false);
  const conf = s.ai_confidence != null ? Number(s.ai_confidence) : null;
  const approved = s.ai_decision === "APPROVED";
  const rejected = s.ai_decision === "REJECTED";
  const scored = conf != null && (approved || rejected);
  const pct = conf != null ? Math.max(0, Math.min(100, Math.round(conf * 100))) : 0;

  return (
    <div className="p-3 sm:p-4">
      {/* top line */}
      <div className="flex items-center gap-2.5 flex-wrap">
        <span
          className={cn(
            "text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded-md border",
            s.action === "ENTRY"
              ? "text-accent-blue border-accent-blue/30 bg-accent-blue/10"
              : "text-muted-foreground border-border bg-muted/40",
          )}
        >
          {s.action}
        </span>
        <span className="font-mono text-xs text-foreground/90 truncate max-w-[40%]">{s.symbol}</span>

        <span className="flex-1" />

        {scored ? (
          <span
            className={cn(
              "inline-flex items-center gap-1 text-xs font-medium",
              approved ? "text-profit" : "text-loss",
            )}
          >
            {approved ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
            {approved ? "Approved" : "Rejected"}
            <span className="font-mono tabular-nums">{conf!.toFixed(2)}</span>
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}

        <span
          className={cn(
            "text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded-md border",
            statusClass(s.status),
          )}
        >
          {s.status}
        </span>

        <span className="text-[11px] text-muted-foreground whitespace-nowrap tabular-nums">
          {new Date(s.received_at).toLocaleString("en-IN", {
            day: "2-digit",
            month: "short",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>

      {/* score bar (only for scored entries) */}
      {scored && (
        <div className="mt-2.5 relative h-1.5 rounded-full bg-white/10 overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full",
              approved ? "bg-gradient-to-r from-emerald-500 to-profit" : "bg-loss/70",
            )}
            style={{ width: `${pct}%` }}
          />
          <div
            className="absolute inset-y-0 w-px bg-white/55"
            style={{ left: `${THRESHOLD_REF * 100}%` }}
            aria-hidden="true"
          />
        </div>
      )}

      {/* reasoning (expandable) */}
      {s.ai_reasoning && (
        <div className="mt-2">
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            className="inline-flex items-center gap-1 text-[11px] text-accent-blue hover:underline"
          >
            <ChevronDown className={cn("h-3 w-3 transition-transform", open && "rotate-180")} />
            {open ? "Hide reasoning" : "Why?"}
          </button>
          {open && (
            <p className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground bg-muted/30 rounded-lg p-2.5 whitespace-pre-wrap break-words">
              {s.ai_reasoning}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export function ConvictionSignals() {
  const { data, isLoading, error } = useApi<SignalsResponse>(
    "/strategies/signals?limit=12",
    null,
    30_000,
  );
  const signals = data?.signals ?? [];

  return (
    <GlassmorphismCard hover={false} className="p-0 overflow-hidden">
      <div className="flex items-center justify-between gap-3 p-4 border-b border-white/[0.04]">
        <div>
          <h3 className="font-semibold">AI Conviction — your signals</h3>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Approve ≥ 0.51 (long) · 0.55 (short), regime-adjusted. Verdict is the engine&apos;s
            real decision.
          </p>
        </div>
        <Link href="/trades" className="text-xs text-accent-blue hover:underline whitespace-nowrap">
          View all →
        </Link>
      </div>

      {isLoading && !data ? (
        <div className="flex items-center justify-center gap-2 p-8 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading signals…
        </div>
      ) : error ? (
        <div className="flex items-center justify-center gap-2 p-8 text-sm text-loss">
          <AlertCircle className="h-4 w-4" /> Couldn&apos;t load signals — retrying…
        </div>
      ) : signals.length === 0 ? (
        <div className="p-8 text-center text-sm text-muted-foreground">
          No signals yet. TRADETRI is listening on your webhook URL — the first Pine alert and
          its conviction score will appear here.
        </div>
      ) : (
        <div className="divide-y divide-white/[0.04]">
          {signals.map((s) => (
            <SignalRow key={s.id} s={s} />
          ))}
        </div>
      )}
    </GlassmorphismCard>
  );
}
