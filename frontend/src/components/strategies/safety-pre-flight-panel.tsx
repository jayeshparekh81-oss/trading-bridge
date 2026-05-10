"use client";

/**
 * Safety Pre-Flight Panel — strategy detail page surface.
 *
 * Polls the backend's GET /api/orders/live/preflight endpoint and
 * renders every safety check's verdict so the user can see what
 * still needs to clear before they're allowed to place a live
 * order. Each failing row carries a deep-link to the page that
 * fixes it (paper sessions → paper-sessions page, scores → backtest,
 * broker → /brokers, etc).
 *
 * The panel is intentionally read-only: no buttons besides Refresh.
 * The actual Go Live action lives in the sibling `GoLiveButton`
 * component which consumes the verdict via the `onResult` callback
 * so the button can disable itself until every check passes.
 */

import { useEffect } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ShieldCheck,
  RefreshCw,
  ExternalLink,
} from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

// ── Wire types ─────────────────────────────────────────────────────────

export interface SafetyCheckResult {
  check_name: string;
  passed: boolean;
  reason_hinglish: string;
  details: Record<string, unknown>;
}

export interface SafetyChainResult {
  all_passed: boolean;
  checks: SafetyCheckResult[];
  blocking_check: SafetyCheckResult | null;
  user_id: string;
  strategy_id: string;
  checked_at: string;
}

// ── Hinglish labels for each check ─────────────────────────────────────

const CHECK_LABELS: Record<string, string> = {
  auto_kill_switch: "Kill Switch Status",
  paper_sessions: "Paper Sessions (7 chahiye)",
  trust_score: "Trust Score (70+ chahiye)",
  truth_score: "Truth Score (55+ chahiye)",
  live_trading_enabled: "Live Trading Permission",
  broker_connection: "Broker Connection",
  risk_engine_precheck: "Risk Engine Pre-Check",
};

