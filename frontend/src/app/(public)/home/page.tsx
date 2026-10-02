"use client";

import { useRef } from "react";
import { motion, useInView } from "framer-motion";
import {
  Eye,
  EyeOff,
  Wallet,
  Code2,
  Landmark,
  Languages,
  ShieldAlert,
  ShieldCheck,
  Bot,
  BarChart3,
  Lock,
  ArrowRight,
} from "lucide-react";
import { AnimatedNumber } from "@/shared/ui/animated-number";
import { GlassmorphismCard } from "@/shared/ui/glassmorphism-card";
import { RoadmapSection } from "@/components/marketing/RoadmapSection";
import { HomePricing } from "@/components/marketing/HomePricing";
import { ConvictionPanel } from "@/components/brand/conviction-panel";
import { Logo } from "@/components/logo";
import { cn } from "@/shared/lib/utils";
import { useGuidedPathLive } from "@/hooks/useGuidedPathLive";
import { SignupOrLogin } from "@/components/site/signup-or-login";
import Link from "next/link";

function Section({ children, className, id }: { children: React.ReactNode; className?: string; id?: string }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });
  return (
    <motion.section
      ref={ref}
      id={id}
      initial={{ opacity: 0, y: 40 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.7, ease: "easeOut" }}
      className={cn("py-20 md:py-28 px-4 md:px-6", className)}
    >
      <div className="max-w-7xl mx-auto">{children}</div>
    </motion.section>
  );
}

/**
 * ONE door for a first-timer (cut 26 Sep): while the guided path is LIVE (frontend flag AND the
 * backend's readiness — the switch-on interlock) "Start Free" opens /start, whose first step IS the
 * signup — no separate register page before the guide. Otherwise /register, exactly as before.
 */
function useStartFreeHref(): string {
  return useGuidedPathLive() === "ready" ? "/start" : "/register";
}

function CTA({ text = "Shuru karo (free)", large = false }: { text?: string; large?: boolean }) {
  const href = useStartFreeHref();
  return (
  <SignupOrLogin
    href={href}
    className={cn(
      "inline-flex items-center gap-2 rounded-xl font-semibold text-white bg-gradient-to-r from-accent-blue to-accent-purple hover:shadow-glow-profit-lg transition-all",
      large ? "px-8 py-4 text-lg" : "px-6 py-3 text-sm"
    )}
    closedText={<>Login karo (naye account abhi band) <ArrowRight className={large ? "h-5 w-5" : "h-4 w-4"} /></>}
  >
    {text} <ArrowRight className={large ? "h-5 w-5" : "h-4 w-4"} />
  </SignupOrLogin>
  );
}

/* ═══════════════════════════════════════════════════════════════════════ */

