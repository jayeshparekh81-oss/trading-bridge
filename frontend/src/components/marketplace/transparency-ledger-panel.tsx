"use client";

/**
 * Strategy Transparency Ledger panel — the master-prompt
 * "Backtest nahi, Proof" differentiator. Reads from the Phase 2
 * /ledger endpoints and surfaces:
 *
 *   * latest snapshot's performance numbers (PnL, trades, drawdown);
 *   * chain verification status — green shield on clean chain,
 *     red warning + reason on tampering;
 *   * "Verify Now" button to re-run the chain walk on demand;
 *   * "View History" affordance that opens the timeline modal.
 *
 * Days-since-publish drives a celebratory copy-shift at the 30 /
 * 60 / 90-day milestones (the master-prompt "90-day proof" gate).
 */

import { useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  Calendar,
  Check,
  History,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

export interface LedgerSnapshot {
  id: string;
  listing_id: string;
  snapshot_date: string;
  sequence_number: number;
  cumulative_pnl_inr: number;
  max_drawdown_pct: number;
  total_trades: number;
  win_rate: number;
  sharpe_ratio: number | null;
  days_since_publish: number;
  paper_trades_count: number;
  live_trades_count: number;
  data_hash: string;
  prior_hash: string | null;
  chain_signature: string;
  created_at: string;
}

export interface LedgerVerificationResult {
  listing_id: string;
  is_chain_valid: boolean;
  snapshots_verified: number;
  first_break_at_sequence: number | null;
  first_break_reason: string | null;
  verified_at: string;
}

interface TransparencyLedgerPanelProps {
  listingId: string;
  onOpenHistory: () => void;
}

export function TransparencyLedgerPanel({
  listingId,
  onOpenHistory,
}: TransparencyLedgerPanelProps) {
  const { data: latest, isLoading, refetch } = useApi<LedgerSnapshot | null>(
    `/marketplace/listings/${listingId}/ledger`,
    null,
  );
  const [verification, setVerification] =
    useState<LedgerVerificationResult | null>(null);
  const [verifying, setVerifying] = useState(false);

  async function handleVerify() {
    setVerifying(true);
    try {
      const result = await api.get<LedgerVerificationResult>(
        `/marketplace/listings/${listingId}/ledger/verify`,
      );
      setVerification(result);
      if (result.is_chain_valid) {
        toast.success("🛡️✅ Chain valid hai — har snapshot match karta hai");
      } else {
        toast.error(
          `⚠️🚨 Chain mein break detect hua sequence #${result.first_break_at_sequence}: ${result.first_break_reason}`,
        );
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Verification fail ho gaya";
      toast.error(msg);
    } finally {
      setVerifying(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
    >
      <GlassmorphismCard hover={false}>
        <div className="space-y-4">
          <header className="flex items-start justify-between gap-3 flex-wrap">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-accent-blue" />
                <h2 className="text-base font-semibold">
                  Strategy Transparency Ledger
                </h2>
                <Badge className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 text-[10px]">
                  Phase 2 (off-chain)
                </Badge>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed max-w-2xl">
                Backtest nahi, proof. Har din ka performance snapshot
                cryptographically chain ho jaata hai — koi bhi field
                badle to verify endpoint pakad leta hai.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleVerify}
                disabled={verifying || latest == null}
                type="button"
              >
                <ShieldCheck className="h-3.5 w-3.5" />
                {verifying ? "Verifying…" : "Verify Now"}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={onOpenHistory}
                type="button"
              >
                <History className="h-3.5 w-3.5" />
                History
              </Button>
            </div>
          </header>

          {isLoading ? (
            <div className="text-[11px] text-muted-foreground">
              Ledger load ho raha hai…
            </div>
          ) : latest == null ? (
            <div className="rounded-lg bg-white/[0.02] border border-white/[0.04] p-3 text-[11px] text-muted-foreground leading-relaxed">
              Abhi koi snapshot nahi liya gaya. Creator pehle daily
              snapshot trigger karega — uske baad chain start hoga.
            </div>
          ) : (
            <LatestSnapshotPanel snapshot={latest} />
          )}

          {verification != null ? (
            <VerificationBanner result={verification} />
          ) : null}

          {/* Force the linter to keep ``refetch`` exposed; users
              looking at a stale tab can reload. */}
          <button
            type="button"
            onClick={refetch}
            className="hidden"
            aria-hidden
          />
        </div>
      </GlassmorphismCard>
    </motion.div>
  );
}

function LatestSnapshotPanel({ snapshot }: { snapshot: LedgerSnapshot }) {
  const milestone = pickMilestone(snapshot.days_since_publish);
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Cell
          label="Cumulative P&L"
          value={`₹${snapshot.cumulative_pnl_inr.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`}
          accent={snapshot.cumulative_pnl_inr >= 0 ? "profit" : "loss"}
        />
        <Cell
          label="Max Drawdown"
          value={`${snapshot.max_drawdown_pct.toFixed(2)}%`}
          accent="loss"
        />
        <Cell
          label="Total Trades"
          value={String(snapshot.total_trades)}
        />
        <Cell
          label="Win Rate"
          value={`${(snapshot.win_rate * 100).toFixed(1)}%`}
          accent={snapshot.win_rate >= 0.5 ? "profit" : undefined}
        />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <Cell
          label="Days Since Publish"
          value={String(snapshot.days_since_publish)}
          icon={Calendar}
        />
        <Cell
          label="Paper Trades"
          value={String(snapshot.paper_trades_count)}
        />
        <Cell label="Live Trades" value={String(snapshot.live_trades_count)} />
      </div>
      {milestone ? (
        <div className="rounded-lg bg-amber-400/10 border border-amber-300/30 p-3 flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-amber-300 shrink-0" />
          <p className="text-[11px] text-amber-200/90 leading-relaxed">
            {milestone}
          </p>
        </div>
      ) : null}
      <div className="text-[10px] text-muted-foreground/70 font-mono break-all">
        sig: {snapshot.chain_signature.slice(0, 16)}…{snapshot.chain_signature.slice(-8)}
        {" · "}
        seq #{snapshot.sequence_number}
      </div>
    </div>
  );
}

function VerificationBanner({ result }: { result: LedgerVerificationResult }) {
  const ok = result.is_chain_valid;
  return (
    <div
      className={cn(
        "rounded-lg border p-3 flex items-start gap-2",
        ok
          ? "bg-profit/10 border-profit/30 text-profit"
          : "bg-loss/10 border-loss/30 text-loss",
      )}
    >
      {ok ? (
        <Check className="h-4 w-4 mt-0.5 shrink-0" />
      ) : (
        <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
      )}
      <div className="space-y-0.5">
        <p className="text-[12px] font-medium">
          {ok
            ? `🛡️✅ Chain valid — ${result.snapshots_verified} snapshots verified`
            : `⚠️🚨 Chain break at sequence #${result.first_break_at_sequence}`}
        </p>
        <p className="text-[10px] opacity-80">
          {ok
            ? `Verified at ${new Date(result.verified_at).toLocaleTimeString()}`
            : (result.first_break_reason ?? "Unknown reason")}
        </p>
      </div>
    </div>
  );
}

function Cell({
  label,
  value,
  accent,
  icon: Icon,
}: {
  label: string;
  value: string;
  accent?: "profit" | "loss";
  icon?: typeof ShieldCheck;
}) {
  return (
    <div className="rounded-lg bg-white/[0.02] border border-white/[0.04] p-2.5">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground flex items-center gap-1">
        {Icon ? <Icon className="h-3 w-3" /> : null}
        {label}
      </div>
      <div
        className={cn(
          "text-sm font-semibold",
          accent === "profit" && "text-profit",
          accent === "loss" && "text-loss",
        )}
      >
        {value}
      </div>
    </div>
  );
}

function pickMilestone(days: number): string | null {
  if (days >= 90)
    return "🏆🎉🎉 90-day forward-test milestone hit — strategy ne 3 mahine actual data pe perform kiya hai.";
  if (days >= 60) return "🎉 60 days clean — 90-day milestone close hai.";
  if (days >= 30) return "🎉 30-day milestone reach ho gaya, keep it up.";
  return null;
}