function fixLinkFor(strategyId: string, checkName: string): string | null {
  switch (checkName) {
    case "paper_sessions":
      return `/strategies/${strategyId}/paper-sessions`;
    case "trust_score":
    case "truth_score":
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

// ── Component ──────────────────────────────────────────────────────────

interface SafetyPreFlightPanelProps {
  strategyId: string;
  /** Notified on every successful preflight fetch. The parent uses
   *  this to gate the Go Live button. */
  onResult?: (result: SafetyChainResult) => void;
}

export function SafetyPreFlightPanel({
  strategyId,
  onResult,
}: SafetyPreFlightPanelProps) {
  const { data: result, isLoading, error, refetch } = useApi<SafetyChainResult>(
    `/orders/live/preflight?strategy_id=${strategyId}`,
    null,
  );

  // Notify the parent whenever a fresh verdict lands. Pure side-effect
  // — no local setState here, so the React Compiler doesn't flag it.
  useEffect(() => {
    if (result && onResult) onResult(result);
  }, [result, onResult]);

  const checkedAtPretty = formatChecked(result?.checked_at ?? null);
  const failingCount = result ? result.checks.filter((c) => !c.passed).length : 0;

  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-4">
        <header className="flex items-start justify-between gap-3 flex-wrap">
          <div className="space-y-1">
            <h2 className="text-base font-semibold flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-accent-blue" />
              Safety Pre-Flight Check
            </h2>
            {checkedAtPretty ? (
              <p className="text-[11px] text-muted-foreground">
                Last checked: {checkedAtPretty}
              </p>
            ) : null}
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {result ? (
              <OverallStatusBadge
                allPassed={result.all_passed}
                failingCount={failingCount}
              />
            ) : null}
            <Button
              variant="ghost"
              size="sm"
              onClick={refetch}
              disabled={isLoading}
              type="button"
            >
              <RefreshCw
                className={cn(
                  "h-3.5 w-3.5",
                  isLoading && "animate-spin",
                )}
              />
              Refresh
            </Button>
          </div>
        </header>

        {error ? (
          <div className="rounded-lg bg-loss/10 border border-loss/30 p-3 text-xs text-loss">
            {error}
          </div>
        ) : null}

        {isLoading && !result ? (
          <CheckListSkeleton />
        ) : result ? (
          <ul className="space-y-2">
            {result.checks.map((check) => (
              <CheckRow
                key={check.check_name}
                check={check}
                strategyId={strategyId}
              />
            ))}
          </ul>
        ) : null}
      </div>
    </GlassmorphismCard>
  );
}

// ── Overall status badge ───────────────────────────────────────────────

function OverallStatusBadge({
  allPassed,
  failingCount,
}: {
  allPassed: boolean;
  failingCount: number;
}) {
  if (allPassed) {
    return (
      <Badge className="bg-profit/15 text-profit border-profit/30 uppercase text-xs">
        🛡️🎉 Live trading ke liye ready
      </Badge>
    );
  }
  return (
    <Badge className="bg-loss/15 text-loss border-loss/30 uppercase text-xs">
      ⚠️ {failingCount} {failingCount === 1 ? "issue" : "issues"} fix karne hain
    </Badge>
  );
}

// ── Per-check row ──────────────────────────────────────────────────────

function CheckRow({
  check,
  strategyId,
}: {
  check: SafetyCheckResult;
  strategyId: string;
}) {
  const label = CHECK_LABELS[check.check_name] ?? check.check_name;
  const fixLink = !check.passed ? fixLinkFor(strategyId, check.check_name) : null;
  const isDeferredPass =
    check.passed && Boolean((check.details as Record<string, unknown>)?.deferred);

  return (
    <motion.li
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.18 }}
      className={cn(
        "flex items-start gap-3 rounded-lg p-3",
        check.passed
          ? "bg-profit/5 border border-profit/15"
          : "bg-loss/5 border border-loss/20",
      )}
    >
      <CheckIcon passed={check.passed} deferred={isDeferredPass} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium">{label}</span>
          {isDeferredPass ? (
            <Badge className="bg-amber-500/15 text-amber-400 border-amber-400/30 text-[10px]">
              DEFERRED
            </Badge>
          ) : null}
        </div>
        <p
          className={cn(
            "text-xs mt-0.5 leading-relaxed",
            check.passed ? "text-muted-foreground" : "text-loss",
          )}
        >
          {check.reason_hinglish}
        </p>
      </div>
      {fixLink ? (
        <Link
          href={fixLink}
          className={cn(
            "inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md shrink-0",
            "bg-accent-blue/15 border border-accent-blue/30 text-accent-blue",
            "hover:bg-accent-blue/25 transition-colors font-medium",
          )}
        >
          Fix
          <ExternalLink className="h-3 w-3" />
        </Link>
      ) : null}
    </motion.li>
  );
}

function CheckIcon({
  passed,
  deferred,
}: {
  passed: boolean;
  deferred: boolean;
}) {
  if (deferred) {
    return <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />;
  }
  if (passed) {
    return <CheckCircle2 className="h-4 w-4 text-profit shrink-0 mt-0.5" />;
  }
  return <XCircle className="h-4 w-4 text-loss shrink-0 mt-0.5" />;
}

// ── Formatters ─────────────────────────────────────────────────────────

function formatChecked(iso: string | null): string | null {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleTimeString("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return null;
  }
}

// ── Loading skeleton ───────────────────────────────────────────────────

function CheckListSkeleton() {
  return (
    <ul className="space-y-2">
      {[0, 1, 2, 3, 4, 5, 6].map((i) => (
        <li
          key={i}
          className="flex items-center gap-3 rounded-lg bg-white/[0.02] border border-white/[0.04] p-3 animate-pulse"
        >
          <div className="h-4 w-4 rounded-full bg-white/[0.06]" />
          <div className="flex-1 space-y-1.5">
            <div className="h-3 w-1/3 bg-white/[0.06] rounded" />
            <div className="h-2 w-2/3 bg-white/[0.04] rounded" />
          </div>
        </li>
      ))}
    </ul>
  );
}
