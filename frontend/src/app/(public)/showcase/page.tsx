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

import { GlassmorphismCard } from "@/shared/ui/glassmorphism-card";
import { cn } from "@/shared/lib/utils";
import { useApi } from "@/shared/api/use-api";
import { useStrategyCardData } from "@/hooks/useShowcase";
import { StrategyCard } from "@/components/strategy/strategy-card";
import type { ShowcaseListItem, ShowcaseListResponse } from "@/lib/showcase/data";
import { publicCopy } from "@/lib/i18n/copy/public";
import { useCopy } from "@/lib/i18n/core";

function ShowcaseStrategy({ item }: { item: ShowcaseListItem }) {
  const feed = useStrategyCardData(item.key);
  return <StrategyCard item={item} detail={feed.detail} live={feed.live} surface="public" layout="full" />;
}

export default function ShowcasePage() {
  const { data, isLoading, error } = useApi<ShowcaseListResponse>("/showcase");
  const strategies = data?.strategies ?? [];
  const { c } = useCopy(publicCopy);

  return (
    <div className="dark bg-background text-foreground min-h-screen">
      <div className="max-w-5xl mx-auto px-6 pt-24 pb-16">
        {/* HERO — thesis = verifiability, not a big number */}
        <section className="text-center pt-6 pb-2">
          <div className="text-xs tracking-[0.32em] uppercase text-muted-foreground font-semibold mb-5">
            {c.sc_eyebrow}
          </div>
          <h1 className="text-5xl md:text-6xl font-black tracking-tight leading-[1.02]">
            {c.sc_h1_a}<br />
            <span className="bg-gradient-to-r from-profit to-brand-mint bg-clip-text text-transparent">{c.sc_h1_b}</span>
          </h1>
          <p className="mt-5 max-w-xl mx-auto text-muted-foreground text-lg leading-relaxed">
            {c.sc_lead_1}<b className="text-foreground">{c.sc_lead_b1}</b>{c.sc_lead_2}<b className="text-foreground">{c.sc_lead_b2}</b>{c.sc_lead_3}<b className="text-foreground">{c.sc_lead_b3}</b>{c.sc_lead_4}
          </p>
        </section>

        {/* LEDGER — shown as the MECHANISM + honest current state (no fake feed) */}
        <GlassmorphismCard hover={false} className="mt-10 p-0 overflow-hidden">
          <div className="flex items-center justify-between gap-3 flex-wrap px-5 py-4 border-b border-border/60 bg-accent-gold/[0.04]">
            <div className="flex items-center gap-2.5 text-13 font-bold tracking-wide">
              <span className="grid place-items-center h-6 w-6 rounded-full border border-accent-gold text-accent-gold text-xs">✓</span>
              {c.sc_ledger_h}
            </div>
            <span className="text-xs text-muted-foreground">{c.sc_ledger_state}</span>
          </div>
          <div className="grid md:grid-cols-3 gap-px bg-border/40">
            {[
              { ic: "①", t: c.sc_l1_t, d: c.sc_l1_d },
              { ic: "②", t: c.sc_l2_t, d: c.sc_l2_d },
              { ic: "③", t: c.sc_l3_t, d: c.sc_l3_d },
            ].map((s) => (
              <div key={s.t} className="bg-card/60 p-5">
                <div className="text-accent-gold font-mono text-lg">{s.ic}</div>
                <h3 className="text-sm font-semibold mt-1.5">{s.t}</h3>
                <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{s.d}</p>
              </div>
            ))}
          </div>
          <div className="px-5 py-3 text-xs text-muted-foreground/70 text-center bg-white/[0.012]">
            <b className="text-muted-foreground">{c.sc_ledger_foot_b}</b>{c.sc_ledger_foot}
          </div>
        </GlassmorphismCard>

        {/* STRATEGIES — the same card the app shows */}
        <section className="pt-16" data-testid="showcase-strategies">
          <div className="text-xs tracking-[0.28em] uppercase text-profit font-bold">{c.sc_strat_eyebrow}</div>
          <h2 className="text-3xl font-extrabold tracking-tight mt-2.5">{c.sc_strat_h2}</h2>
          <p className="text-muted-foreground mt-2 text-15 max-w-xl">{c.sc_strat_p}</p>

          <div className="flex flex-col gap-4 mt-7">
            {isLoading && <p className="text-center text-sm text-muted-foreground py-8">{c.sc_loading}</p>}
            {error && (
              <p className="text-center text-sm text-loss py-8">
                {c.sc_error_a} {error} {c.sc_error_b}
              </p>
            )}
            {strategies.map((s) => (
              <ShowcaseStrategy key={s.key} item={s} />
            ))}
          </div>
        </section>

        {/* HOW IT WORKS */}
        <section className="pt-16">
          <div className="text-xs tracking-[0.28em] uppercase text-profit font-bold">{c.sc_how_eyebrow}</div>
          <h2 className="text-3xl font-extrabold tracking-tight mt-2.5">{c.sc_how_h2}</h2>
          <div className="grid md:grid-cols-3 gap-4 mt-7">
            {[
              { Icon: FlaskConical, tone: "text-profit", bg: "bg-profit/10", t: c.sc_h1_t, d: c.sc_h1_d },
              { Icon: Building2, tone: "text-accent-blue", bg: "bg-accent-blue/10", t: c.sc_h2_t, d: c.sc_h2_d },
              { Icon: ShieldCheck, tone: "text-accent-gold", bg: "bg-accent-gold/10", t: c.sc_h3_t, d: c.sc_h3_d },
            ].map(({ Icon, tone, bg, t, d }) => (
              <GlassmorphismCard key={t} hover={false} className="p-5">
                <div className={cn("h-9 w-9 rounded-lg grid place-items-center mb-3.5", bg, tone)}><Icon className="h-4 w-4" /></div>
                <h3 className="text-sm font-bold">{t}</h3>
                <p className="text-13 text-muted-foreground mt-1.5 leading-relaxed">{d}</p>
              </GlassmorphismCard>
            ))}
          </div>
        </section>

        {/* DISCLAIMER */}
        <GlassmorphismCard hover={false} className="mt-14">
          <h4 className="flex items-center gap-1.5 text-xs tracking-[0.16em] uppercase text-muted-foreground font-bold mb-3">
            <Lock className="h-3.5 w-3.5" /> {c.sc_disc_h}
          </h4>
          <div className="space-y-2.5 text-xs text-muted-foreground/80 leading-relaxed">
            <p><b className="text-muted-foreground">{c.sc_disc_1_b}</b>{c.sc_disc_1}</p>
            <p><b className="text-muted-foreground">{c.sc_disc_2_b}</b>{c.sc_disc_2_a}<b className="text-muted-foreground">{c.sc_disc_2_b2}</b>{c.sc_disc_2_c}<b className="text-muted-foreground">{c.sc_disc_2_b3}</b></p>
            <p>{c.sc_disc_3_a}<b className="text-muted-foreground">{c.sc_disc_3_b}</b>{c.sc_disc_3_c}</p>
          </div>
        </GlassmorphismCard>

        <footer className="text-center text-xs text-muted-foreground/60 pt-10">
          {c.sc_footer}{" "}
          <Link href="/pricing" className="text-accent-blue hover:underline">{c.sc_footer_pricing}</Link>
        </footer>
      </div>
    </div>
  );
}
