"use client";

/**
 * TRADETRI Strategy Showcase (DRAFT — for review, not deployed).
 *
 * Rebuild of the approved demo as a real Next.js page on existing brand tokens
 * + GlassmorphismCard. Consumes the read-only Module 2 API (NET basis):
 *   GET /api/showcase · /api/showcase/{key} · /api/showcase/{key}/live
 *
 * HONESTY: shows ONLY what the API returns. No fabricated live trades, no fake
 * on-chain hashes/ledger rows (the chain isn't built — the Ledger is shown as
 * the verification MECHANISM + the honest "tracking active" state). No
 * compounded totals, no cumulative-return curve, no rupee P&L. Drawdown is the
 * negative value the API now returns. Risk is as prominent as return.
 */
import { useState } from "react";
import Link from "next/link";
import { ShieldCheck, Lock, Building2, FlaskConical } from "lucide-react";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { EquityCurve } from "@/components/charts/equity-curve";
import { cn } from "@/lib/utils";
import { useApi } from "@/lib/use-api";
import {
  BADGE,
  type Direction,
  type LiveRecord,
  type Metrics,
  type ShowcaseDetail,
  type ShowcaseListItem,
  type ShowcaseListResponse,
} from "@/lib/showcase/data";

// ── formatters ──────────────────────────────────────────────────────────
const f1 = (v: number) => `${v.toFixed(1)}%`;
const fSigned = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
const fDD = (v: number) => `${v.toFixed(2)}%`; // already negative
const fPF = (v: number | null) => (v == null ? "∞" : v.toFixed(2));
const fNum = (v: number) => v.toLocaleString("en-IN");

