"use client";

/**
 * Signal feed — your pending signals, reviewed and taken MANUALLY.
 *
 * Phase-1a: MOCK DATA ONLY. There is no backend subscriber signal feed and no
 * confirm endpoint yet (both are gated backend tasks). This page renders the
 * eventual shape off a local fixture so it can be built + QA'd with zero chance
 * of firing a real order. The one-click "Take trade" control is a no-op mock.
 *
 * SWAP NOTE (Phase-1c, when the backend lands): replace the `MOCK_SIGNALS`
 * import with the polling fetch — the shape already matches:
 *   const { data, isLoading, error, refetch, paywalled, paywallUrl } =
 *     useApi<{ signals: MockSignal[] }>("/marketplace/signals?status=pending", null, 15_000);
 * …then delete lib/mock/signals-mock.ts.
 */

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { RadioTower, Clock, ShieldAlert, FlaskConical } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { UpgradeWall } from "@/components/billing/upgrade-wall";
import { OneClickConfirmButton } from "@/components/signals/one-click-confirm-button";
import { cn } from "@/lib/utils";
import {
  ENTRY_VALIDITY_MINUTES,
  IS_MOCK,
  MOCK_NOW_MS,
  MOCK_PAYWALLED,
  MOCK_SIGNALS,
  type MockSignal,
} from "@/lib/mock/signals-mock";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.05 } } };
const fadeUp = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.3 } } };

const ENTRY_WINDOW_MS = ENTRY_VALIDITY_MINUTES * 60_000;

// DISPLAY ONLY — real validity must be server-enforced before any live confirm
// (backend task). This countdown is cosmetic: it never gates the actual order,
// it only tells the customer how long the window looks. The confirm endpoint,
// once built, re-checks the window server-side and rejects a lapsed take.
type Validity =
  | { kind: "entry"; live: boolean; remainingMs: number }
  | { kind: "exit"; live: boolean }
  | { kind: "lapsed" };

function computeValidity(sig: MockSignal, now: number): Validity {
  if (sig.status === "expired") return { kind: "lapsed" };
  if (sig.side === "EXIT") return { kind: "exit", live: true }; // valid till EOD
  const remainingMs = ENTRY_WINDOW_MS - (now - new Date(sig.received_at).getTime());
  if (remainingMs <= 0) return { kind: "lapsed" };
  return { kind: "entry", live: true, remainingMs };
}

