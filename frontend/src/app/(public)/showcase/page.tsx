"use client";

/**
 * TRADETRI public Track Record ("Proof") — live at /showcase.
 *
 * The strategy cards here are THE SAME component the app renders in its
 * Marketplace and on listing detail (components/strategy/strategy-card.tsx),
 * fed by the same hook (hooks/useShowcase.ts) from the read-only Module 2 API
 * (NET basis):  GET /api/showcase · /api/showcase/{key} · /api/showcase/{key}/live
 *
 * Public = shop window: the card is read-only with ONE call to action —
 * logged out → Start Free (register, then straight back to this strategy);
 * logged in → "App mein kholo" (the in-app strategy detail, where Subscribe lives).
 *
 * HONESTY: shows ONLY what the API returns. No fabricated live trades, no fake
 * ledger rows, and NO blockchain claim: the ledger is off-chain (our Postgres)
 * and hash-linked — each snapshot stores the previous snapshot's hash — and it
 * is EMPTY until the first snapshot, so the Ledger card shows the MECHANISM
 * plus the honest "tracking active" state.
 */
import Link from "next/link";
import { ShieldCheck, Lock, Building2, FlaskConical } from "lucide-react";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { cn } from "@/lib/utils";
import { useApi } from "@/lib/use-api";
import { useStrategyCardData } from "@/hooks/useShowcase";
import { StrategyCard } from "@/components/strategy/strategy-card";
import type { ShowcaseListItem, ShowcaseListResponse } from "@/lib/showcase/data";

function ShowcaseStrategy({ item }: { item: ShowcaseListItem }) {
  const feed = useStrategyCardData(item.key);
  return <StrategyCard item={item} detail={feed.detail} live={feed.live} surface="public" layout="full" />;
}

export default function ShowcasePage() {
  const { data, isLoading, error } = useApi<ShowcaseListResponse>("/showcase");
  const strategies = data?.strategies ?? [];

  return (
    <div className="dark bg-background text-foreground min-h-screen">
      <div className="max-w-5xl mx-auto px-6 pt-24 pb-16">
        {/* HERO — thesis = verifiability, not a big number */}
        <section className="text-center pt-6 pb-2">
          <div className="text-xs tracking-[0.32em] uppercase text-muted-foreground font-semibold mb-5">
            Strategy Transparency Ledger
          </div>
          <h1 className="text-5xl md:text-6xl font-black tracking-tight leading-[1.02]">
            Backtest nahi.<br />
            <span className="bg-gradient-to-r from-profit to-brand-mint bg-clip-text text-transparent">Proof.</span>
          </h1>
          <p className="mt-5 max-w-xl mx-auto text-muted-foreground text-lg leading-relaxed">
            Har live trade apne <b className="text-foreground">real broker order</b> se juda hota hai. Jaise-jaise
            verified record banta hai, har snapshot ek <b className="text-foreground">hash</b> carry karega jo
            pichhle snapshot ke hash se link hota hai — ek append-only, tamper-evident record. Yeh ledger abhi{" "}
            <b className="text-foreground">off-chain</b> hai (hamare database mein, kisi blockchain pe nahi), aur
            pehle snapshot tak khaali hai. Logged-in subscribers strategy ke ledger panel se chain khud verify kar sakte hain.
          </p>
        </section>

        {/* LEDGER — shown as the MECHANISM + honest current state (no fake feed) */}
        <GlassmorphismCard hover={false} className="mt-10 p-0 overflow-hidden">
          <div className="flex items-center justify-between gap-3 flex-wrap px-5 py-4 border-b border-border/60 bg-accent-gold/[0.04]">
            <div className="flex items-center gap-2.5 text-13 font-bold tracking-wide">
              <span className="grid place-items-center h-6 w-6 rounded-full border border-accent-gold text-accent-gold text-xs">✓</span>
              Verified Ledger — how it works
            </div>
            <span className="text-11 text-muted-foreground">Off-chain, hash-linked record · no snapshots yet</span>
          </div>
          <div className="grid md:grid-cols-3 gap-px bg-border/40">
            {[
              { ic: "①", t: "Real order", d: "Every live trade routes through your own broker — each fill carries its real broker order ID." },
              { ic: "②", t: "Hash chain", d: "Each snapshot of reconciled trades is hashed (SHA-256) and stores the previous snapshot's hash — an append-only, tamper-evident chain in our own database. Off-chain: there is no blockchain." },
              { ic: "③", t: "You verify", d: "Logged-in subscribers can re-run the chain check from the strategy's ledger panel. Editing any past snapshot breaks the hash link and verification fails — a self-checking record, not third-party notarised." },
            ].map((s) => (
              <div key={s.t} className="bg-card/60 p-5">
                <div className="text-accent-gold font-mono text-lg">{s.ic}</div>
                <h3 className="text-sm font-semibold mt-1.5">{s.t}</h3>
                <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{s.d}</p>
              </div>
            ))}
          </div>
          <div className="px-5 py-3 text-11 text-muted-foreground/70 text-center bg-white/[0.012]">
            <b className="text-muted-foreground">No ledger snapshots have been published yet.</b> This ledger
            fills in only as real trades settle and snapshots are taken. No fabricated entries, no sample hashes.
          </div>
        </GlassmorphismCard>

        {/* STRATEGIES — the same card the app shows */}
        <section className="pt-16" data-testid="showcase-strategies">
          <div className="text-xs tracking-[0.28em] uppercase text-profit font-bold">Strategies</div>
          <h2 className="text-3xl font-extrabold tracking-tight mt-2.5">Live record first — in verification. Backtest as context.</h2>
          <p className="text-muted-foreground mt-2 text-15 max-w-xl">
            Har strategy ka live record build hote hi yahan publish hoga — risk ko return jitni hi
            prominence di jaati hai, koi cherry-picking nahi. Jodna hai? App mein — yahan sirf dekho.
          </p>

          <div className="flex flex-col gap-4 mt-7">
            {isLoading && <p className="text-center text-sm text-muted-foreground py-8">Loading strategies…</p>}
            {error && (
              <p className="text-center text-sm text-loss py-8">
                Couldn&apos;t load the showcase — is the backend running? ({error})
              </p>
            )}
            {strategies.map((s) => (
              <ShowcaseStrategy key={s.key} item={s} />
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
              { Icon: ShieldCheck, c: "text-accent-gold", bg: "bg-accent-gold/10", t: "Every signal, shown", d: "You see each entry and exit with its price, stop and target. Subscriptions start in manual mode — you confirm each one. The strategy's internal rules stay with the creator." },
            ].map(({ Icon, c, bg, t, d }) => (
              <GlassmorphismCard key={t} hover={false} className="p-5">
                <div className={cn("h-9 w-9 rounded-lg grid place-items-center mb-3.5", bg, c)}><Icon className="h-4 w-4" /></div>
                <h3 className="text-sm font-bold">{t}</h3>
                <p className="text-13 text-muted-foreground mt-1.5 leading-relaxed">{d}</p>
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
            <p>TRADETRI <b className="text-muted-foreground">shows you every signal and every fill</b>. Strategy internals stay with the creator. No guaranteed returns are claimed or implied. Strategies are routed through your exchange-registered broker in line with SEBI&apos;s algorithmic-trading framework.</p>
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