// ── segmented toggle (keyboard-focusable) ───────────────────────────────
function Seg<T extends string>({
  value,
  options,
  onChange,
  ariaLabel,
}: {
  value: T;
  options: { v: T; label: string }[];
  onChange: (v: T) => void;
  ariaLabel: string;
}) {
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

function Stat({ value, label, tone }: { value: string; label: string; tone?: string }) {
  return (
    <div>
      <div className={cn("text-lg font-bold font-mono tabular-nums tracking-tight", tone ?? "text-[#C7D0DE]")}>{value}</div>
      <div className="text-[10.5px] text-muted-foreground/70 mt-0.5">{label}</div>
    </div>
  );
}

// ── one strategy card ───────────────────────────────────────────────────
function StrategyCard({ item }: { item: ShowcaseListItem }) {
  const [dir, setDir] = useState<Direction>("all");
  const [period, setPeriod] = useState<"yearly" | "monthly">("yearly");
  const { data: detail } = useApi<ShowcaseDetail>(`/showcase/${item.key}`);
  const { data: live } = useApi<LiveRecord>(`/showcase/${item.key}/live`);

  const badge = BADGE[item.live_status.track_type];
  const agg: Metrics =
    detail?.backtest.aggregate[dir] ??
    ({ ...item.headline_net } as Metrics); // headline = NET 'all' until detail loads
  const periods = detail
    ? Object.entries(period === "yearly" ? detail.backtest.by_year : detail.backtest.by_month)
    : [];
  const sliceCaveat = dir !== "all" ? (agg.caveat ?? detail?.meta.slice_caveat) : null;

  // non-compounded cumulative-edge curve for the active direction (API M3.5).
  // {d,v} -> {time,value}; v is cumulative NET percentage-points, NOT rupees.
  const equityPoints =
    detail?.backtest.series?.[dir]?.equity_curve_noncompounded.map((p) => ({
      time: p.d,
      value: p.v,
    })) ?? [];

  // honest live line from /live
  const liveLine = (() => {
    if (!live) return { em: "Loading live record…", sub: "" };
    if (live.status === "paper_no_live")
      return { em: "Backtest-only candidate.", sub: "No real-money results exist. In paper evaluation; promoted to live only after forward-testing." };
    if (live.reconciled_trades > 0)
      return { em: `${live.reconciled_trades} live trade(s) reconciled.`, sub: "Verified per-trade results pending publication — no P&L shown until reviewed." };
    return { em: "Live tracking active.", sub: "Verified trades publish as they accumulate — nothing recorded yet. No estimates, no padding." };
  })();

  return (
    <GlassmorphismCard hover={false} className="p-0 overflow-hidden">
      {/* header */}
      <div className="flex items-start justify-between gap-4 flex-wrap p-6 pb-0">
        <div>
          <h3 className="text-lg font-bold tracking-tight">{item.name}</h3>
          <p className="text-xs text-muted-foreground/70 mt-0.5">{item.instrument} · NSE F&amp;O · NRML</p>
        </div>
        <span className={cn("inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11.5px] font-semibold", badge.cls)}>
          <span className={cn("h-1.5 w-1.5 rounded-full", badge.dot)} />
          {item.live_status.label}
        </span>
      </div>

      {/* primary: live record + risk (the prominent, honest part) */}
      <div className="grid md:grid-cols-[1.4fr_1fr] gap-3.5 p-6 pt-5">
        <div className="rounded-xl border border-border bg-white/[0.018] p-4">
          <div className="flex items-center gap-2 text-[10.5px] uppercase tracking-[0.14em] text-muted-foreground/70 font-semibold">
            Verified live record
            <span className="text-accent-gold text-[9.5px] border border-accent-gold/30 rounded px-1.5 py-px">◆ ledger</span>
          </div>
          <p className="mt-2.5 text-sm leading-relaxed">
            <span className="text-profit font-semibold">{liveLine.em}</span>
          </p>
          {liveLine.sub && <p className="mt-1.5 text-xs text-muted-foreground">{liveLine.sub}</p>}
        </div>
        <div className="rounded-xl border border-border bg-white/[0.018] p-4">
          <div className="text-[10.5px] uppercase tracking-[0.14em] text-muted-foreground/70 font-semibold">Risk · Max drawdown</div>
          <div className="mt-2 text-3xl font-bold font-mono tabular-nums tracking-tight text-loss">{fDD(agg.max_drawdown_pct)}</div>
          <div className="text-[11.5px] text-muted-foreground mt-1">Worst peak-to-trough — non-compounded, in-sample</div>
        </div>
      </div>

      {/* backtest = subordinate, clearly hypothetical */}
      <div className="m-6 mt-0 rounded-xl border border-dashed border-muted-foreground/25 bg-muted/[0.04] p-4">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">
            In-sample backtest{detail ? ` · ${detail.backtest.in_sample_range.from} → ${detail.backtest.in_sample_range.to}` : ""}
            <span className="text-[9.5px] tracking-normal bg-muted/40 text-muted-foreground px-1.5 py-0.5 rounded border border-border normal-case">
              Hypothetical — not a guarantee
            </span>
          </div>
          <Seg<Direction>
            value={dir}
            onChange={setDir}
            ariaLabel="Trade direction"
            options={[{ v: "all", label: "All" }, { v: "long", label: "Long" }, { v: "short", label: "Short" }]}
          />
        </div>

        {/* current-direction headline stats */}
        <div className="grid grid-cols-3 sm:grid-cols-5 gap-2.5 mt-4">
          <Stat value={f1(agg.win_rate_pct)} label="Win rate" tone="text-accent-blue" />
          <Stat value={fSigned(agg.avg_pct_per_trade)} label="Avg net / trade" tone="text-profit" />
          <Stat value={fPF(agg.profit_factor)} label="Profit factor" tone="text-accent-gold" />
          <Stat value={fDD(agg.max_drawdown_pct)} label="Max drawdown" tone="text-loss" />
          <Stat value={fNum(agg.trades)} label="Trades (sample)" />
        </div>

        {sliceCaveat && (
          <p className="mt-3 text-[11px] text-accent-gold/90 bg-accent-gold/[0.06] border border-accent-gold/20 rounded-md px-2.5 py-1.5 flex gap-1.5">
            <span aria-hidden>⚠</span> {sliceCaveat}
          </p>
        )}

        {/* cumulative-edge chart (non-compounded) — follows the direction toggle */}
        <div className="mt-5">
          <div className="flex items-baseline justify-between gap-2 flex-wrap">
            <span className="text-[10.5px] uppercase tracking-[0.14em] text-muted-foreground/70 font-semibold">
              Cumulative edge ({dir})
            </span>
            <span className="text-[10px] text-muted-foreground/60">Non-compounded · NET %</span>
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground/70 leading-snug">
            Cumulative edge — fixed-size, non-compounded (NOT a compounded return). Each point is the
            running sum of per-trade NET&nbsp;% at its exit date.
          </p>
          {!detail ? (
            <div className="mt-2 h-[200px] grid place-items-center text-xs text-muted-foreground">
              Loading chart…
            </div>
          ) : equityPoints.length === 0 ? (
            <div className="mt-2 h-[200px] grid place-items-center text-xs text-muted-foreground">
              No {dir} trades to chart.
            </div>
          ) : (
            <div className="mt-2">
              <EquityCurve data={equityPoints} unit="pct" valueLabel="Cumulative net %" />
            </div>
          )}
        </div>

        {/* per-period table */}
        <div className="mt-5 flex items-center justify-between gap-3 flex-wrap">
          <span className="text-[10.5px] uppercase tracking-[0.14em] text-muted-foreground/70 font-semibold">
            Per-period ({dir})
          </span>
          <Seg
            value={period}
            onChange={setPeriod}
            ariaLabel="Period granularity"
            options={[{ v: "yearly", label: "Yearly" }, { v: "monthly", label: "Monthly" }]}
          />
        </div>
        <div className="mt-2.5 max-h-64 overflow-y-auto rounded-lg border border-border">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-card/95 backdrop-blur">
              <tr className="text-[10px] uppercase tracking-wide text-muted-foreground/70">
                {["Period", "Win", "Avg/tr", "PF", "Max DD", "Trades"].map((h) => (
                  <th key={h} className="text-right first:text-left px-3 py-2 font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="font-mono tabular-nums">
              {periods.length === 0 && (
                <tr><td colSpan={6} className="px-3 py-3 text-center text-muted-foreground">Loading…</td></tr>
              )}
              {periods.map(([key, blk]) => {
                const m = blk[dir];
                return (
                  <tr key={key} className="border-t border-border/60">
                    <td className="text-left px-3 py-1.5 text-foreground">{key}</td>
                    <td className="text-right px-3 py-1.5">{f1(m.win_rate_pct)}</td>
                    <td className="text-right px-3 py-1.5 text-profit/90">{fSigned(m.avg_pct_per_trade)}</td>
                    <td className="text-right px-3 py-1.5">{fPF(m.profit_factor)}</td>
                    <td className="text-right px-3 py-1.5 text-loss/90">{fDD(m.max_drawdown_pct)}</td>
                    <td className="text-right px-3 py-1.5 text-muted-foreground">{fNum(m.trades)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <p className="mt-3 text-[11px] text-muted-foreground/70 leading-relaxed border-t border-border/60 pt-3">
          NET of estimated Indian F&amp;O charges; <b className="text-muted-foreground">slippage excluded (best-case)</b>.
          In-sample, single-symbol, no walk-forward — past results don&apos;t predict live performance.
          Fixed-size, non-compounded basis (differs from TradingView&apos;s compounded figures). Compounded/cumulative totals deliberately not shown.
        </p>
      </div>
    </GlassmorphismCard>
  );
}

export default function ShowcasePage() {
  const { data, isLoading, error } = useApi<ShowcaseListResponse>("/showcase");
  const strategies = data?.strategies ?? [];

  return (
    <div className="dark bg-background text-foreground min-h-screen">
      <div className="max-w-5xl mx-auto px-6 pt-24 pb-16">
        {/* DRAFT ribbon */}
        <div className="text-center mb-5">
          <span className="inline-block px-3 py-1 rounded-full bg-accent-gold/10 text-accent-gold text-xs font-semibold border border-accent-gold/25">
            ◆ DRAFT — for review · not the live site
          </span>
        </div>

        {/* HERO — thesis = verifiability, not a big number */}
        <section className="text-center pt-6 pb-2">
          <div className="text-xs tracking-[0.32em] uppercase text-muted-foreground font-semibold mb-5">
            Strategy Transparency Ledger
          </div>
          <h1 className="text-5xl md:text-6xl font-black tracking-tight leading-[1.02]">
            Backtest nahi.<br />
            <span className="bg-gradient-to-r from-profit to-[#9affd0] bg-clip-text text-transparent">Proof.</span>
          </h1>
          <p className="mt-5 max-w-xl mx-auto text-muted-foreground text-[17px] leading-relaxed">
            Har live trade apne <b className="text-foreground">real broker order</b> se juda hota hai. Jaise-jaise
            verified record banta hai, har entry ek <b className="text-foreground">daily, immutable on-chain hash</b> carry
            karegi. Aap record verify karte ho — bharosa nahi karna padta.
          </p>
        </section>

        {/* LEDGER — shown as the MECHANISM + honest current state (no fake feed) */}
        <GlassmorphismCard hover={false} className="mt-10 p-0 overflow-hidden">
          <div className="flex items-center justify-between gap-3 flex-wrap px-5 py-4 border-b border-border/60 bg-accent-gold/[0.04]">
            <div className="flex items-center gap-2.5 text-[13px] font-bold tracking-wide">
              <span className="grid place-items-center h-6 w-6 rounded-full border border-accent-gold text-accent-gold text-xs">✓</span>
              Verified Ledger — how it works
            </div>
            <span className="text-[11.5px] text-muted-foreground">Concept · chain not yet live</span>
          </div>
          <div className="grid md:grid-cols-3 gap-px bg-border/40">
            {[
              { ic: "①", t: "Real order", d: "Every live trade routes through your own broker — each fill carries its real broker order ID." },
              { ic: "②", t: "Daily hash", d: "Reconciled trades get a daily cryptographic hash, anchored on-chain — tamper-proof, append-only." },
              { ic: "③", t: "You verify", d: "Anyone can check the record. We can't quietly delete a losing trade or pad a winner." },
            ].map((s) => (
              <div key={s.t} className="bg-card/60 p-5">
                <div className="text-accent-gold font-mono text-lg">{s.ic}</div>
                <h3 className="text-sm font-semibold mt-1.5">{s.t}</h3>
                <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{s.d}</p>
              </div>
            ))}
          </div>
          <div className="px-5 py-3 text-[11.5px] text-muted-foreground/70 text-center bg-white/[0.012]">
            <b className="text-muted-foreground">Live tracking is active — 0 trades reconciled &amp; published yet.</b> This ledger
            fills in only as real trades settle. No fabricated entries, no sample hashes.
          </div>
        </GlassmorphismCard>

        {/* STRATEGIES */}
        <section className="pt-16">
          <div className="text-xs tracking-[0.28em] uppercase text-profit font-bold">Live Strategies</div>
          <h2 className="text-3xl font-extrabold tracking-tight mt-2.5">Verified record first. Backtest as context.</h2>
          <p className="text-muted-foreground mt-2 text-[15px] max-w-xl">
            Har strategy ka live record build hote hi yahan publish hoga — risk ko return jitni hi
            prominence di jaati hai, koi cherry-picking nahi.
          </p>

          <div className="flex flex-col gap-4 mt-7">
            {isLoading && <p className="text-center text-sm text-muted-foreground py-8">Loading strategies…</p>}
            {error && (
              <p className="text-center text-sm text-loss py-8">
                Couldn&apos;t load the showcase — is the backend running? ({error})
              </p>
            )}
            {strategies.map((s) => (
              <StrategyCard key={s.key} item={s} />
            ))}
          </div>
        </section>

        {/* HOW IT WORKS */}
        <section className="pt-16">
          <div className="text-xs tracking-[0.28em] uppercase text-profit font-bold">How it works</div>
          <h2 className="text-3xl font-extrabold tracking-tight mt-2.5">You stay in control.</h2>
          <div className="grid md:grid-cols-3 gap-4 mt-7">
            {[
              { Icon: FlaskConical, c: "text-profit", bg: "bg-profit/10", t: "Paper-trade first", d: "Try any strategy in simulation with live market data before risking a rupee. Go live only when you're comfortable." },
              { Icon: Building2, c: "text-accent-blue", bg: "bg-accent-blue/10", t: "Your money, your broker", d: "Trades run in your own broker account — we send the signal and execute via your linked broker. We never hold your funds." },
              { Icon: ShieldCheck, c: "text-accent-gold", bg: "bg-accent-gold/10", t: "White-box logic", d: "Strategy rules are transparent and replicable — no black box. Every live result is verifiable on the Ledger." },
            ].map(({ Icon, c, bg, t, d }) => (
              <GlassmorphismCard key={t} hover={false} className="p-5">
                <div className={cn("h-9 w-9 rounded-lg grid place-items-center mb-3.5", bg, c)}><Icon className="h-4 w-4" /></div>
                <h3 className="text-sm font-bold">{t}</h3>
                <p className="text-[13px] text-muted-foreground mt-1.5 leading-relaxed">{d}</p>
              </GlassmorphismCard>
            ))}
          </div>
        </section>

        {/* DISCLAIMER */}
        <GlassmorphismCard hover={false} className="mt-14">
          <h4 className="flex items-center gap-1.5 text-xs tracking-[0.16em] uppercase text-muted-foreground font-bold mb-3">
            <Lock className="h-3.5 w-3.5" /> Important — please read
          </h4>
          <div className="space-y-2.5 text-xs text-muted-foreground/80 leading-relaxed">
            <p><b className="text-muted-foreground">Trading in securities and derivatives carries a high risk of loss</b> and may not be suitable for all investors. Over 90% of retail F&amp;O traders lose money. Only trade with capital you can afford to lose.</p>
            <p><b className="text-muted-foreground">Backtest / hypothetical results have inherent limitations</b> — prepared with hindsight, involve no real risk, and frequently differ sharply from actual results. Figures shown are net of estimated charges but <b className="text-muted-foreground">exclude slippage (so they are best-case)</b>, are in-sample with no walk-forward, and use a fixed-size, non-compounded basis that differs from TradingView&apos;s compounded figures. <b className="text-muted-foreground">Past performance is not indicative of future results.</b></p>
            <p>TRADETRI offers <b className="text-muted-foreground">white-box (fully transparent) strategies only</b>. No guaranteed returns are claimed or implied. Strategies are routed through your exchange-registered broker in line with SEBI&apos;s algorithmic-trading framework.</p>
          </div>
        </GlassmorphismCard>

        <footer className="text-center text-xs text-muted-foreground/60 pt-10">
          TRADETRI · Built on radical transparency — &ldquo;Proof, not promises.&rdquo;{" "}
          <Link href="/pricing" className="text-accent-blue hover:underline">See pricing</Link>
        </footer>
      </div>
    </div>
  );
}