export default function HomePage() {
  return (
    <>
      {/* ── SECTION 1: HERO ──────────────────────────────────────────── */}
      <section className="relative min-h-screen flex flex-col justify-center pt-24 pb-12 px-4 md:px-6 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-accent-blue/5 via-transparent to-accent-purple/5" />
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[min(600px,100vw)] h-[min(600px,100vw)] rounded-full bg-accent-blue/5 blur-3xl" />

        <div className="max-w-7xl mx-auto w-full grid lg:grid-cols-2 gap-12 items-center relative z-10">
          <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
            {/* Brand logo — same component as /login and /showcase */}
            <div className="flex items-center gap-2 mb-6">
              <Logo variant="icon" width={48} height={48} priority />
              <Logo variant="wordmark" height={46} />
            </div>

            <p className="text-xs font-mono tracking-[0.25em] text-accent-gold/70 uppercase mb-3">
              Har signal, saaf dikhega
            </p>

            {/* 5-SECOND TEST (founder's rule, 26 Sep): the headline says what this is FOR. */}
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold leading-[1.05] tracking-tight">
              Har trading signal saaf dikhega.{" "}
              <span className="bg-gradient-to-b from-brand-gold to-brand-green bg-clip-text text-transparent">
                Paisa aapke broker me.
              </span>
            </h1>

            <p className="text-base md:text-lg text-foreground/85 mt-5 max-w-xl leading-relaxed">
              TRADETRI par taiyar strategy chuno. Har signal dikhega — kab lena, stop kahan, target kahan — aur saath me ek bharosa score (conviction score), jo sirf salah hai. Shuru me har signal par aap khud &ldquo;haan&rdquo; bolte ho. Trade aapke apne broker account se hota hai — aapka paisa hum kabhi nahi pakadte.
            </p>

            <p className="text-xs md:text-13 text-muted-foreground font-mono tracking-[0.06em] mt-4">
              L&amp;T engineer ne banaya · 24 saal engineering · 20 saal ka NSE data · Dhan aur Fyers se seedha jude · server Mumbai me
            </p>

            {/* Honest stat row — no fabricated performance numbers */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8 max-w-xl">
              {[
                { icon: Eye, value: "Har signal", label: "Dikhega, apne score ke saath" },
                { icon: Landmark, value: "2", label: "Broker jude: Dhan, Fyers" },
                { icon: Wallet, value: "Aapka broker", label: "Paisa aapke paas rehta hai" },
                { icon: ShieldCheck, value: "SEBI niyam", label: "ke hisaab se (manzoori abhi baaki)" },
              ].map((s) => (
                <div key={s.label} className="text-center sm:text-left">
                  <s.icon className="h-5 w-5 mx-auto sm:mx-0 text-accent-blue mb-1.5" />
                  <div className="text-sm font-bold leading-tight">{s.value}</div>
                  <div className="text-xs text-muted-foreground leading-tight">{s.label}</div>
                </div>
              ))}
            </div>

            <div className="mt-8 flex flex-col sm:flex-row sm:items-center gap-4">
              <CTA large />
              <Link
                href="/showcase"
                className="inline-flex items-center gap-1.5 text-sm font-medium text-accent-blue hover:underline"
              >
                Dekho Proof →
              </Link>
            </div>
            <p className="text-sm text-muted-foreground mt-3">Free hai — card nahi chahiye.</p>
          </motion.div>

          {/* Right column — honest conviction-score demo (replaces the
              fabricated P&L widget). The panel is self-tagged "EXAMPLE". */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.3 }}
            className="hidden lg:block"
          >
            <ConvictionPanel />
          </motion.div>
        </div>

        {/* Broker integrations — integration, NOT endorsement */}
        <div className="max-w-7xl mx-auto w-full px-4 relative z-10 mt-14">
          <p className="text-xs text-muted-foreground text-center mb-3">Aaj Dhan aur Fyers ke saath chalta hai</p>
          <div className="flex justify-center flex-wrap gap-x-8 gap-y-2 text-sm text-muted-foreground">
            {["Dhan", "Fyers"].map((b) => (
              <span key={b} className="opacity-60 hover:opacity-100 transition-opacity">{b}</span>
            ))}
            <span className="w-full text-center text-xs text-muted-foreground/60">Zerodha, Upstox, AngelOne, Shoonya: jald aa rahe hain</span>
          </div>
        </div>
      </section>

      {/* ── SECTION 2: PROBLEM → DIFFERENT ───────────────────────────── */}
      <Section className="bg-gradient-to-b from-transparent via-loss/[0.02] to-transparent">
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-12">Zyadatar algo platform kehte hain — bas aankh band karke bharosa karo</h2>
        <div className="grid md:grid-cols-3 gap-6 mb-12">
          {[
                        { icon: Wallet, title: "PAISA UNKE PAAS", desc: "Kuch platform aapka paisa khud rakhte hain, ya apna tareeka paise ke peeche chhupa ke rakhte hain.", color: "text-loss" },
            { icon: Code2, title: "MUSHKIL", desc: "Code likhna padta hai. Sab kuch sirf English me. Apni bhasha me koi madad nahi.", color: "text-loss" },
          ].map((p) => (
            <GlassmorphismCard key={p.title} hover={false} className="text-center border-loss/10">
              <p.icon className={cn("h-8 w-8 mx-auto mb-3", p.color)} />
              <h3 className="font-bold text-lg mb-1">{p.title}</h3>
              <p className="text-sm text-muted-foreground">{p.desc}</p>
            </GlassmorphismCard>
          ))}
        </div>
        <div className="text-center text-3xl mb-8" aria-hidden="true">↓</div>
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-8">
          <span className="bg-gradient-to-r from-accent-blue to-profit bg-clip-text text-transparent">TRADETRI</span> — alag tarah se banaya
        </h2>
        <div className="grid md:grid-cols-3 gap-6">
          {[
            { icon: Eye, title: "Pehle signal", desc: "Har entry aur exit aapko dikhti hai — daam, stop aur target. Jodi hui strategy pehle haath-se (manual) mode me chalti hai: har signal par aap khud haan bolte ho.", color: "text-profit" },
            { icon: Landmark, title: "Aapka broker", desc: "Trade aapke apne registered broker se hota hai. Aapka paisa hum kabhi nahi rakhte.", color: "text-profit" },
            { icon: Languages, title: "Aasan + Hindi", desc: "Bina code ke strategy banao, Hinglish me coach, aur AlgoMitra Hinglish, English, Hindi aur Gujarati me.", color: "text-profit" },
          ].map((s) => (
            <GlassmorphismCard key={s.title} glow="profit" className="text-center">
              <s.icon className={cn("h-8 w-8 mx-auto mb-3", s.color)} />
              <h3 className="font-bold text-lg mb-1">{s.title}</h3>
              <p className="text-sm text-muted-foreground">{s.desc}</p>
            </GlassmorphismCard>
          ))}
        </div>
      </Section>

      {/* ── SECTION 3: FEATURES ──────────────────────────────────────── */}
      <Section id="features">
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">Saaf-saaf dikhane par bana, shor par nahi</h2>
        <p className="text-muted-foreground text-center mb-12 max-w-2xl mx-auto">Har cheez L&amp;T wali engineering ki aadat se bani. Koi shortcut nahi, aur koi trade aisa nahi jo aapne pehle na dekha ho.</p>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[
            { icon: Eye, title: "Bharosa score (conviction score)", desc: "Har signal ke saath ek score hota hai jo batata hai ki strategy ke niyam kitne pakke se haan bol rahe hain. Yeh sirf salah hai — faisla aapka, score aapki jagah nahi leta." },
            { icon: ShieldAlert, title: "Sab band switch (kill switch)", desc: "Pehle se chalu. Din ki tay nuksaan-had aate hi naye order rok deta hai aur jo khula hai use bazaar daam par band karta hai. Nuksaan ko seemit karta hai — pakka number ka vaada nahi karta." },
            { icon: Landmark, title: "Aapka apna broker", desc: "Aaj Dhan aur Fyers. Aapka paisa kabhi aapke broker account se bahar nahi jaata." },
            { icon: Bot, title: "Bina code ke strategy banao", desc: "Strategy banao, purane bazaar data par test karo, phir nakli paise se chalao — bina code likhe. Taiyar templates saath me; asli kab chalani hai, yeh aap tay karte ho." },
            { icon: BarChart3, title: "Imaandaar hisaab", desc: "Jeet ka hissa (win rate) aur P&L aapke APNE trades par — saaf likha hua, kabhi banaya hua nahi." },
            { icon: Lock, title: "Suraksha", desc: "Aapki broker ki chabi band (encrypted) rakhi jaati hai, hum tak aane wale har signal ke paas gupt code hona zaroori hai, aur baar-baar galat password par login ruk jaata hai." },
          ].map((f) => (
            <GlassmorphismCard key={f.title}>
              <f.icon className="h-8 w-8 text-accent-blue mb-3" />
              <h3 className="font-semibold text-lg mb-2">{f.title}</h3>
              <p className="text-sm text-muted-foreground">{f.desc}</p>
            </GlassmorphismCard>
          ))}
        </div>
      </Section>

      {/* ── SECTION 4: HOW IT WORKS ──────────────────────────────────── */}
      <Section className="bg-gradient-to-b from-transparent via-accent-blue/[0.02] to-transparent">
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-12">3 aasan kadam me shuru</h2>
        <div className="grid md:grid-cols-3 gap-8 mb-12">
          {[
            /* The SAME three steps Simple mode's onboarding shows (lib/simple/copy.ts ob_step_*). */
            { step: "1", title: "Bhasha chuno", desc: "Jo bhasha aaram ki ho — Hinglish, English, Hindi ya Gujarati. Kabhi bhi badal sakte ho." },
            { step: "2", title: "Broker jodo", desc: "Apna broker jodo (Dhan / Fyers). Paisa aapke broker ke paas hi rehta hai — hum sirf signal bhejte hain." },
            { step: "3", title: "Strategy chuno", desc: "Taiyar strategy aur uska jaancha hua record dekho. Pasand aaye to jodo — ya baad me aao." },
          ].map((s) => (
            <div key={s.step} className="text-center">
              <div className="h-14 w-14 rounded-2xl bg-gradient-to-br from-accent-blue to-accent-purple text-white font-bold text-2xl flex items-center justify-center mx-auto mb-4">{s.step}</div>
              <h3 className="font-semibold text-xl mb-2">{s.title}</h3>
              <p className="text-sm text-muted-foreground">{s.desc}</p>
            </div>
          ))}
        </div>
        <div className="text-center"><CTA text="Shuru karo (free)" large /></div>
      </Section>

      {/* ── SECTION 5: PROOF (replaces the fabricated performance table) ─ */}
      <Section>
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Proof,{" "}
            <span className="bg-gradient-to-b from-brand-gold to-brand-green bg-clip-text text-transparent">vaade nahi</span>
          </h2>
          <p className="text-muted-foreground leading-relaxed mb-3">
            Hum pehle page par banaye hue return nahi chipkaate. Record hamare khule Proof page par hai: purane bazaar data par test, saaf likha &ldquo;guarantee nahi&rdquo;, risk return ke bagal me, aur live record ki sachchi haalat — abhi jaanch me, publish nahi hua.
          </p>
          <p className="text-xs text-muted-foreground/70 mb-8">
            Pichhla pradarshan aage ke nateeje ki guarantee nahi deta. Purane data wale test andaaza hain, aur asli order test se thoda kharab daam par bhi bhar sakta hai.
          </p>
          <Link
            href="/showcase"
            className="inline-flex items-center gap-2 rounded-xl font-semibold text-white bg-gradient-to-r from-accent-blue to-accent-purple hover:shadow-glow-profit-lg transition-all px-8 py-4 text-lg"
          >
            Dekho Proof <ArrowRight className="h-5 w-5" />
          </Link>
        </div>
      </Section>

      {/* ── SECTION 6: FOUNDER STORY ─────────────────────────────────── */}
      <Section className="bg-gradient-to-b from-transparent via-accent-purple/[0.02] to-transparent">
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-12">Ek engineer ne banaya, influencer ne nahi.</h2>
        <div className="grid md:grid-cols-5 gap-8 items-center">
          <div className="md:col-span-1 text-center">
            <div className="h-28 w-28 rounded-full bg-gradient-to-br from-accent-blue to-accent-purple mx-auto flex items-center justify-center text-4xl font-bold text-white">JP</div>
          </div>
          <div className="md:col-span-4">
            <blockquote className="text-lg md:text-xl italic text-muted-foreground leading-relaxed">
              &ldquo;Maine 24 saal L&amp;T me asli dhancha banaya — Atal Setu, bijli ghar — jin par lakhon log bharosa karte hain. Wahi engineering ki aadat algo trading me laaya: saaf tareeka, aapka paisa aapke apne broker me, aur record imaandaari se dikhaya hua.
              <br /><br />
              Main course nahi bechta. Vaade nahi karta. Aisa system banata hoon jo chale — aur aapko dikhaye ki kaise chalta hai.&rdquo;
            </blockquote>
            <div className="mt-4">
              <div className="font-semibold">Jayesh Parekh</div>
              <div className="text-sm text-muted-foreground">Founder aur Engineer · Pehle L&amp;T me · 24 saal</div>
            </div>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-6 mt-12">
          {[
            { value: 24, label: "saal engineering (L&T me)" },
            { value: 20, label: "saal ka NSE data" },
            { value: 2, label: "broker jude (Dhan, Fyers)" },
          ].map((s) => (
            <GlassmorphismCard key={s.label} className="text-center py-6">
              <div className="text-3xl font-bold text-accent-blue">
                <AnimatedNumber value={s.value} />
              </div>
              <div className="text-sm text-muted-foreground mt-1">{s.label}</div>
            </GlassmorphismCard>
          ))}
        </div>
      </Section>

      {/* ── SECTION 7: ROADMAP — what ships when ─────────────────────── */}
      <RoadmapSection />

      {/* ── SECTION 8: PRICING ───────────────────────────────────────── */}
      <Section id="pricing" className="bg-gradient-to-b from-transparent via-accent-gold/[0.02] to-transparent">
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">Seedha, saaf daam</h2>
        <p className="text-muted-foreground text-center mb-10">Account banane me card nahi lagta. Paid plan pehli payment se shuru hota hai — kabhi bhi band kar sakte ho.</p>
        <HomePricing />
      </Section>

      {/* ── SECTION 9: FINAL CTA + HONEST RISK DISCLAIMER ────────────── */}
      <Section className="text-center bg-gradient-to-b from-transparent via-accent-blue/[0.03] to-transparent">
        <h2 className="text-3xl md:text-4xl font-bold mb-4">Proof ke saath trade karo, vaadon ke saath nahi.</h2>
        <p className="text-muted-foreground mb-8 max-w-lg mx-auto">
          Har signal dikhega, har bhara order likha jaayega — aapki strategy, aapka broker, aapka paisa. Aaj hi free shuru karo.
        </p>
        <CTA text="Shuru karo (free)" large />
        <p className="text-sm text-muted-foreground mt-3">Free hai — card nahi chahiye.</p>

        <p className="text-xs leading-relaxed text-muted-foreground/55 max-w-3xl mx-auto mt-12">
          Trading me poonji (capital) doobne ka bada risk hai. Pichhla pradarshan aage ke nateeje ki guarantee nahi deta, aur yahan kuch bhi nivesh ki salah (investment advice) nahi hai. TRADETRI pakke return ka koi daawa nahi karta. Trade aapke apne exchange-registered broker se jaate hain, SEBI ke algo-trading niyamon ke anusaar.
        </p>
      </Section>
    </>
  );
}
