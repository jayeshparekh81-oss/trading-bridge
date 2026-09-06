"use client";

/**
 * THE ONE STRATEGY CARD (founder, 2026-09-05): the rich showcase card —
 * backtest stats with their honest labels, risk band, min capital, the
 * live-record verification state and ONE call to action — rendered from ONE
 * data source (hooks/useShowcase.ts) on BOTH surfaces:
 *
 *   public Track Record  surface="public"  CTA: Start Free (logged out, ?next=
 *                        back to this strategy) · "App mein kholo →" (logged in)
 *   app Marketplace      surface="app"     layout="compact" in the Pro grid,
 *                        "full" one-at-a-time in Simple, and on listing detail
 *
 * Numbers can never drift between the two: same component, same fields, same
 * formatters. Masking is the API's (S1/S2/S3); this component adds nothing.
 *
 * HONESTY: shows ONLY what the API returns. No fabricated live trades, no
 * compounded totals, no rupee P&L. Drawdown is the negative value the API
 * returns. Risk is as prominent as return.
 */

import type { ReactNode } from "react";
import { useState } from "react";
import Link from "next/link";
import { ArrowRight, ShieldAlert } from "lucide-react";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { EquityCurve } from "@/components/charts/equity-curve";
import { DEFAULT_RANGE, RANGE_OPTIONS, type RangeKey, rangeMonths, rebaseToWindow } from "@/lib/showcase/range";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { withNext } from "@/lib/safe-next";
import { RiskChip } from "@/components/risk/risk-chip";
import { CARD_RISK_BAND_HINT, CARD_RISK_BAND_LABEL, EDITORIAL_NOTE, FUTURES_BASIS_LABEL, highVolatilityNote } from "@/lib/risk-labels";
import { BADGE, type Direction, type LiveRecord, type Metrics, type ShowcaseDetail, type ShowcaseListItem } from "@/lib/showcase/data";

/** Founder's wording (2026-09-04) while live execution is unverified. Exact; do not soften. */
export const VERIFICATION_PERIOD_NOTE = "Live execution is in a verification period — live results are not yet published.";