function fmtCountdown(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function ValidityCell({ v }: { v: Validity }) {
  if (v.kind === "lapsed") {
    return (
      <Badge className="uppercase text-xs bg-muted text-muted-foreground border-border">
        Expired
      </Badge>
    );
  }
  if (v.kind === "exit") {
    return (
      <span className="text-xs text-accent-blue whitespace-nowrap inline-flex items-center gap-1">
        <Clock className="h-3 w-3" /> Valid till EOD
      </span>
    );
  }
  const urgent = v.remainingMs < 60_000;
  return (
    <span
      className={cn(
        "text-xs whitespace-nowrap inline-flex items-center gap-1 tabular-nums",
        urgent ? "text-loss" : "text-profit",
      )}
    >
      <Clock className="h-3 w-3" /> {fmtCountdown(v.remainingMs)} left
    </span>
  );
}

export default function SignalsPage() {
  // Live-ticking "now" anchored to the fixture time (see MOCK_NOW_MS): starts
  // deterministic at mount, then ticks each second so the countdown feels live
  // without depending on the real wall clock. Real wiring uses actual Date.now().
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setElapsed((e) => e + 1000), 1000);
    return () => clearInterval(t);
  }, []);
  const now = MOCK_NOW_MS + elapsed;

  const signals = MOCK_SIGNALS; // ← swap for useApi fetch when the backend lands
  const paywalled = MOCK_PAYWALLED; // ← real: `paywalled` from useApi's 402 (B3)

  const pendingCount = useMemo(
    () => signals.filter((s) => s.status === "pending").length,
    [signals],
  );

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto space-y-6"
    >
      {/* Header — MANUAL framing */}
      <motion.div variants={fadeUp} className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <RadioTower className="h-6 w-6 text-accent-blue" /> Signals
            {IS_MOCK && (
              <Badge className="ml-1 uppercase text-[10px] bg-amber-400/15 text-amber-300 border-amber-300/40 inline-flex items-center gap-1">
                <FlaskConical className="h-3 w-3" /> Mock data
              </Badge>
            )}
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            Aapke pending signals — review karo aur manually take karo. Default{" "}
            <strong>MANUAL</strong> hai: koi trade apne aap fire nahi hoti, aap
            har signal khud confirm karte ho. Entry window ~{ENTRY_VALIDITY_MINUTES} min,
            exit EOD tak valid.
          </p>
        </div>
        <Badge className="uppercase text-xs bg-accent-blue/15 text-accent-blue border-accent-blue/30">
          {pendingCount} pending
        </Badge>
      </motion.div>

      {/* Premium gate for the one-click action — reuses the B3 UpgradeWall.
          Shown only when paywalled (the useApi 402/PLAN_REQUIRED signal). */}
      {paywalled && (
        <motion.div variants={fadeUp}>
          <UpgradeWall
            variant="inline"
            feature="One-click confirm"
            description="Take signals in one tap. Upgrade to enable one-click confirmation."
            upgradeUrl="/pricing"
          />
        </motion.div>
      )}

      {/* Feed */}
      <motion.div variants={fadeUp}>
        <GlassmorphismCard hover={false} className="p-0 overflow-hidden">
          {signals.length === 0 ? (
            <div className="p-12 text-center">
              <RadioTower className="h-10 w-10 text-muted-foreground mx-auto mb-3 opacity-50" />
              <h3 className="font-semibold mb-1">No pending signals</h3>
              <p className="text-sm text-muted-foreground">
                New signals from your subscribed strategies appear here for you to
                review and take manually.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-white/[0.02] text-xs text-muted-foreground uppercase">
                  <tr>
                    <th className="text-left p-3 font-medium">Strategy</th>
                    <th className="text-left p-3 font-medium">Symbol</th>
                    <th className="text-left p-3 font-medium">Side</th>
                    <th className="text-right p-3 font-medium">Entry</th>
                    <th className="text-right p-3 font-medium">SL</th>
                    <th className="text-right p-3 font-medium">Target</th>
                    <th className="text-left p-3 font-medium">Validity</th>
                    <th className="text-right p-3 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {signals.map((s) => {
                    const v = computeValidity(s, now);
                    const canTake = s.status === "pending" && v.kind !== "lapsed";
                    return (
                      <tr
                        key={s.id}
                        className="border-t border-white/[0.04] hover:bg-white/[0.02]"
                      >
                        <td className="p-3 whitespace-nowrap">{s.strategyName}</td>
                        <td className="p-3 font-mono text-xs">{s.symbol}</td>
                        <td className="p-3">
                          <Badge
                            className={cn(
                              "uppercase text-xs",
                              s.side === "ENTRY"
                                ? "bg-profit/15 text-profit border-profit/30"
                                : "bg-loss/15 text-loss border-loss/30",
                            )}
                          >
                            {s.side}
                          </Badge>
                        </td>
                        <td className="p-3 text-right tabular-nums">{s.entry ?? "—"}</td>
                        <td className="p-3 text-right tabular-nums text-muted-foreground">
                          {s.sl ?? "—"}
                        </td>
                        <td className="p-3 text-right tabular-nums text-muted-foreground">
                          {s.target ?? "—"}
                        </td>
                        <td className="p-3">
                          <ValidityCell v={v} />
                        </td>
                        <td className="p-3 text-right">
                          {!canTake ? (
                            <span className="text-xs text-muted-foreground">—</span>
                          ) : paywalled ? (
                            <Badge className="uppercase text-[10px] bg-white/[0.03] text-muted-foreground border-white/10 inline-flex items-center gap-1">
                              <ShieldAlert className="h-3 w-3" /> Premium
                            </Badge>
                          ) : (
                            <OneClickConfirmButton signal={s} />
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </GlassmorphismCard>
      </motion.div>

      {/* Honest footer — mock + display-only validity */}
      <motion.div variants={fadeUp}>
        <p className="text-[10px] text-muted-foreground leading-relaxed">
          Mock preview — no real orders are placed. Validity countdowns are
          display-only; live one-click confirmation (with server-enforced
          validity) activates when the backend endpoints ship (Phase&nbsp;3 /
          empanelment).
        </p>
      </motion.div>
    </motion.div>
  );
}
