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
            Har trade ka khula hisaab
          </div>
          <h1 className="text-5xl md:text-6xl font-black tracking-tight leading-[1.02]">
            Vaade nahi.<br />
            <span className="bg-gradient-to-r from-profit to-brand-mint bg-clip-text text-transparent">Proof.</span>
          </h1>
          <p className="mt-5 max-w-xl mx-auto text-muted-foreground text-lg leading-relaxed">
            Har asli trade aapke broker ke <b className="text-foreground">asli order</b> se juda hota hai. Jaise-jaise
            pakka record banta hai, har hisaab ka panna ek <b className="text-foreground">digital seal (hash)</b> se band hoga jo
            pichhle panne se bhi juda rahega (pichhle snapshot ke hash se link) — koi purana panna chupke se badle to seal
            toot jaata hai (tamper-evident). Yeh hisaab{" "}
            <b className="text-foreground">hamare apne database</b> me hai (off-chain — kisi blockchain par nahi), aur pehla panna
            banne tak khaali hai. Login kiye subscriber strategy ke hisaab panel se seal khud check kar sakte hain.
          </p>
        </section>

        {/* LEDGER — shown as the MECHANISM + honest current state (no fake feed) */}
        <GlassmorphismCard hover={false} className="mt-10 p-0 overflow-hidden">
          <div className="flex items-center justify-between gap-3 flex-wrap px-5 py-4 border-b border-border/60 bg-accent-gold/[0.04]">
            <div className="flex items-center gap-2.5 text-13 font-bold tracking-wide">
              <span className="grid place-items-center h-6 w-6 rounded-full border border-accent-gold text-accent-gold text-xs">✓</span>
              Hisaab kaise pakka hota hai
            </div>
            <span className="text-xs text-muted-foreground">Hamare database me, seal se jude panne · abhi koi panna nahi (no snapshots yet)</span>
          </div>
          <div className="grid md:grid-cols-3 gap-px bg-border/40">
            {[
              { ic: "①", t: "Asli order", d: "Har live trade aapke apne broker se jaata hai — har bhare order ke saath uska asli broker order number hota hai." },
              { ic: "②", t: "Seal lage panne", d: "Band hue trades ke har panne par ek digital seal (SHA-256 hash) lagti hai jo pichhle panne ko bhi dhakti hai — koi purana panna chupke se nahi badal sakta. Yeh hamare apne database me hai; koi blockchain nahi." },
              { ic: "③", t: "Aap khud jaancho", d: "Login kiye subscriber strategy ke hisaab panel se seal dobara check kar sakte hain. Purana panna badla to seal toot jaati hai aur jaanch fail — khud-jaanchne wala record, kisi bahar wale ki mohar nahi." },
            ].map((s) => (
              <div key={s.t} className="bg-card/60 p-5">
                <div className="text-accent-gold font-mono text-lg">{s.ic}</div>
                <h3 className="text-sm font-semibold mt-1.5">{s.t}</h3>
                <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{s.d}</p>
              </div>
            ))}
          </div>
          <div className="px-5 py-3 text-xs text-muted-foreground/70 text-center bg-white/[0.012]">
            <b className="text-muted-foreground">Abhi koi panna publish nahi hua (no ledger snapshots yet).</b> Yeh hisaab
            tabhi bharta hai jab asli trade band hote hain aur panna banta hai. Koi banaya hua record nahi, koi namoona seal (sample hash) nahi.
          </div>
        </GlassmorphismCard>

        {/* STRATEGIES — the same card the app shows */}
        <section className="pt-16" data-testid="showcase-strategies">
          <div className="text-xs tracking-[0.28em] uppercase text-profit font-bold">Strategies</div>
          <h2 className="text-3xl font-extrabold tracking-tight mt-2.5">Pehle asli record (abhi jaanch me). Purane data wala test sirf sandarbh ke liye.</h2>
          <p className="text-muted-foreground mt-2 text-15 max-w-xl">
            Har strategy ka live record build hote hi yahan publish hoga — risk ko return jitni hi
            prominence di jaati hai, koi cherry-picking nahi. Jodna hai? App mein — yahan sirf dekho.
          </p>

          <div className="flex flex-col gap-4 mt-7">
            {isLoading && <p className="text-center text-sm text-muted-foreground py-8">Strategies load ho rahi hain…</p>}
            {error && (
              <p className="text-center text-sm text-loss py-8">
                Showcase abhi load nahi hua. {error} Thodi der baad page dobara kholo.
              </p>
            )}
            {strategies.map((s) => (
              <ShowcaseStrategy key={s.key} item={s} />
            ))}
          </div>
        </section>

        {/* HOW IT WORKS */}
        <section className="pt-16">
          <div className="text-xs tracking-[0.28em] uppercase text-profit font-bold">Kaise chalta hai</div>
          <h2 className="text-3xl font-extrabold tracking-tight mt-2.5">Kaabu aapke haath me.</h2>
          <div className="grid md:grid-cols-3 gap-4 mt-7">
            {[
              { Icon: FlaskConical, c: "text-profit", bg: "bg-profit/10", t: "Pehle nakli paise se (paper)", d: "Koi bhi strategy pehle nakli paise me, live bazaar data ke saath try karo — ek rupaya lagane se pehle. Asli tab, jab aap taiyar ho." },
              { Icon: Building2, c: "text-accent-blue", bg: "bg-accent-blue/10", t: "Aapka paisa, aapka broker", d: "Trade aapke apne broker account me chalte hain — hum signal bhejte hain, order aapke jude broker se jaata hai. Aapka paisa hum kabhi nahi rakhte." },
              { Icon: ShieldCheck, c: "text-accent-gold", bg: "bg-accent-gold/10", t: "Har signal, saaf dikhega", d: "Har entry aur exit uske daam, stop aur target ke saath dikhti hai. Jodi hui strategy pehle haath-se (manual) mode me chalti hai — har signal par aap haan bolte ho. Strategy ke andar ke niyam banane wale ke paas rehte hain." },
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
            <Lock className="h-3.5 w-3.5" /> Zaroori — padh lo
          </h4>
          <div className="space-y-2.5 text-xs text-muted-foreground/80 leading-relaxed">
            <p><b className="text-muted-foreground">Shares aur futures/options (F&amp;O) me trading me nuksaan ka bada risk hai</b> aur yeh har kisi ke liye theek nahi. 90% se zyada retail F&amp;O trader paisa khote hain. Sirf utna lagao jitna khone ki haisiyat ho.</p>
            <p><b className="text-muted-foreground">Purane bazaar data par test (backtest / hypothetical) ke nateejon ki asli seemaayein hain</b> — peechhe mud kar dekh kar banaye, bina asli paisa lagaye, aur aksar asli se bahut alag. Aankde andaazan charges ke baad hain, par <b className="text-muted-foreground">maante hain ki har order test ke daam par bhara (slippage excluded — isliye yeh best-case hain)</b>, sirf usi data par jaanche gaye jis par strategy bani (in-sample, no walk-forward), aur har trade ek hi size ka maana (fixed-size, non-compounded — TradingView ke compounded aankdon se alag). <b className="text-muted-foreground">Pichhla pradarshan aage ke nateeje ki guarantee nahi deta.</b></p>
            <p>TRADETRI <b className="text-muted-foreground">aapko har signal aur har bhara order dikhata hai</b>. Strategy ke andar ke niyam banane wale ke paas rehte hain. Pakke return ka koi daawa nahi — na seedha, na ishaare me. Strategy aapke exchange-registered broker se, SEBI ke algo-trading niyamon ke anusaar chalti hai.</p>
          </div>
        </GlassmorphismCard>

        <footer className="text-center text-xs text-muted-foreground/60 pt-10">
          TRADETRI · Sab kuch saaf dikhane par bana — &ldquo;Proof, vaade nahi.&rdquo;{" "}
          <Link href="/pricing" className="text-accent-blue hover:underline">Daam dekho</Link>
        </footer>
      </div>
    </div>
  );
}