// ── formatters (exported so a test can assert both surfaces print the same strings) ──
export const fmt = {
  pct1: (v: number) => `${v.toFixed(1)}%`,
  signed: (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(2)}%`,
  dd: (v: number) => `${v.toFixed(2)}%`, // already negative
  pf: (v: number | null) => (v == null ? "∞" : v.toFixed(2)),
  num: (v: number) => v.toLocaleString("en-IN"),
};

// Customer-friendly stat copy: plain Hinglish label + the real technical term + a one-line tooltip.
export const STAT = {
  win: { label: "Jeetne wale trades", tech: "win rate", tip: "100 mein se kitne trades profit mein band hue" },
  avg: { label: "Har trade ka average", tech: "avg/trade", tip: "Har trade average kitna % deta hai — charges ke baad" },
  pf: { label: "Profit ratio", tech: "profit factor", tip: "₹1 nuksaan ke badle kitna kamaya. 2 = double" },
  dd: { label: "Sabse bada gir", tech: "max drawdown", tip: "Peak se kitna neeche gaya — yeh aapka risk hai" },
  trades: { label: "Kitne trades", tech: "sample", tip: "Itne trades pe yeh data bana" },
} as const;

/** The honest live line for a live record (exported: the test pins the states). */
export function liveLineFor(live: LiveRecord | null | undefined): { em: string; sub: string } {
  if (!live) return { em: "Loading live record…", sub: "" };
  if (live.status === "paper_no_live")
    return { em: "Backtest-only candidate.", sub: "No real-money results exist. In paper evaluation; promoted to live only after forward-testing." };
  if (live.status === "verification_period") return { em: VERIFICATION_PERIOD_NOTE, sub: "" };
  const interfered =
    typeof live.human_interfered_trades === "number" && live.human_interfered_trades > 0
      ? ` ${live.human_interfered_trades} closed trade(s) are human-interfered — not attributable: excluded by rule, not zeroed.`
      : "";
  if ((live.reconciled_trades ?? 0) > 0)
    return { em: `${live.reconciled_trades ?? 0} live trade(s) reconciled.`, sub: `Verified per-trade results pending publication — no P&L shown until reviewed.${interfered}` };
  if (interfered && live.status === "tracking_active") return { em: "Live tracking active.", sub: `Nothing priced yet.${interfered} No estimates, no padding.` };
  if (live.status === "tracking_active")
    return { em: "Live tracking active.", sub: "Verified trades publish as they accumulate — nothing recorded yet. No estimates, no padding." };
  return { em: "No verified record yet.", sub: "Nothing recorded — no estimates, no padding." };
}

// ── small parts ──────────────────────────────────────────────────────
function Seg<T extends string>({ value, options, onChange, ariaLabel }: { value: T; options: { v: T; label: string }[]; onChange: (v: T) => void; ariaLabel: string }) {
  return (
    <div role="group" aria-label={ariaLabel} className="inline-flex rounded-lg border border-border bg-white/[0.02] overflow-hidden">
      {options.map((o) => (
        <button
          key={o.v}
          type="button"
          aria-pressed={value === o.v}
          onClick={() => onChange(o.v)}
          className={cn(
            "px-3.5 py-1.5 text-xs font-semibold tracking-wide transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-profit/60",
            value === o.v ? "bg-profit/12 text-profit" : "text-muted-foreground hover:text-foreground",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function InfoTip({ content, children, className }: { content: string; children: ReactNode; className?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <Tooltip open={open} onOpenChange={setOpen}>
      <TooltipTrigger
        render={<button type="button" onClick={() => setOpen((o) => !o)} />}
        className={cn("cursor-help text-left rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-profit/50", className)}
      >
        {children}
      </TooltipTrigger>
      <TooltipContent className="max-w-[15rem] text-11 leading-relaxed">{content}</TooltipContent>
    </Tooltip>
  );
}

function Stat({ value, stat, tone, testid }: { value: string; stat: { label: string; tech: string; tip: string }; tone?: string; testid: string }) {
  return (
    <div className="min-w-0" data-testid={testid}>
      <div className={cn("text-lg font-bold font-mono tabular-nums tracking-tight", tone ?? "text-foreground/80")} data-testid={`${testid}-value`}>
        {value}
      </div>
      <InfoTip content={stat.tip} className="mt-0.5 block">
        <span className="block text-11 font-semibold text-foreground/85 leading-tight underline decoration-dotted decoration-muted-foreground/40 underline-offset-2">
          {stat.label}
        </span>
        <span className="block text-9 text-muted-foreground/55 leading-tight mt-px lowercase">{stat.tech}</span>
      </InfoTip>
    </div>
  );
}

/** The public Track Record's ONE call to action: register (and come straight back) or open the app. */
export function PublicStrategyCta({ listingId, className }: { listingId?: string | null; className?: string }) {
  const { user, isLoading } = useAuth();
  if (!listingId) return null;
  const target = `/marketplace/${listingId}`;
  if (isLoading) {
    return (
      <div data-testid="showcase-subscribe-loading" aria-hidden className={cn("inline-flex items-center rounded-lg bg-white/[0.04] px-4 py-2 text-sm text-transparent select-none", className)}>
        Start Free
      </div>
    );
  }
  const href = user ? target : withNext("/register", target);
  return (
    <Link
      href={href}
      data-testid="showcase-subscribe"
      data-authed={user ? "yes" : "no"}
      className={cn("inline-flex items-center gap-1.5 rounded-lg px-4 py-2 bg-primary text-primary-foreground text-sm font-semibold hover:opacity-90 transition-opacity", className)}
    >
      {user ? "App mein kholo" : "Start Free"}
      <ArrowRight className="h-3.5 w-3.5" />
    </Link>
  );
}

/** A listing with no showcase entry still renders the same card shape — honestly empty (pair with `unproven`). */
export function unprovenItem(listingId: string, title: string): ShowcaseListItem {
  return {
    key: `listing-${listingId}`,
    instrument: "—",
    name: title,
    live_status: { track_type: "PAPER", label: "No verified record yet", disclaimer: "" },
    basis: "",
    disclaimer: "",
    headline_net: { win_rate_pct: 0, avg_pct_per_trade: 0, profit_factor: null, max_drawdown_pct: 0, trades: 0 },
  };
}

// ── the card ─────────────────────────────────────────────────────────
export interface StrategyListingInfo {
  id: string;
  price_inr: number;
  subscriber_count: number;
  rating_avg: number | null;
  rating_count: number;
}

export interface StrategyCardProps {
  /** Masked showcase item (name "Strategy S1", instrument, live status, headline NET). */
  item: ShowcaseListItem;
  detail?: ShowcaseDetail | null;
  live?: LiveRecord | null;
  /** The published marketplace listing joined by listing_id (price, subscribers, rating). */
  listing?: StrategyListingInfo | null;
  surface: "public" | "app";
  /** "full" = everything (chart, per-period table); "compact" = header + live record + headline stats. */
  layout?: "full" | "compact";
  /** Replaces the default CTA (public: Start Free / App mein kholo; app compact: "Dekho →"). */
  cta?: ReactNode;
  /** Where a compact app card opens. */
  href?: string;
  /**
   * A marketplace listing with NO showcase entry: no backtest, no live record,
   * and we do not know its segment. The card then shows the non-claiming risk
   * RANGE (not a segment chip) and an honest "nothing published" panel instead
   * of numbers. Never fabricate a zero.
   */
  unproven?: boolean;
}

export function StrategyCard({ item, detail, live, listing, surface, layout = "full", cta, href, unproven = false }: StrategyCardProps) {
  const [dir, setDir] = useState<Direction>("all");
  const [range, setRange] = useState<RangeKey>(DEFAULT_RANGE);
  const [period, setPeriod] = useState<"yearly" | "monthly">("yearly");

  const badge = BADGE[item.live_status.track_type];
  const agg: Metrics = detail?.backtest.aggregate[dir] ?? ({ ...item.headline_net } as Metrics); // headline = NET 'all' until detail loads
  const periods = detail ? Object.entries(period === "yearly" ? detail.backtest.by_year : detail.backtest.by_month) : [];
  const sliceCaveat = dir !== "all" ? (agg.caveat ?? detail?.meta.slice_caveat) : null;
  const rawSeries = detail?.backtest.series?.[dir]?.equity_curve_noncompounded ?? [];
  const equityPoints = rebaseToWindow(rawSeries, rangeMonths(range));
  const liveLine = unproven
    ? { em: "No verified record yet.", sub: "Yeh strategy abhi public Track Record par nahi hai — koi backtest ya live record publish nahi hua. No estimates, no padding." }
    : liveLineFor(live);
  const listingId = listing?.id ?? live?.listing_id ?? null;
  const detailHref = href ?? (listingId ? `/marketplace/${listingId}` : null);

  const defaultCta =
    surface === "public" ? (
      <PublicStrategyCta listingId={listingId} className="mt-3.5" />
    ) : layout === "compact" && detailHref ? (
      <Link href={detailHref} data-testid="strategy-open" className="mt-3.5 inline-flex items-center gap-1.5 rounded-lg px-4 py-2 bg-primary text-primary-foreground text-sm font-semibold hover:opacity-90 transition-opacity">
        Dekho <ArrowRight className="h-3.5 w-3.5" />
      </Link>
    ) : null;

  return (
    <TooltipProvider delay={120}>
      <div data-testid={`strategy-card-${item.key}`} data-surface={surface} data-layout={layout}>
      <GlassmorphismCard hover={false} className="p-0 overflow-hidden">
        {/* header */}
        <div className="flex items-start justify-between gap-4 flex-wrap p-6 pb-0">
          <div>
            <h3 className="text-lg font-bold tracking-tight" data-testid="strategy-name">
              {item.name}
            </h3>
            {unproven ? (
              /* Segment unknown (instrument_type is not on the listing): the
                 RANGE + "by segment" is the only honest band. */
              <div className="flex items-center gap-2 flex-wrap mt-0.5">
                <span data-testid="card-risk-band" title={CARD_RISK_BAND_HINT} className="inline-flex items-center gap-1 text-10 text-muted-foreground border border-white/[0.08] rounded-full px-2 py-0.5">
                  <ShieldAlert className="h-3 w-3 opacity-70" />
                  {CARD_RISK_BAND_LABEL}
                </span>
              </div>
            ) : (
              <>
                {/* Showcase strategies are unambiguously FUTURES (NRML), so a single segment chip is truthful here. */}
                <div className="flex items-center gap-2 flex-wrap mt-0.5">
                  <p className="text-xs text-muted-foreground/70">{item.instrument} · Futures, overnight hold</p>
                  <RiskChip segment="futures" />
                </div>
                <p className="text-10 text-amber-300/70 leading-relaxed mt-1 max-w-md">{EDITORIAL_NOTE}</p>
              </>
            )}
            {highVolatilityNote(item.instrument) ? (
              <p data-testid="high-volatility-note" className="text-10 text-muted-foreground/80 leading-relaxed mt-1 max-w-md">
                {highVolatilityNote(item.instrument)}
              </p>
            ) : null}
            {listing ? (
              <p className="mt-1.5 text-xs text-muted-foreground" data-testid="strategy-listing-line">
                {listing.price_inr > 0 ? `₹${listing.price_inr.toLocaleString("en-IN")} / month` : "Free"} · {listing.subscriber_count} subscriber{listing.subscriber_count === 1 ? "" : "s"}
                {listing.rating_avg != null ? ` · ★ ${Number(listing.rating_avg).toFixed(1)} (${listing.rating_count})` : ""}
              </p>
            ) : null}
          </div>
          <span className={cn("inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-11 font-semibold", badge.cls)}>
            <span className={cn("h-1.5 w-1.5 rounded-full", badge.dot)} />
            {item.live_status.label}
          </span>
        </div>

        {/* primary: live record + risk (the prominent, honest part) */}
        <div className="grid md:grid-cols-[1.4fr_1fr] gap-3.5 p-6 pt-5">
          <div className="rounded-xl border border-border bg-white/[0.018] p-4" data-testid="strategy-live-record">
            <div className="flex items-center gap-2 text-10 uppercase tracking-[0.14em] text-muted-foreground/70 font-semibold" data-testid="strategy-live-heading">
              {/* "Verified" only once real reconciled trades are published — never before. */}
              <span data-testid="strategy-live-heading-text">{live?.status === "tracking_active" && (live.reconciled_trades ?? 0) > 0 ? "Verified live record" : "Live record"}</span>
              <span className="text-accent-gold text-9 border border-accent-gold/30 rounded px-1.5 py-px">◆ ledger</span>
            </div>
            <div data-testid="strategy-live-line">
              <p className="mt-2.5 text-sm leading-relaxed">
                <span className="text-profit font-semibold">{liveLine.em}</span>
              </p>
              {liveLine.sub && <p className="mt-1.5 text-xs text-muted-foreground">{liveLine.sub}</p>}
            </div>
            {cta ?? defaultCta}
          </div>
          {unproven ? (
            <div data-testid="strategy-unproven" className="rounded-xl border border-dashed border-muted-foreground/25 bg-muted/[0.04] p-4">
              <div className="text-10 uppercase tracking-[0.14em] text-muted-foreground/70 font-semibold">Backtest · Risk</div>
              <p className="mt-2 text-sm text-muted-foreground leading-relaxed">Publish nahi hua. Numbers tab dikhenge jab verified record banega — hum andaaza nahi dikhate.</p>
            </div>
          ) : (
          <div data-testid="certified-metrics-risk" className="rounded-xl border border-border bg-white/[0.018] p-4">
            <div className="text-10 uppercase tracking-[0.14em] text-muted-foreground/70 font-semibold">Risk · Max drawdown</div>
            <div className="mt-2 text-3xl font-bold font-mono tabular-nums tracking-tight text-loss" data-testid="strategy-dd-value">
              {fmt.dd(agg.max_drawdown_pct)}
            </div>
            <div className="text-11 text-muted-foreground mt-1">Worst peak-to-trough — non-compounded, in-sample · {FUTURES_BASIS_LABEL}</div>
          </div>
          )}
        </div>

        {/* backtest = subordinate, clearly hypothetical */}
        {!unproven && (
        <div data-testid="certified-metrics" className="m-6 mt-0 rounded-xl border border-dashed border-muted-foreground/25 bg-muted/[0.04] p-4">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-2 text-11 uppercase tracking-wider text-muted-foreground font-semibold">
              In-sample backtest{detail ? ` · ${detail.backtest.in_sample_range.from} → ${detail.backtest.in_sample_range.to}` : ""}
              <span className="text-9 tracking-normal bg-muted/40 text-muted-foreground px-1.5 py-0.5 rounded border border-border normal-case">Hypothetical — not a guarantee</span>
              <span className="text-9 tracking-normal bg-muted/40 text-muted-foreground px-1.5 py-0.5 rounded border border-border normal-case">{FUTURES_BASIS_LABEL}</span>
            </div>
            {layout === "full" ? (
              <Seg<Direction> value={dir} onChange={setDir} ariaLabel="Trade direction" options={[{ v: "all", label: "All" }, { v: "long", label: "Long" }, { v: "short", label: "Short" }]} />
            ) : null}
          </div>

          <div className="grid grid-cols-3 sm:grid-cols-5 gap-2.5 mt-4" data-testid="strategy-stats">
            <Stat value={fmt.pct1(agg.win_rate_pct)} stat={STAT.win} tone="text-accent-blue" testid="stat-win" />
            <Stat value={fmt.signed(agg.avg_pct_per_trade)} stat={STAT.avg} tone="text-profit" testid="stat-avg" />
            <Stat value={fmt.pf(agg.profit_factor)} stat={STAT.pf} tone="text-accent-gold" testid="stat-pf" />
            <Stat value={fmt.dd(agg.max_drawdown_pct)} stat={STAT.dd} tone="text-loss" testid="stat-dd" />
            <Stat value={fmt.num(agg.trades)} stat={STAT.trades} testid="stat-trades" />
          </div>

          {sliceCaveat && (
            <p className="mt-3 text-11 text-accent-gold/90 bg-accent-gold/[0.06] border border-accent-gold/20 rounded-md px-2.5 py-1.5 flex gap-1.5">
              <span aria-hidden>⚠</span> {sliceCaveat}
            </p>
          )}

          {layout === "full" && (
            <>
              <div className="mt-5">
                <div className="flex items-baseline justify-between gap-2 flex-wrap">
                  <span className="text-10 uppercase tracking-[0.14em] text-muted-foreground/70 font-semibold">Cumulative edge ({dir})</span>
                  <span className="text-10 text-muted-foreground/60">Non-compounded · NET %</span>
                </div>
                <p className="mt-1 text-11 text-muted-foreground/70 leading-snug">
                  Cumulative edge — fixed-size, non-compounded (NOT a compounded return). Each point is the running sum of per-trade NET&nbsp;% at its exit date.
                </p>
                {!detail ? (
                  <div className="mt-2 h-[200px] grid place-items-center text-xs text-muted-foreground">Loading chart…</div>
                ) : equityPoints.length === 0 ? (
                  <div className="mt-2 h-[200px] grid place-items-center text-xs text-muted-foreground">No {dir} trades to chart.</div>
                ) : (
                  <div className="mt-2">
                    <EquityCurve data={equityPoints} unit="pct" valueLabel="Cumulative net %" />
                  </div>
                )}
                <div className="mt-3 flex items-center justify-between gap-2 flex-wrap">
                  <span className="text-10 text-muted-foreground/60 leading-snug">
                    {range === "All" ? "Full series, from 0% at the first trade." : `Last ${range}, re-based to 0% — window measured from the backtest's latest date.`}
                  </span>
                  <div className="overflow-x-auto -mx-1 px-1">
                    <Seg<RangeKey> value={range} onChange={setRange} ariaLabel="Equity curve time range" options={RANGE_OPTIONS.map((o) => ({ v: o.v, label: o.v }))} />
                  </div>
                </div>
              </div>

              <div className="mt-5 flex items-center justify-between gap-3 flex-wrap">
                <span className="text-10 uppercase tracking-[0.14em] text-muted-foreground/70 font-semibold">Per-period ({dir})</span>
                <Seg value={period} onChange={setPeriod} ariaLabel="Period granularity" options={[{ v: "yearly", label: "Yearly" }, { v: "monthly", label: "Monthly" }]} />
              </div>
              <div className="mt-2.5 max-h-64 overflow-y-auto rounded-lg border border-border">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-card/95 backdrop-blur">
                    <tr className="text-10 uppercase tracking-wide text-muted-foreground/70">
                      {[{ label: "Period" }, { label: "Jeetne wale", tip: STAT.win.tip }, { label: "Har trade avg", tip: STAT.avg.tip }, { label: "Profit ratio", tip: STAT.pf.tip }, { label: "Sabse bada gir", tip: STAT.dd.tip }, { label: "Kitne trades", tip: STAT.trades.tip }].map((h) => (
                        <th key={h.label} className="text-right first:text-left px-3 py-2 font-semibold">
                          {h.tip ? (
                            <InfoTip content={h.tip}>
                              <span className="underline decoration-dotted decoration-muted-foreground/40 underline-offset-2">{h.label}</span>
                            </InfoTip>
                          ) : (
                            h.label
                          )}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="font-mono tabular-nums">
                    {periods.length === 0 && (
                      <tr>
                        <td colSpan={6} className="px-3 py-3 text-center text-muted-foreground">Loading…</td>
                      </tr>
                    )}
                    {periods.map(([key, blk]) => {
                      const m = blk[dir];
                      return (
                        <tr key={key} className="border-t border-border/60">
                          <td className="text-left px-3 py-1.5 text-foreground">{key}</td>
                          <td className="text-right px-3 py-1.5">{fmt.pct1(m.win_rate_pct)}</td>
                          <td className="text-right px-3 py-1.5 text-profit/90">{fmt.signed(m.avg_pct_per_trade)}</td>
                          <td className="text-right px-3 py-1.5">{fmt.pf(m.profit_factor)}</td>
                          <td className="text-right px-3 py-1.5 text-loss/90">{fmt.dd(m.max_drawdown_pct)}</td>
                          <td className="text-right px-3 py-1.5 text-muted-foreground">{fmt.num(m.trades)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}

          <p className="mt-3 text-11 text-muted-foreground/70 leading-relaxed border-t border-border/60 pt-3">
            NET of estimated Indian F&amp;O charges; <b className="text-muted-foreground">slippage excluded (best-case)</b>. In-sample, single-symbol, no walk-forward — past results don&apos;t predict live performance. Fixed-size, non-compounded basis (differs from TradingView&apos;s compounded figures). Compounded/cumulative totals deliberately not shown.
          </p>
        </div>
        )}
      </GlassmorphismCard>
      </div>
    </TooltipProvider>
  );
}
