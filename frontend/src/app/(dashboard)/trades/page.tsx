"use client";

/**
 * /trades — THE BOT ORDER LOG. Not the account trade book.
 *
 * ⛔ THIS PAGE IS THE BOT'S RECORD, NOT THE ACCOUNT'S. ⛔
 * It shows ONLY orders belonging to a tracked position of this strategy:
 * orders TRADETRI placed, plus the engine's own broker-side stop fills, which
 * are attributed to their position through the ENGINE LEDGER (child fill ->
 * tape algoOrdNo -> parent Forever id -> the trade that stop was placed for),
 * never by matching on time.
 *
 * Manual Dhan-app fills and other instruments are NOT shown. A briefly-shipped
 * "whole account fills" section was removed on 2026-09-16: this page is shown
 * to other people as the bot's live record, and a manual trade sitting in it
 * is a claim about the bot that is not true.
 *
 * ONE ROW PER BROKER ORDER. `strategy_executions` stores one row per LEG: the
 * 07-Sep entry is four rows of 200 sharing broker_order_id 322260907150406,
 * and it rendered as four separate 200-lot orders — a customer counting his
 * own orders would have counted four where the broker shows one. The rows are
 * grouped by broker_order_id here; quantity is the SUM of the legs, the price
 * is the leg price the broker already averaged, and the time is the order's.
 *
 * NO P&L COLUMN. Per-trade money lives on /positions, which is the only place
 * that knows a round trip. An order leg has no P&L to show.
 *
 * The legs expander stays OUT until a position_id mapping exists — inventing
 * one client-side would be a mapping nobody verified.
 */

import { useState, useMemo } from "react";
import { groupLegsIntoOrders } from "@/lib/broker-orders";
import { motion } from "framer-motion";
import { Loader2, AlertTriangle, RefreshCw, Download } from "lucide-react";
import { toast } from "sonner";
import { ProPage, ProEmpty } from "@/components/dashboard/pro-page";
import { TrackingEpochNote } from "@/components/dashboard/tracking-epoch-note";
import { UpgradeWall } from "@/components/billing/upgrade-wall";
import { GlassmorphismCard } from "@/shared/ui/glassmorphism-card";
import { GlowButton } from "@/shared/ui/glow-button";
import { Badge } from "@/shared/ui/badge";
import { useApi } from "@/shared/api/use-api";
import { api, ApiError } from "@/shared/api/client";
import { cn } from "@/shared/lib/utils";
import { formatPriceOrUnknown } from "@/shared/lib/price-display";
import { ARCHIVE_HINT, sinceEpochHeadline, useTrackingEpoch } from "@/lib/tracking-epoch";

/**
 * The CSV is of THIS list — `/strategies/executions` — not the legacy
 * `/users/me/trades/export`, which streams the `trades` table the strategy
 * engine never writes (0 rows on prod). Same owner-scoped query server-side,
 * so the file can never disagree with the page it was downloaded from.
 */
const EXPORT_ENDPOINT = "/strategies/executions/export";
const EXPORT_FILENAME = "tradetri-executions.csv";

/** The page's own name, and the sentence that keeps it honest. */
const PAGE_TITLE = "TRADETRI ke orders";
const PAGE_BLURB = "TRADETRI ke orders, aur neeche broker par hue baaki fills.";

/** A status we have not read. Never the word "pending" — that is a claim. */
const NO_STATUS = "—";

const stagger = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.05 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

interface Execution {
  id: string;
  signal_id: string;
  leg_number: number;
  leg_role: string;
  symbol: string;
  side: string;
  quantity: number;
  order_type: string;
  price: string | null;
  broker_order_id: string | null;
  broker_status: string | null;
  error_code: string | null;
  error_message: string | null;
  placed_at: string;
  completed_at: string | null;
}

interface ExecutionsResponse {
  executions: Execution[];
  count: number;
}

type LegFilter =
  | "all"
  | "entry"
  | "direct_partial"
  | "direct_exit"
  | "direct_sl"
  | "partial_target"
  | "trailing_sl"
  | "hard_sl";

