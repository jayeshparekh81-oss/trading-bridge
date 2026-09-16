"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { Loader2, AlertTriangle, RefreshCw } from "lucide-react";
import { GlassmorphismCard } from "@/shared/ui/glassmorphism-card";
import { GlowButton } from "@/shared/ui/glow-button";
import { Badge } from "@/shared/ui/badge";
import { ProPage, ProEmpty } from "@/components/dashboard/pro-page";
import {
  PaperModeBanner,
  PaperRowBadge,
} from "@/components/dashboard/paper-mode-banner";
import { TrackingEpochNote } from "@/components/dashboard/tracking-epoch-note";
import { usePaperModes } from "@/hooks/usePaperModes";
import { paperScope } from "@/lib/paper-mode";
import { ARCHIVE_HINT, sinceEpochHeadline, useTrackingEpoch } from "@/lib/tracking-epoch";
import { useApi } from "@/shared/api/use-api";
import { formatCurrency, cn } from "@/shared/lib/utils";
import {
  formatPriceOrUnknown,
  isUnknownPrice,
  NO_PRICE as UNKNOWN_PRICE,
} from "@/shared/lib/price-display";
import {
  HUMAN_INTERFERED_FALLBACK_DETAIL,
  HUMAN_INTERFERED_LABEL,
  OPERATOR_ESTIMATE_FALLBACK_DETAIL,
  OPERATOR_ESTIMATE_LABEL,
  UNPRICEABLE_FALLBACK_DETAIL,
  type PnlAttribution,
} from "@/lib/pnl-attribution";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.05 } } };
const fadeUp = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.3 } } };

interface Position {
  id: string;
  strategy_id: string;
  symbol: string;
  side: string;
  total_quantity: number;
  remaining_quantity: number;
  avg_entry_price: string | null;
  target_price: string | null;
  stop_loss_price: string | null;
  /** The stop actually RESTING at the broker, when one has been read.
   *  `stop_loss_price` above is our own column and is NULL on every
   *  direct-exit row, because pine_replica places the trailing stop
   *  straight at Dhan. null here means UNKNOWN, never "no stop". */
  broker_stop_price?: string | null;
  broker_stop_order_id?: string | null;
  highest_price_seen: string | null;
  status: string;
  opened_at: string;
  closed_at: string | null;
  final_pnl: string | null;
  /** bot_only | account_flat | human_interfered | unpriceable | paper_sim | null (not yet attributed). */
  pnl_attribution?: PnlAttribution | string | null;
  pnl_attribution_detail?: string | null;
  /** S1(d). False when a CLOSED row's legs do not add up — the row then shows
   *  "adhura" and the reason, never a number over legs that disagree. */
  legs_balanced?: boolean;
  incomplete_reason?: string | null;
  /** Present only where a system fault fired a second exit against an
   *  already-closed position (2026-09-04). Shown, with its own fill-sourced
   *  number, and counted — a bug that cost money is part of the record. */
  duplicate_exit?: {
    broker_order_id?: string | null;
    side?: string | null;
    qty?: number | null;
    price?: string | null;
    gross_pnl?: string | null;
    /** What Dhan BILLED on the accidental exit AND the fills that closed the
     *  position it opened. The system's mistake cost charges like any trade. */
    billed_charges?: string | null;
    /** gross_pnl - billed_charges, or null when the bill is incomplete. */
    net_pnl?: string | null;
    label?: string | null;
    reason?: string | null;
    closed_by?: { broker_order_id?: string; qty?: number; price?: number }[];
  } | null;
  /** R4. Every leg behind this row, in the order they happened — the whole
   *  point of the page: a P&L whose fills cannot be read off the screen is a
   *  number the reader has to take on trust. */
  legs?: PositionLeg[];
  /** GROSS on the closed portion, fill-sourced. Served beside the net figure
   *  so a total can sum like-for-like instead of mixing the two. */
  derived_gross_pnl?: string | null;
  /** What DHAN BILLED. null means the bill has not arrived — the row then
   *  shows gross and says "charges baaki". Never a modelled fallback. */
  derived_realised_charges?: string | null;
  derived_realised_reason?: string | null;
  /** R1.2 / R1.3. "verified" only when a STORED truth-check run covers this
   *  row's close; "manual_closed" when a hand-placed Dhan order closed it
   *  (an answer, not a pending state); "pending" otherwise. */
  verification?: "verified" | "manual_closed" | "pending" | string;
  /** The date of the run that verified this row. A badge may never outlive
   *  the check that earned it. */
  verified_on?: string | null;
}

