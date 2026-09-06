"use client";

import { useEffect } from "react";

/**
 * Signal feed — signals from the strategies you subscribe to, taken MANUALLY.
 *
 * Header comes from the ONE Pro template (ProPage): the title is the sidebar
 * label and the blurb is the nav blurb, so this page cannot rename itself. Its
 * single primary action is Refresh (a callback, hence `actionSlot`).
 *
 * Wired to the real subscriber endpoints:
 *   GET  /marketplace/subscriptions/signals?status=received   (this page, 15s poll)
 *   POST /marketplace/subscriptions/signals/{id}/confirm      (OneClickConfirmButton)
 *
 * Default is MANUAL: nothing fires automatically — each signal is confirmed by
 * the customer. The confirm endpoint is PAPER-GATED today (records a simulated
 * fill, never a real broker order). Validity is SERVER-computed: this page shows
 * `signal.validity` directly and runs NO client clock — the number refreshes on
 * the 15s poll, and the confirm endpoint re-checks the window server-side.
 */

import { motion } from "framer-motion";
import { Clock, ShieldAlert, Loader2, AlertTriangle, RefreshCw } from "lucide-react";
import { ProPage, ProEmpty } from "@/components/dashboard/pro-page";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Badge } from "@/components/ui/badge";
import { UpgradeWall } from "@/components/billing/upgrade-wall";
import { OneClickConfirmButton } from "@/components/signals/one-click-confirm-button";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import type { SignalValidity, SubscriberSignal, SubscriberSignalListResponse } from "@/lib/signals";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.05 } } };
const fadeUp = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.3 } } };

/** ENTRY-class signal? Display-only (badge colour / label). Confirmability is
 *  gated by the server's `validity.valid`, never by this. */
function isEntryAction(action: string): boolean {
  return (action || "").toUpperCase().includes("ENTRY");
}