const LEG_ROLE_LABEL: Record<string, { label: string; cls: string }> = {
  entry: { label: "ENTRY", cls: "bg-accent-blue/15 text-accent-blue border-accent-blue/30" },
  direct_partial: {
    label: "PARTIAL",
    cls: "bg-yellow-500/15 text-yellow-500 border-yellow-500/30",
  },
  direct_exit: { label: "EXIT", cls: "bg-profit/15 text-profit border-profit/30" },
  direct_sl: { label: "SL_HIT", cls: "bg-loss/15 text-loss border-loss/30" },
  partial_target: {
    label: "PARTIAL",
    cls: "bg-yellow-500/15 text-yellow-500 border-yellow-500/30",
  },
  trailing_sl: { label: "TRAIL_SL", cls: "bg-orange-500/15 text-orange-500 border-orange-500/30" },
  hard_sl: { label: "HARD_SL", cls: "bg-loss/15 text-loss border-loss/30" },
  circuit_breaker: { label: "BREAKER", cls: "bg-loss/15 text-loss border-loss/30" },
  kill_switch: { label: "KILL_SW", cls: "bg-loss/15 text-loss border-loss/30" },
};

const EXIT_ROLES = [
  "direct_exit",
  "direct_partial",
  "direct_sl",
  "partial_target",
  "trailing_sl",
  "hard_sl",
];

/** ONE BROKER ORDER, assembled from its legs. */
export interface BrokerOrderRow {
  key: string;
  brokerOrderId: string | null;
  placedAt: string;
  legRole: string;
  symbol: string;
  side: string;
  /** The sum of the legs — what the broker actually filled on this order. */
  quantity: number;
  price: string | null;
  brokerStatus: string | null;
  errorCode: string | null;
  legs: number;
}

/**
 * Legs → orders for this page's row shape.
 *
 * The RULE lives in `@/lib/broker-orders` — one owner, shared with the
 * Overview, so the two screens can never count the same activity differently
 * (ADR 0001 §2). This only maps the shared result onto what the table renders.
 */
export function groupByBrokerOrder(rows: Execution[]): BrokerOrderRow[] {
  return groupLegsIntoOrders(
    rows.map((e) => ({ ...e, timestamp: e.placed_at })),
  ).map((o) => ({
    key: o.key,
    brokerOrderId: o.first.broker_order_id,
    // placed_at is NOT NULL on an execution, so the shared nullable falls back.
    placedAt: o.timestamp ?? o.first.placed_at,
    legRole: o.first.leg_role,
    symbol: o.first.symbol,
    side: o.first.side,
    quantity: o.quantity,
    price: o.first.price,
    brokerStatus: o.brokerStatus,
    errorCode: o.first.error_code,
    legs: o.legs,
  }));
}