/** One leg = one Dhan fill (or, for a manual close, the fill we deliberately
 *  do not price). `price` is full precision; `price_display` is the same
 *  number at two decimals, formatted by the backend so every surface agrees. */
interface PositionLeg {
  leg_role: string;
  label: string;
  side?: string | null;
  quantity: number;
  price?: string | null;
  price_display?: string | null;
  broker_order_id?: string | null;
  filled_at?: string | null;
  /** Already IST, already formatted — the page must not re-derive a timezone. */
  filled_at_ist?: string | null;
  broker_fill?: boolean;
}

interface PositionsResponse {
  positions: Position[];
  count: number;
}

type StatusFilter = "all" | "open" | "partial" | "closed";

export default function PositionsPage() {
  const [filter, setFilter] = useState<StatusFilter>("all");
  const url =
    filter === "all"
      ? "/strategies/positions?limit=100"
      : `/strategies/positions?status=${filter}&limit=100`;

  const { data, isLoading, error, refetch } = useApi<PositionsResponse>(url, null, 15_000);

  // Memoised so the derivations below do not recompute on every render — a
  // fresh [] each render would invalidate both useMemos every time.
  const positions = useMemo(() => data?.positions ?? [], [data]);

  /**
   * A1 — TOTAL GROSS and TOTAL NET, separately, and never mixed.
   *
   * The founder's review of the first S4 table caught exactly this: a total
   * that adds a gross figure to a net one is not a number about anything. So
   * gross sums gross, net sums net, and the duplicate exit — a loss the SYSTEM
   * caused — is counted in both, because he pays for it the same as for a win.
   *
   * 🔴 NET IS NULL IF ANY BILL IS MISSING. Summing the rows that happen to be
   * billed and calling it the total would understate charges and overstate net,
   * quietly, in the flattering direction. When a bill has not arrived the total
   * says so and names how many rows it is waiting on.
   */
  const totals = useMemo(() => {
    let gross = 0;
    let net = 0;
    let unbilled = 0;
    let counted = 0;
    for (const p of positions) {
      const rowGross =
        p.derived_gross_pnl != null ? Number(p.derived_gross_pnl) : null;
      const rowNet = p.final_pnl != null ? Number(p.final_pnl) : null;
      if (rowGross == null && rowNet == null) continue;
      counted += 1;
      if (rowGross != null) gross += rowGross;
      if (rowNet != null) net += rowNet;
      else unbilled += 1;
      // 🔴 CAUGHT BY THE R4 RENDER, not by reading the code. Adding this row's
      // GROSS into the NET total made the headline 133.13 too high — the
      // accidental sell and its two closing buys were billed like any other
      // trade. Gross with gross, net with net, here too.
      const dupGross = p.duplicate_exit?.gross_pnl;
      if (dupGross != null) gross += Number(dupGross);
      if (p.duplicate_exit) {
        const dupNet = p.duplicate_exit.net_pnl;
        if (dupNet != null) net += Number(dupNet);
        // An unbilled mistake is an unbilled row: the total says "baaki"
        // rather than counting this one at gross while everything else is net.
        else unbilled += 1;
      }
    }
    return { gross, net, unbilled, counted };
  }, [positions]);

  /**
   * Per-row paper truth. `/strategies/positions` carries `strategy_id` but no
   * `is_paper`, so the mode is joined in from the owner's strategy list — the
   * same flag `resolve_paper_mode` obeys on the execution path.
   *
   * This page genuinely MIXES: the founder's live "BSE LTD Futures" rows sit
   * beside a paper "PAPER FANOUT TEST" row. A single banner over both is a
   * lie whichever way it is worded, so the scope decides whether any blanket
   * sentence may be printed at all, and every row carries its own label.
   */
  const { modeFor } = usePaperModes();
  /**
   * Where the record starts, read from the server — never a date written
   * here. Only the "all" empty state names it: "no OPEN position" is a claim
   * about right now and is true whatever the cut-off is, but "nothing at all
   * in this list" would read as "nothing ever" unless the period is named.
   */
  const { shortLabel: epochShort } = useTrackingEpoch();
  const rowModes = useMemo(
    () => positions.map((p) => modeFor(p.strategy_id)),
    [positions, modeFor],
  );
  const scope = useMemo(() => paperScope(rowModes), [rowModes]);
  /**
   * ADR 0001 §4. useApi keeps its fallback visible on failure, so these chips
   * printed a bold "0 open / 0 partial / 0 closed" during an outage — four
   * confident zeros about the customer's live exposure, directly above an
   * error card saying we could not load anything. A count we have not got is
   * an em dash, never a zero.
   */
  const countsKnown = data !== null && !error;
  const stats = useMemo(() => {
    const open = positions.filter((p) => p.status === "open").length;
    const partial = positions.filter((p) => p.status === "partial").length;
    const closed = positions.filter((p) => p.status === "closed").length;
    return { open, partial, closed, total: positions.length };
  }, [positions]);

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto"
    >
      <ProPage
        actionSlot={
          <GlowButton size="sm" onClick={refetch}>
            <RefreshCw className={cn("h-4 w-4 mr-2", isLoading && "animate-spin")} />
            Refresh
          </GlowButton>
        }
      >
      {/* Closing a position is an ACT, so the mode must be disclosed above
          it — but only a claim that is true for EVERY row below. Mixed pages
          get the pointer to per-row labels; unknown gets silence. */}
      <PaperModeBanner scope={scope} />

      {/* Where this list starts. Renders nothing until the server says. */}
      <TrackingEpochNote />

      <motion.div variants={fadeUp} className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {(["all", "open", "partial", "closed"] as StatusFilter[]).map((s) => {
          const count =
            s === "all"
              ? stats.total
              : s === "open"
              ? stats.open
              : s === "partial"
              ? stats.partial
              : stats.closed;
          return (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={cn(
                "rounded-lg border px-4 py-3 text-left transition-colors",
                filter === s
                  ? "bg-accent-blue/10 border-accent-blue/40 text-accent-blue"
                  : "bg-white/[0.02] border-white/[0.05] text-muted-foreground hover:bg-white/[0.04]",
              )}
            >
              <div className="text-xs uppercase tracking-wide">{s}</div>
              <div className="text-2xl font-bold mt-1">{countsKnown ? count : "—"}</div>
            </button>
          );
        })}
      </motion.div>

      <motion.div variants={fadeUp}>
        {!(error && !data) && !(isLoading && !data) && positions.length === 0 ? (
          <ProEmpty
            headline={
              filter !== "all"
                ? `Is filter mein koi position nahi — ${filter}`
                : epochShort
                ? sinceEpochHeadline(epochShort, "abhi tak koi position nahi bani")
                : "Abhi koi position khuli nahi hai"
            }
            next={
              filter !== "all"
                ? "Abhi is status mein kuch nahi hai. Poori list ke liye upar All chuno."
                : "Signal accept hote hi position seconds mein khul jaati hai. Ek strategy chalu karo, ya apna TradingView alert webhook URL par bhejo." +
                  (epochShort ? ` ${ARCHIVE_HINT}` : "")
            }
            action={filter === "all" ? { label: "Strategies", href: "/strategies" } : undefined}
          />
        ) : (
        <GlassmorphismCard hover={false} className="p-0 overflow-hidden">
          {error && !data ? (
            <div className="p-8 text-center">
              <AlertTriangle className="h-10 w-10 text-loss mx-auto mb-3" />
              <h3 className="font-semibold mb-1">Could not load positions</h3>
              <p className="text-sm text-muted-foreground mb-4">{error}</p>
              <GlowButton onClick={refetch} size="sm">Retry</GlowButton>
            </div>
          ) : isLoading && !data ? (
            <div className="p-12 flex justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-white/[0.02] text-xs text-muted-foreground uppercase">
                  <tr>
                    <th className="text-left p-3 font-medium">Symbol</th>
                    <th className="text-left p-3 font-medium">Mode</th>
                    <th className="text-left p-3 font-medium">Side</th>
                    <th className="text-right p-3 font-medium">Total</th>
                    <th className="text-right p-3 font-medium">Remaining</th>
                    <th className="text-right p-3 font-medium">Entry</th>
                    <th className="text-right p-3 font-medium">Target</th>
                    <th className="text-right p-3 font-medium">SL</th>
                    <th className="text-left p-3 font-medium">Status</th>
                    <th className="text-left p-3 font-medium">Opened</th>
                    {/* The API has always returned closed_at; nothing rendered
                        it, so a closed row gave no clue WHEN it closed and the
                        only time on the page was the entry's. Still null for
                        an open row — that is a dash, not a guess. */}
                    <th className="text-left p-3 font-medium">Closed</th>
                    <th
                      className="text-right p-3 font-medium"
                      title="Fills aur charges dono Dhan ke apne record se — koi estimate nahi. Jis fill ka bill abhi nahi aaya, uska net khaali rehta hai."
                    >
                      Realised P&amp;L{" "}
                      <span className="normal-case font-normal">
                        (charges Dhan ke bill se)
                      </span>
                    </th>
                    <th className="text-left p-3 font-medium">Verify</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.flatMap((p, i) => [
                    <tr key={p.id} className="border-t border-white/[0.04] hover:bg-white/[0.02]">
                      <td className="p-3 font-mono text-xs">{p.symbol}</td>
                      {/* Per-row truth. Renders nothing for a row whose
                          strategy we could not read — never a guess. */}
                      <td className="p-3">
                        <PaperRowBadge paper={rowModes[i] ?? null} />
                      </td>
                      <td className="p-3">
                        <Badge
                          className={cn(
                            "uppercase text-xs",
                            p.side.toLowerCase() === "buy"
                              ? "bg-profit/15 text-profit border-profit/30"
                              : "bg-loss/15 text-loss border-loss/30",
                          )}
                        >
                          {p.side}
                        </Badge>
                      </td>
                      <td className="p-3 text-right tabular-nums">{p.total_quantity}</td>
                      <td className="p-3 text-right tabular-nums">
                        {p.remaining_quantity}
                        {p.remaining_quantity !== p.total_quantity && (
                          <span className="text-muted-foreground text-xs ml-1">
                            (-{p.total_quantity - p.remaining_quantity})
                          </span>
                        )}
                      </td>
                      <td className="p-3 text-right tabular-nums">
                        {formatPriceOrUnknown(p.avg_entry_price)}
                      </td>
                      <td className="p-3 text-right tabular-nums text-muted-foreground">
                        {formatPriceOrUnknown(p.target_price)}
                      </td>
                      {/* Our column first; the broker's resting stop when we
                          have none of our own. An invisible stop reads as no
                          stop, and this row had a real 3354.85 armed at Dhan
                          while the screen printed a dash. */}
                      <td className="p-3 text-right tabular-nums text-muted-foreground">
                        {!isUnknownPrice(p.stop_loss_price) ? (
                          formatPriceOrUnknown(p.stop_loss_price)
                        ) : !isUnknownPrice(p.broker_stop_price) ? (
                          <span
                            data-testid="broker-resting-stop"
                            title={
                              "Resting at the broker" +
                              (p.broker_stop_order_id
                                ? ` — order ${p.broker_stop_order_id}`
                                : "")
                            }
                            className="inline-flex items-center gap-1"
                          >
                            {formatPriceOrUnknown(p.broker_stop_price)}
                            <span className="text-10 uppercase tracking-wide text-accent-blue">
                              broker
                            </span>
                          </span>
                        ) : (
                          UNKNOWN_PRICE
                        )}
                      </td>
                      <td className="p-3">
                        <Badge
                          className={cn(
                            "uppercase text-xs",
                            p.status === "open"
                              ? "bg-accent-blue/15 text-accent-blue border-accent-blue/30"
                              : p.status === "partial"
                              ? "bg-yellow-500/15 text-yellow-500 border-yellow-500/30"
                              : "bg-muted text-muted-foreground border-border",
                          )}
                        >
                          {p.status}
                        </Badge>
                      </td>
                      <td className="p-3 text-xs text-muted-foreground whitespace-nowrap">
                        {new Date(p.opened_at).toLocaleString("en-IN", {
                          dateStyle: "short",
                          timeStyle: "short",
                        })}
                      </td>
                      <td
                        className="p-3 text-xs text-muted-foreground whitespace-nowrap"
                        data-testid="position-closed-at"
                      >
                        {p.closed_at
                          ? new Date(p.closed_at).toLocaleString("en-IN", {
                              dateStyle: "short",
                              timeStyle: "short",
                            })
                          : "—"}
                      </td>
                      <td className="p-3 text-right tabular-nums">
                        {/* The tag wins over a number: a human-interfered row is NULL by
                            rule, and a stale value left by an append-only run must not
                            read as a P&L. Every OTHER null keeps the plain dash. */}
                        {p.pnl_attribution === "human_interfered" ? (
                          <span
                            className="inline-flex items-center rounded-full border border-amber-300/40 bg-amber-400/10 px-2 py-0.5 text-10 font-medium text-amber-200"
                            data-testid="pnl-human-interfered"
                            title={p.pnl_attribution_detail ?? HUMAN_INTERFERED_FALLBACK_DETAIL}
                          >
                            {HUMAN_INTERFERED_LABEL}
                          </span>
                        ) : p.pnl_attribution === "operator_estimate" &&
                          p.final_pnl !== null &&
                          p.final_pnl !== undefined ? (
                          /* An OPERATOR ESTIMATE carries a real number, so it is
                             shown — but the tooltip below claims "fills are real",
                             and on this row they are not: part of it was priced
                             from a level the engine derived for an exit that was
                             never dispatched. The caveat travels WITH the money,
                             as a visible chip, not only in a hover. */
                          <span className="inline-flex items-center gap-1.5">
                            <span
                              className={Number(p.final_pnl) >= 0 ? "text-profit" : "text-loss"}
                            >
                              {formatCurrency(Number(p.final_pnl), { showSign: true })}
                            </span>
                            <span
                              className="inline-flex items-center rounded-full border border-sky-300/40 bg-sky-400/10 px-2 py-0.5 text-10 font-medium text-sky-200"
                              data-testid="pnl-operator-estimate"
                              title={
                                p.pnl_attribution_detail ?? OPERATOR_ESTIMATE_FALLBACK_DETAIL
                              }
                            >
                              {OPERATOR_ESTIMATE_LABEL}
                            </span>
                          </span>
                        ) : p.final_pnl !== null && p.final_pnl !== undefined ? (
                          <span
                            className={Number(p.final_pnl) >= 0 ? "text-profit" : "text-loss"}
                            title={
                              p.derived_realised_reason ??
                              "Net — charges Dhan ke bill se, estimate nahi"
                            }
                          >
                            {formatCurrency(Number(p.final_pnl), { showSign: true })}
                          </span>
                        ) : p.legs_balanced === false ? (
                          /* S1(d). The legs do not add up, so there is no
                             honest number to print. Say that, and say why. */
                          <span
                            className="text-10 text-amber-200/90"
                            data-testid="pnl-incomplete"
                            title={p.incomplete_reason ?? undefined}
                          >
                            adhura — legs poore nahi
                          </span>
                        ) : p.pnl_attribution === "unpriceable" ? (
                          <span
                            className="text-10 text-muted-foreground/80"
                            data-testid="pnl-unpriceable"
                            title={p.pnl_attribution_detail ?? UNPRICEABLE_FALLBACK_DETAIL}
                          >
                            not a trade
                          </span>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                        {/* GROSS beside NET, so a reader adding the column up
                            cannot accidentally mix the two. Shown only when it
                            says something the net does not. */}
                        {p.derived_gross_pnl != null &&
                          p.final_pnl == null &&
                          p.legs_balanced !== false && (
                            <div
                              className="text-10 text-muted-foreground"
                              data-testid="pnl-gross-only"
                              title={p.derived_realised_reason ?? undefined}
                            >
                              gross{" "}
                              {formatCurrency(Number(p.derived_gross_pnl), {
                                showSign: true,
                              })}
                              {" · "}
                              {p.derived_realised_charges != null
                                ? `charges ${p.derived_realised_charges} Dhan ke bill se`
                                : "charges baaki"}
                            </div>
                          )}
                      </td>
                      {/* R1.2 / R1.3 — three honest states. A ✅ requires a
                          STORED run covering this close, and names its date. */}
                      <td className="p-3">
                        {p.verification === "verified" ? (
                          <span
                            className="inline-flex items-center rounded-full border border-emerald-300/40 bg-emerald-400/10 px-2 py-0.5 text-10 font-medium text-emerald-200"
                            data-testid="verify-verified"
                            title={`Us din ka truth check Dhan se match hua (${p.verified_on ?? "—"})`}
                          >
                            Dhan se verified ✅ {p.verified_on ?? ""}
                          </span>
                        ) : p.verification === "manual_closed" ? (
                          /* NOT a pending state. By the founder's rule this
                             trade's P&L is not counted at all, so promising a
                             ✅ that can never arrive would be a lie. */
                          <span
                            className="inline-flex items-center rounded-full border border-amber-300/40 bg-amber-400/10 px-2 py-0.5 text-10 font-medium text-amber-200"
                            data-testid="verify-manual-closed"
                            title={p.incomplete_reason ?? undefined}
                          >
                            manual se band
                          </span>
                        ) : (
                          <span
                            className="text-10 text-muted-foreground"
                            data-testid="verify-pending"
                            title="Is row ko abhi kisi truth check ne Dhan se match nahi kiya"
                          >
                            Dhan se verify baaki
                          </span>
                        )}
                      </td>
                    </tr>,
                    /* ── THE FILLS ───────────────────────────────────────
                       The founder's actual ask: every AUTOMATED order behind
                       this row — entry, partial, broker stop (auto), SL /
                       trailing exit — with qty, fill price, IST time and the
                       Dhan order id. Always rendered, never behind a click:
                       a number whose working is one interaction away is a
                       number most readers never check. */
                    p.legs && p.legs.length > 0 ? (
                      <tr
                        key={`${p.id}-legs`}
                        className="border-t border-white/[0.02] bg-white/[0.015]"
                        data-testid="position-legs"
                      >
                        <td colSpan={13} className="px-3 pb-3 pt-1">
                          <div className="flex flex-col gap-1">
                            {p.legs.map((leg, i) => (
                              <div
                                key={`${p.id}-leg-${i}`}
                                className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-11 text-muted-foreground"
                              >
                                <span className="min-w-[9.5rem] text-foreground/80">
                                  {leg.label}
                                </span>
                                <span className="tabular-nums">
                                  {leg.side ? `${leg.side.toUpperCase()} ` : ""}
                                  {leg.quantity}
                                </span>
                                <span className="tabular-nums">
                                  {/* price_display is formatted by the backend
                                      so the page, the CSV and the alert cannot
                                      drift apart. A leg with no fill of its own
                                      prints a dash, never 0.00. */}
                                  {leg.price_display ?? "—"}
                                </span>
                                <span className="tabular-nums">
                                  {leg.filled_at_ist ?? "—"}
                                </span>
                                <span className="font-mono text-10 opacity-70">
                                  {leg.broker_order_id ?? "—"}
                                </span>
                                {leg.broker_fill === false && (
                                  <span
                                    className="text-10 text-amber-200/80"
                                    title="Is leg ka apna koi broker fill nahi hai"
                                  >
                                    broker fill nahi
                                  </span>
                                )}
                              </div>
                            ))}
                            {/* 🔴 A SYSTEM FAULT THAT COST MONEY IS PART OF THE
                                RECORD. On 04-Sep the platform's SL fired four
                                minutes after the engine's stop had already taken
                                the position to zero, and opened a short 400 from
                                flat. It is not this position's exit — so it is
                                shown apart, with its own fill-sourced number,
                                and it is COUNTED in the totals below. Hiding a
                                loss the system caused would make the record
                                flattering in exactly the way it must not be. */}
                            {p.duplicate_exit && (
                              <div
                                className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-0.5 border-t border-amber-300/20 pt-1 text-11 text-amber-200/90"
                                data-testid="duplicate-exit"
                                title={p.duplicate_exit.reason ?? undefined}
                              >
                                <span className="min-w-[9.5rem] font-medium">
                                  {p.duplicate_exit.label ??
                                    "system galti: duplicate exit"}
                                </span>
                                <span className="tabular-nums">
                                  {p.duplicate_exit.side?.toUpperCase() ?? ""}{" "}
                                  {p.duplicate_exit.qty ?? "—"}
                                </span>
                                <span className="tabular-nums">
                                  {p.duplicate_exit.price ?? "—"}
                                </span>
                                <span className="font-mono text-10 opacity-70">
                                  {p.duplicate_exit.broker_order_id ?? "—"}
                                </span>
                                {p.duplicate_exit.gross_pnl != null && (
                                  <span className="tabular-nums text-loss">
                                    {formatCurrency(
                                      Number(p.duplicate_exit.gross_pnl),
                                      { showSign: true },
                                    )}
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    ) : null,
                  ])}
                </tbody>
                {/* A1 — the two totals, side by side and never added together.
                    Rendered only when there is something to total, so an empty
                    page never prints a confident 0.00. */}
                {totals.counted > 0 && (
                  <tfoot
                    className="border-t border-white/10 bg-white/[0.02]"
                    data-testid="positions-totals"
                  >
                    <tr>
                      <td colSpan={11} className="p-3 text-right text-xs text-muted-foreground">
                        {totals.counted} row{totals.counted === 1 ? "" : "s"} ka total
                      </td>
                      <td className="p-3 text-right tabular-nums">
                        <div data-testid="total-gross" className="text-xs">
                          <span className="text-muted-foreground">TOTAL GROSS </span>
                          <span className={totals.gross >= 0 ? "text-profit" : "text-loss"}>
                            {formatCurrency(totals.gross, { showSign: true })}
                          </span>
                        </div>
                        <div data-testid="total-net" className="text-xs">
                          <span className="text-muted-foreground">TOTAL NET </span>
                          {totals.unbilled > 0 ? (
                            <span
                              className="text-amber-200/90"
                              title={`${totals.unbilled} row(s) ka charges bill abhi Dhan se nahi aaya — unka net nahi joda ja sakta`}
                            >
                              baaki ({totals.unbilled} row
                              {totals.unbilled === 1 ? "" : "s"} ka bill baaki)
                            </span>
                          ) : (
                            <span className={totals.net >= 0 ? "text-profit" : "text-loss"}>
                              {formatCurrency(totals.net, { showSign: true })}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="p-3" />
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          )}
        </GlassmorphismCard>
        )}
        <p className="mt-3 text-xs text-muted-foreground">
          Har 15 second mein apne aap update hoti hai. Kuch strategies apna
          exit khud nahi karti — position tab tak khuli rehti hai jab tak
          strategy ka exit signal nahi aata.
        </p>
      </motion.div>
      </ProPage>
    </motion.div>
  );
}
