"use client";

/**
 * Order Result Card — renders inline after a Go Live submission.
 *
 * Three visual states:
 *
 *   * Live success — 🎉🎉🎉 + broker order id + raw broker_response
 *     details (collapsed by default).
 *   * Dry-run success — 🧪✅ + "all checks passed" summary.
 *   * Block / failure — ⚠️🛑 + Hinglish reason + deep-link to fix.
 *
 * The audit-log id is always surfaced so the operator can copy it
 * into a support ticket if anything goes wrong.
 */

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  FlaskConical,
  ShieldOff,
  Sparkles,
  XCircle,
} from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { LiveOrderResult } from "./go-live-modal";

interface OrderResultCardProps {
  result: LiveOrderResult;
  strategyId: string;
  onPlaceAnother: () => void;
}

export function OrderResultCard({
  result,
  strategyId,
  onPlaceAnother,
}: OrderResultCardProps) {
  if (!result.success) {
    return (
      <BlockedCard
        result={result}
        strategyId={strategyId}
        onPlaceAnother={onPlaceAnother}
      />
    );
  }
  if (result.is_dry_run) {
    return <DryRunCard result={result} onPlaceAnother={onPlaceAnother} />;
  }
  return <LiveSuccessCard result={result} onPlaceAnother={onPlaceAnother} />;
}

// ── Live success ──────────────────────────────────────────────────────

function LiveSuccessCard({
  result,
  onPlaceAnother,
}: {
  result: LiveOrderResult;
  onPlaceAnother: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <GlassmorphismCard hover={false} className="border-profit/30">
        <div className="space-y-3">
          <header className="flex items-start justify-between gap-3 flex-wrap">
            <div className="space-y-1">
              <h3 className="text-base font-semibold flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-profit" />
                🎉🎉🎉 Order placed!
              </h3>
              <p className="text-xs text-muted-foreground">
                Placed at {prettyTime(result.placed_at)}
              </p>
            </div>
            <Badge className="bg-profit/15 text-profit border-profit/30 uppercase text-xs">
              Live
            </Badge>
          </header>

          <FieldRow label="Broker Order ID" value={result.order_id ?? "—"} mono />
          <FieldRow label="Audit Log ID" value={result.audit_log_id} mono />

          {result.broker_response ? (
            <div className="rounded-lg border border-white/[0.06] bg-white/[0.02]">
              <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className="w-full flex items-center justify-between p-2 text-xs font-medium hover:bg-white/[0.04] rounded-lg transition-colors"
              >
                <span>Broker response</span>
                {expanded ? (
                  <ChevronUp className="h-3.5 w-3.5" />
                ) : (
                  <ChevronDown className="h-3.5 w-3.5" />
                )}
              </button>
              {expanded ? (
                <pre className="p-2 text-[10px] font-mono leading-relaxed text-muted-foreground overflow-x-auto border-t border-white/[0.04]">
                  {JSON.stringify(result.broker_response, null, 2)}
                </pre>
              ) : null}
            </div>
          ) : null}

          <div className="flex justify-end pt-1">
            <Button
              variant="outline"
              size="sm"
              onClick={onPlaceAnother}
              type="button"
            >
              Place another order
            </Button>
          </div>
        </div>
      </GlassmorphismCard>
    </motion.div>
  );
}

// ── Dry-run success ────────────────────────────────────────────────────

