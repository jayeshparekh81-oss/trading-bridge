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
import { publicCopy } from "@/lib/i18n/copy/public";
import { useCopy } from "@/lib/i18n/core";

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

function CTA({ text, large = false }: { text?: string; large?: boolean }) {
  const href = useStartFreeHref();
  const { c } = useCopy(publicCopy);
  return (
  <SignupOrLogin
    href={href}
    className={cn(
      "inline-flex items-center gap-2 rounded-xl font-semibold text-white bg-gradient-to-r from-accent-blue to-accent-purple hover:shadow-glow-profit-lg transition-all",
      large ? "px-8 py-4 text-lg" : "px-6 py-3 text-sm"
    )}
    closedText={<>{c.cta_start_closed} <ArrowRight className={large ? "h-5 w-5" : "h-4 w-4"} /></>}
  >
    {text ?? c.cta_start} <ArrowRight className={large ? "h-5 w-5" : "h-4 w-4"} />
  </SignupOrLogin>
  );
}

/* ═══════════════════════════════════════════════════════════════════════ */

export default function HomePage() {
  const { c } = useCopy(publicCopy);
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
              {c.home_eyebrow}
            </p>

            {/* 5-SECOND TEST (founder's rule, 26 Sep): the headline says what this is FOR. */}
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold leading-[1.05] tracking-tight">
              {c.home_h1_a}{" "}
              <span className="bg-gradient-to-b from-brand-gold to-brand-green bg-clip-text text-transparent">
                {c.home_h1_b}
              </span>
            </h1>

            <p className="text-base md:text-lg text-foreground/85 mt-5 max-w-xl leading-relaxed">
              {c.home_lead}
            </p>

            <p className="text-xs md:text-13 text-muted-foreground font-mono tracking-[0.06em] mt-4">
              {c.home_facts}
            </p>

            {/* Honest stat row — no fabricated performance numbers */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8 max-w-xl">
              {[
                { icon: Eye, value: c.stat_signal_v, label: c.stat_signal_l },
                { icon: Landmark, value: c.stat_brokers_v, label: c.stat_brokers_l },
                { icon: Wallet, value: c.stat_money_v, label: c.stat_money_l },
                { icon: ShieldCheck, value: c.stat_sebi_v, label: c.stat_sebi_l },
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
                {c.see_proof}
              </Link>
            </div>
            <p className="text-sm text-muted-foreground mt-3">{c.free_no_card}</p>
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
          <p className="text-xs text-muted-foreground text-center mb-3">{c.brokers_today}</p>
          <div className="flex justify-center flex-wrap gap-x-8 gap-y-2 text-sm text-muted-foreground">
            {["Dhan", "Fyers"].map((b) => (
              <span key={b} className="opacity-60 hover:opacity-100 transition-opacity">{b}</span>
            ))}
            <span className="w-full text-center text-xs text-muted-foreground/60">{c.brokers_soon}</span>
          </div>
        </div>
      </section>

      {/* ── SECTION 2: PROBLEM → DIFFERENT ───────────────────────────── */}
      <Section className="bg-gradient-to-b from-transparent via-loss/[0.02] to-transparent">
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-12">{c.problem_h2}</h2>
        <div className="grid md:grid-cols-3 gap-6 mb-12">
          {[
            { icon: Wallet, title: c.p1_title, desc: c.p1_desc, color: "text-loss" },
            { icon: Code2, title: c.p2_title, desc: c.p2_desc, color: "text-loss" },
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
          <span className="bg-gradient-to-r from-accent-blue to-profit bg-clip-text text-transparent">TRADETRI</span> {c.different_h2_b}
        </h2>
        <div className="grid md:grid-cols-3 gap-6">
          {[
            { icon: Eye, title: c.d1_title, desc: c.d1_desc, color: "text-profit" },
            { icon: Landmark, title: c.d2_title, desc: c.d2_desc, color: "text-profit" },
            { icon: Languages, title: c.d3_title, desc: c.d3_desc, color: "text-profit" },
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
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">{c.feat_h2}</h2>
        <p className="text-muted-foreground text-center mb-12 max-w-2xl mx-auto">{c.feat_sub}</p>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[
            { icon: Eye, title: c.f1_title, desc: c.f1_desc },
            { icon: ShieldAlert, title: c.f2_title, desc: c.f2_desc },
            { icon: Landmark, title: c.f3_title, desc: c.f3_desc },
            { icon: Bot, title: c.f4_title, desc: c.f4_desc },
            { icon: BarChart3, title: c.f5_title, desc: c.f5_desc },
            { icon: Lock, title: c.f6_title, desc: c.f6_desc },
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
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-12">{c.how_h2}</h2>
        <div className="grid md:grid-cols-3 gap-8 mb-12">
          {[
            /* The SAME three steps Simple mode's onboarding shows (lib/simple/copy.ts ob_step_*). */
            { step: "1", title: c.how1_title, desc: c.how1_desc },
            { step: "2", title: c.how2_title, desc: c.how2_desc },
            { step: "3", title: c.how3_title, desc: c.how3_desc },
          ].map((s) => (
            <div key={s.step} className="text-center">
              <div className="h-14 w-14 rounded-2xl bg-gradient-to-br from-accent-blue to-accent-purple text-white font-bold text-2xl flex items-center justify-center mx-auto mb-4">{s.step}</div>
              <h3 className="font-semibold text-xl mb-2">{s.title}</h3>
              <p className="text-sm text-muted-foreground">{s.desc}</p>
            </div>
          ))}
        </div>
        <div className="text-center"><CTA large /></div>
      </Section>

      {/* ── SECTION 5: PROOF (replaces the fabricated performance table) ─ */}
      <Section>
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            {c.proof_h2_a}{" "}
            <span className="bg-gradient-to-b from-brand-gold to-brand-green bg-clip-text text-transparent">{c.proof_h2_b}</span>
          </h2>
          <p className="text-muted-foreground leading-relaxed mb-3">
            {c.proof_p1}
          </p>
          <p className="text-xs text-muted-foreground/70 mb-8">
            {c.proof_p2}
          </p>
          <Link
            href="/showcase"
            className="inline-flex items-center gap-2 rounded-xl font-semibold text-white bg-gradient-to-r from-accent-blue to-accent-purple hover:shadow-glow-profit-lg transition-all px-8 py-4 text-lg"
          >
            {c.see_proof_btn} <ArrowRight className="h-5 w-5" />
          </Link>
        </div>
      </Section>

      {/* ── SECTION 6: FOUNDER STORY ─────────────────────────────────── */}
      <Section className="bg-gradient-to-b from-transparent via-accent-purple/[0.02] to-transparent">
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-12">{c.founder_h2}</h2>
        <div className="grid md:grid-cols-5 gap-8 items-center">
          <div className="md:col-span-1 text-center">
            <div className="h-28 w-28 rounded-full bg-gradient-to-br from-accent-blue to-accent-purple mx-auto flex items-center justify-center text-4xl font-bold text-white">JP</div>
          </div>
          <div className="md:col-span-4">
            <blockquote className="text-lg md:text-xl italic text-muted-foreground leading-relaxed">
              {c.founder_quote_1}
              <br /><br />
              {c.founder_quote_2}
            </blockquote>
            <div className="mt-4">
              <div className="font-semibold">{c.founder_name}</div>
              <div className="text-sm text-muted-foreground">{c.founder_role}</div>
            </div>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-6 mt-12">
          {[
            { value: 24, label: c.fstat_1 },
            { value: 20, label: c.fstat_2 },
            { value: 2, label: c.fstat_3 },
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
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">{c.pricing_h2}</h2>
        <p className="text-muted-foreground text-center mb-10">{c.pricing_sub}</p>
        <HomePricing />
      </Section>

      {/* ── SECTION 9: FINAL CTA + HONEST RISK DISCLAIMER ────────────── */}
      <Section className="text-center bg-gradient-to-b from-transparent via-accent-blue/[0.03] to-transparent">
        <h2 className="text-3xl md:text-4xl font-bold mb-4">{c.final_h2}</h2>
        <p className="text-muted-foreground mb-8 max-w-lg mx-auto">{c.final_p}</p>
        <CTA large />
        <p className="text-sm text-muted-foreground mt-3">{c.free_no_card}</p>

        <p className="text-xs leading-relaxed text-muted-foreground/55 max-w-3xl mx-auto mt-12">
          {c.risk_line}
        </p>
      </Section>
    </>
  );
}