export default function TradesPage() {
  const [legFilter, setLegFilter] = useState<LegFilter>("all");
  const [exporting, setExporting] = useState(false);
  // Where the record starts — from the server, never written here. This list
  // IS the history, so an empty one must name the period it is empty for.
  const { shortLabel: epochShort } = useTrackingEpoch();

  async function exportCsv() {
    setExporting(true);
    try {
      const bytes = await api.download(EXPORT_ENDPOINT, EXPORT_FILENAME);
      toast.success(`Exported ${EXPORT_FILENAME} (${bytes.toLocaleString("en-IN")} bytes)`);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Export failed";
      toast.error(msg);
    } finally {
      setExporting(false);
    }
  }

  const { data, isLoading, error, refetch, paywalled, paywallUrl } = useApi<ExecutionsResponse>(
    "/strategies/executions?limit=200",
    null,
    60_000,
  );

  const all = useMemo(() => data?.executions ?? [], [data]);
  const orders = useMemo(() => groupByBrokerOrder(all), [all]);
  const filtered = useMemo(
    () => (legFilter === "all" ? orders : orders.filter((o) => o.legRole === legFilter)),
    [orders, legFilter],
  );

  // ORDERS, not legs. Counting legs told the founder he had placed four
  // orders on 07-Sep when the broker had one.
  const stats = useMemo(() => {
    const entries = orders.filter((o) => o.legRole === "entry").length;
    const exits = orders.filter((o) => EXIT_ROLES.includes(o.legRole)).length;
    return { orders: orders.length, entries, exits, legs: all.length };
  }, [orders, all]);

  const filterChips: LegFilter[] = ["all", "entry", "direct_partial", "direct_exit", "direct_sl"];

  // Same three-way branch the card used to hold, named so the empty state can
  // step OUT of the card without the order of the cases drifting.
  const showError = !!error && !data;
  const showLoading = !showError && isLoading && !data;
  const showEmpty = !showError && !showLoading && filtered.length === 0;

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto"
    >
      <ProPage
        // The page says what it is. The sidebar calls it "Trades"; a customer
        // reading THIS screen must be told, in the header, that these are the
        // bot's orders and that his own manual fills are not here.
        title={PAGE_TITLE}
        blurb={PAGE_BLURB}
        // The ONE primary action. It is a button, not a link, so it comes in
        // through actionSlot. Hidden behind the wall — the endpoint is gated the
        // same way as the list, so a button here would only ever 402. Disabled
        // with no rows: an empty file is not a feature.
        actionSlot={
          paywalled ? undefined : (
            <GlowButton
              size="sm"
              onClick={exportCsv}
              disabled={exporting || isLoading || all.length === 0}
              data-testid="export-csv"
              aria-label="Export trades as CSV"
            >
              {exporting ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Download className="h-4 w-4 mr-2" />
              )}
              Export CSV
            </GlowButton>
          )
        }
      >
        <div className="space-y-6">
          <TrackingEpochNote />

          {paywalled ? (
            <motion.div variants={fadeUp}>
              <UpgradeWall
                feature="Trade history"
                description="Your full strategy-engine execution history is a premium feature."
                upgradeUrl={paywallUrl ?? undefined}
              />
            </motion.div>
          ) : (
            <>
              <motion.div variants={fadeUp} className="grid grid-cols-3 gap-3">
                <div className="rounded-lg border border-white/[0.05] bg-white/[0.02] p-4">
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">
                    Orders
                  </div>
                  <div className="text-2xl font-bold mt-1" data-testid="tile-orders">
                    {stats.orders}
                  </div>
                  {/* Says WHY this is smaller than the row count used to be. */}
                  <div className="text-xs text-muted-foreground mt-1">
                    {stats.legs} execution leg{stats.legs === 1 ? "" : "s"}
                  </div>
                </div>
                <div className="rounded-lg border border-white/[0.05] bg-white/[0.02] p-4">
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">
                    Entries
                  </div>
                  <div className="text-2xl font-bold mt-1 text-accent-blue" data-testid="tile-entries">
                    {stats.entries}
                  </div>
                </div>
                <div className="rounded-lg border border-white/[0.05] bg-white/[0.02] p-4">
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">Exits</div>
                  <div className="text-2xl font-bold mt-1 text-profit" data-testid="tile-exits">
                    {stats.exits}
                  </div>
                </div>
              </motion.div>

              {/* Refresh belongs WITH the list it refreshes, not in the page
                  header — the header carries the one primary action. */}
              <motion.div variants={fadeUp} className="flex flex-wrap items-center gap-2">
                {filterChips.map((f) => (
                  <button
                    key={f}
                    onClick={() => setLegFilter(f)}
                    className={cn(
                      "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                      legFilter === f
                        ? "bg-accent-blue/15 border-accent-blue/40 text-accent-blue"
                        : "bg-white/[0.02] border-white/[0.05] text-muted-foreground hover:bg-white/[0.04]",
                    )}
                  >
                    {f === "all" ? "All" : (LEG_ROLE_LABEL[f]?.label ?? f)}
                  </button>
                ))}
                <GlowButton size="sm" onClick={refetch} className="ml-auto">
                  <RefreshCw className={cn("h-4 w-4 mr-2", isLoading && "animate-spin")} /> Refresh
                </GlowButton>
              </motion.div>

              <motion.div variants={fadeUp}>
                {showEmpty ? (
                  <ProEmpty
                    // The headline wording is fixed by
                    // tests/tracking/tracking-epoch.test.tsx — it is the
                    // sentence that names (or refuses to name) the cut-off
                    // period, and the period is the point of it. Only the
                    // "what happens next" line changed: it used to promise
                    // "har entry aur exit LEG yahan dikhega", which this page
                    // no longer does — one row is one broker order.
                    headline={
                      legFilter !== "all"
                        ? `Is filter mein koi trade nahi — ${LEG_ROLE_LABEL[legFilter]?.label ?? legFilter}`
                        : epochShort
                        ? sinceEpochHeadline(epochShort, "abhi tak koi trade nahi hui")
                        : "Abhi tak koi trade nahi hui"
                    }
                    next={
                      legFilter !== "all"
                        ? "Is leg type ka koi order nahi hai. Poori list ke liye 'All' chuno."
                        : "Jab aapki chalu strategy pehla order bhejegi, woh yahan dikhega. Pehle ek strategy chalu karo." +
                          (epochShort ? ` ${ARCHIVE_HINT}` : "")
                    }
                    action={
                      legFilter === "all"
                        ? { label: "Strategies", href: "/strategies" }
                        : undefined
                    }
                  />
                ) : (
                  <GlassmorphismCard hover={false} className="p-0 overflow-hidden">
                    {showError ? (
                      <div className="p-8 text-center">
                        <AlertTriangle className="h-10 w-10 text-loss mx-auto mb-3" />
                        <h3 className="font-semibold mb-1">Could not load the order log</h3>
                        <p className="text-sm text-muted-foreground mb-4">{error}</p>
                        <GlowButton onClick={refetch} size="sm">
                          Retry
                        </GlowButton>
                      </div>
                    ) : showLoading ? (
                      <div className="p-12 flex justify-center">
                        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                      </div>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead className="bg-white/[0.02] text-xs text-muted-foreground uppercase">
                            <tr>
                              <th className="text-left p-3 font-medium">Placed</th>
                              <th className="text-left p-3 font-medium">Type</th>
                              <th className="text-left p-3 font-medium">Symbol</th>
                              <th className="text-left p-3 font-medium">Side</th>
                              <th className="text-right p-3 font-medium">Qty</th>
                              <th className="text-right p-3 font-medium">Price</th>
                              <th className="text-left p-3 font-medium">Broker order</th>
                              <th className="text-left p-3 font-medium">Status</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filtered.map((o) => {
                              const role = LEG_ROLE_LABEL[o.legRole] ?? {
                                label: o.legRole,
                                cls: "bg-muted text-muted-foreground",
                              };
                              const isError = !!o.errorCode;
                              return (
                                <tr
                                  key={o.key}
                                  data-testid="order-row"
                                  className={cn(
                                    "border-t border-white/[0.04] hover:bg-white/[0.02]",
                                    isError && "bg-loss/5",
                                  )}
                                >
                                  <td className="p-3 text-xs text-muted-foreground whitespace-nowrap">
                                    {new Date(o.placedAt).toLocaleString("en-IN", {
                                      dateStyle: "short",
                                      timeStyle: "medium",
                                    })}
                                  </td>
                                  <td className="p-3">
                                    <Badge className={cn("uppercase text-xs", role.cls)}>
                                      {role.label}
                                    </Badge>
                                  </td>
                                  <td className="p-3 font-mono text-xs">{o.symbol}</td>
                                  <td className="p-3">
                                    <span
                                      className={cn(
                                        "uppercase text-xs font-medium",
                                        o.side.toLowerCase() === "buy" ? "text-profit" : "text-loss",
                                      )}
                                    >
                                      {o.side}
                                    </span>
                                  </td>
                                  <td className="p-3 text-right tabular-nums">{o.quantity}</td>
                                  <td className="p-3 text-right tabular-nums">
                                    {formatPriceOrUnknown(o.price)}
                                  </td>
                                  <td className="p-3 font-mono text-xs text-muted-foreground max-w-[200px] truncate">
                                    {o.brokerOrderId ?? "—"}
                                  </td>
                                  <td className="p-3">
                                    {isError ? (
                                      <Badge className="uppercase text-xs bg-loss/15 text-loss border-loss/30">
                                        {o.errorCode}
                                      </Badge>
                                    ) : o.brokerStatus ? (
                                      <Badge className="uppercase text-xs bg-profit/15 text-profit border-profit/30">
                                        {o.brokerStatus}
                                      </Badge>
                                    ) : (
                                      // NOT "pending". We have not read a
                                      // status; saying one would be a claim
                                      // about an order state nobody read.
                                      <span
                                        className="text-xs text-muted-foreground"
                                        data-testid="status-unknown"
                                        title="Broker ne is order ka status abhi nahi bataya"
                                      >
                                        {NO_STATUS}
                                      </span>
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
                )}
              </motion.div>

            </>
          )}
        </div>
      </ProPage>
    </motion.div>
  );
}