function DryRunCard({
  result,
  onPlaceAnother,
}: {
  result: LiveOrderResult;
  onPlaceAnother: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <GlassmorphismCard hover={false} className="border-accent-blue/30">
        <div className="space-y-3">
          <header className="flex items-start justify-between gap-3 flex-wrap">
            <div className="space-y-1">
              <h3 className="text-base font-semibold flex items-center gap-2">
                <FlaskConical className="h-4 w-4 text-accent-blue" />
                🧪✅ Dry-run successful
              </h3>
              <p className="text-xs text-muted-foreground">
                Saari safety checks pass huin — no real order placed.
              </p>
            </div>
            <Badge className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 uppercase text-xs">
              Dry-run
            </Badge>
          </header>

          <FieldRow label="Order ID" value={result.order_id ?? "—"} mono />
          <FieldRow label="Audit Log ID" value={result.audit_log_id} mono />

          <div className="rounded-lg bg-accent-blue/10 border border-accent-blue/25 p-2.5 text-xs leading-relaxed">
            Live mode mein switch karke dobara test karo when ready —
            confirmation modal mein dry-run toggle ko OFF kar do.
          </div>

          <div className="flex justify-end pt-1">
            <Button
              variant="outline"
              size="sm"
              onClick={onPlaceAnother}
              type="button"
            >
              Place another order
            </Button>
          </div>
        </div>
      </GlassmorphismCard>
    </motion.div>
  );
}

// ── Blocked ────────────────────────────────────────────────────────────

function BlockedCard({
  result,
  strategyId,
  onPlaceAnother,
}: {
  result: LiveOrderResult;
  strategyId: string;
  onPlaceAnother: () => void;
}) {
  const blocking = result.safety_chain_result.blocking_check;
  const fixLink = fixLinkFor(strategyId, blocking?.check_name ?? null);
  const blockedByGuard =
    !result.broker_guard_passed && result.safety_chain_result.all_passed;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <GlassmorphismCard hover={false} className="border-loss/30">
        <div className="space-y-3">
          <header className="flex items-start justify-between gap-3 flex-wrap">
            <div className="space-y-1">
              <h3 className="text-base font-semibold flex items-center gap-2">
                <ShieldOff className="h-4 w-4 text-loss" />
                ⚠️🛑 Order blocked
              </h3>
              <p className="text-xs text-muted-foreground">
                {result.is_dry_run
                  ? "Dry-run check fail ho gaya — actual order skip"
                  : "Safety chain ne block kar diya — koi order place nahi hua"}
              </p>
            </div>
            <Badge className="bg-loss/15 text-loss border-loss/30 uppercase text-xs">
              {blockedByGuard ? "Broker Guard" : (blocking?.check_name ?? "Blocked")}
            </Badge>
          </header>

          <div className="rounded-lg bg-loss/10 border border-loss/30 p-3 text-xs text-loss leading-relaxed">
            {result.failure_reason_hinglish ??
              "Pre-flight panel mein details dekho."}
          </div>

          <FieldRow label="Audit Log ID" value={result.audit_log_id} mono />

          <div className="flex items-center justify-end gap-2 pt-1 flex-wrap">
            {fixLink ? (
              <Link
                href={fixLink}
                className={cn(
                  "inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md",
                  "bg-accent-blue/15 border border-accent-blue/30 text-accent-blue",
                  "hover:bg-accent-blue/25 transition-colors font-medium",
                )}
              >
                Fix
                <ExternalLink className="h-3 w-3" />
              </Link>
            ) : null}
            <Button
              variant="outline"
              size="sm"
              onClick={onPlaceAnother}
              type="button"
            >
              Try again
            </Button>
          </div>
        </div>
      </GlassmorphismCard>
    </motion.div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────

function FieldRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3 text-xs">
      <span className="text-muted-foreground uppercase tracking-wide text-[10px]">
        {label}
      </span>
      <span
        className={cn(
          "min-w-0 truncate text-right",
          mono ? "font-mono" : "font-medium",
        )}
        title={value}
      >
        {value}
      </span>
    </div>
  );
}

function prettyTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "—";
  }
}

function fixLinkFor(strategyId: string, checkName: string | null): string | null {
  if (!checkName) return null;
  switch (checkName) {
    case "paper_sessions":
      return `/strategies/${strategyId}/paper-sessions`;
    case "trust_score":
    case "truth_score":
    case "stop_loss_present":
      return `/strategies/${strategyId}/backtest`;
    case "broker_connection":
      return "/brokers";
    case "live_trading_enabled":
      return "/settings/account";
    case "auto_kill_switch":
      return "/kill-switch";
    default:
      return null;
  }
}

// Marker icons re-export so a future panel can pick them up.
export { CheckCircle2, XCircle };