function fmtCountdown(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/**
 * Renders the SERVER-computed validity — no client countdown. `seconds_remaining`
 * is a server snapshot refreshed by the 15s poll (intentionally steppy). The
 * confirm endpoint re-checks the window, so a slightly-stale display can never
 * place a lapsed order.
 */
function ValidityCell({ v }: { v: SignalValidity }) {
  if (!v.valid) {
    return (
      <Badge className="uppercase text-xs bg-muted text-muted-foreground border-border">
        Expired
      </Badge>
    );
  }
  if (v.window === "exit") {
    return (
      <span className="text-xs text-accent-blue whitespace-nowrap inline-flex items-center gap-1">
        <Clock className="h-3 w-3" /> Valid till EOD
      </span>
    );
  }
  const urgent = v.seconds_remaining < 60;
  return (
    <span
      className={cn(
        "text-xs whitespace-nowrap inline-flex items-center gap-1 tabular-nums",
        urgent ? "text-loss" : "text-profit",
      )}
    >
      <Clock className="h-3 w-3" /> {fmtCountdown(v.seconds_remaining)} left
    </span>
  );
}

export default function SignalsPage() {
  const { data, isLoading, error, paywalled, refetch } =
    useApi<SubscriberSignalListResponse>(
      "/marketplace/subscriptions/signals?status=received",
      null,
      15_000,
    );

  const signals: SubscriberSignal[] = data?.signals ?? [];

  // The ladder's "first signal seen" fact: a customer who has this page open
  // with at least one signal has seen one (Level 2 needs it, with broker +
  // first subscription). Idempotent on the ladder side.
  useEffect(() => {
    if (signals.length > 0) {
      window.dispatchEvent(new CustomEvent("tradetri:ladder", { detail: { firstSignalSeen: true } }));
    }
  }, [signals.length]);
  const pendingCount = signals.filter((s) => s.validity.valid).length;

  return (
    <ProPage
      actionSlot={
        <GlowButton size="sm" onClick={refetch}>
          <RefreshCw className={cn("h-4 w-4 mr-2", isLoading && "animate-spin")} />
          Refresh
        </GlowButton>
      }
    >
      <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-6">
        {/* Count + the MANUAL framing that used to sit in the bespoke header. */}
        <motion.div variants={fadeUp} className="flex flex-wrap items-center gap-3">
          <Badge className="uppercase text-xs bg-accent-blue/15 text-accent-blue border-accent-blue/30">
            {pendingCount} valid
          </Badge>
          <p className="text-xs text-muted-foreground max-w-2xl">
            Koi trade apne aap nahi hoti: har signal aap khud confirm karte ho.
            Entry ~5&nbsp;min tak, exit din khatam hone tak valid. Har 15 sec khud
            refresh hota hai.
          </p>
        </motion.div>

        {/* Premium gate for the one-click action — reuses the B3 UpgradeWall.
            Shown only when the feed fetch returns a 402/PLAN_REQUIRED. */}
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
          {error && !data ? (
            <GlassmorphismCard hover={false} className="p-0 overflow-hidden">
              <div className="p-8 text-center">
                <AlertTriangle className="h-10 w-10 text-loss mx-auto mb-3" />
                <h3 className="font-semibold mb-1">Could not load signals</h3>
                <p className="text-sm text-muted-foreground mb-4">{error}</p>
                <GlowButton onClick={refetch} size="sm">Retry</GlowButton>
              </div>
            </GlassmorphismCard>
          ) : isLoading && !data ? (
            <GlassmorphismCard hover={false} className="p-0 overflow-hidden">
              <div className="p-12 flex justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            </GlassmorphismCard>
          ) : signals.length === 0 ? (
            <ProEmpty
              headline="Abhi koi pending signal nahi hai"
              next="Jin strategies ko aapne subscribe kiya hai, unke signals yahin aayenge — review karke khud lo. Abhi tak koi subscription nahi hai to Marketplace se ek strategy chuno."
              action={{ label: "Marketplace", href: "/marketplace" }}
            />
          ) : (
            <GlassmorphismCard hover={false} className="p-0 overflow-hidden">
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
                      const entry = isEntryAction(s.action);
                      const canTake = s.validity.valid;
                      return (
                        <tr
                          key={s.id}
                          className="border-t border-white/[0.04] hover:bg-white/[0.02]"
                        >
                          <td className="p-3 whitespace-nowrap">{s.listing_title}</td>
                          <td className="p-3 font-mono text-xs">{s.symbol}</td>
                          <td className="p-3">
                            <Badge
                              className={cn(
                                "uppercase text-xs",
                                entry
                                  ? "bg-profit/15 text-profit border-profit/30"
                                  : "bg-loss/15 text-loss border-loss/30",
                              )}
                            >
                              {s.action}
                            </Badge>
                          </td>
                          <td className="p-3 text-right tabular-nums">{s.entry ?? "—"}</td>
                          <td className="p-3 text-right tabular-nums text-muted-foreground">
                            {s.stop_loss ?? "—"}
                          </td>
                          <td className="p-3 text-right tabular-nums text-muted-foreground">
                            {s.target ?? "—"}
                          </td>
                          <td className="p-3">
                            <ValidityCell v={s.validity} />
                          </td>
                          <td className="p-3 text-right">
                            {!canTake ? (
                              <span className="text-xs text-muted-foreground">—</span>
                            ) : paywalled ? (
                              <Badge className="uppercase text-10 bg-white/[0.03] text-muted-foreground border-white/10 inline-flex items-center gap-1">
                                <ShieldAlert className="h-3 w-3" /> Premium
                              </Badge>
                            ) : (
                              <OneClickConfirmButton signal={s} onConfirmed={refetch} />
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </GlassmorphismCard>
          )}
        </motion.div>

        {/* Honest footer — paper + server-enforced validity */}
        <motion.div variants={fadeUp}>
          <p className="text-10 text-muted-foreground leading-relaxed">
            Abhi sab seekhne wala mode hai — koi asli order nahi jaata, bas dikhaya jaata hai ki kya hota. Har signal ki time-limit server par check hoti hai.
          </p>
        </motion.div>
      </motion.div>
    </ProPage>
  );
}
