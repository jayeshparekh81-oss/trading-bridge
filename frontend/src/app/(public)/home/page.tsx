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
import { AnimatedNumber } from "@/components/ui/animated-number";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { RoadmapSection } from "@/components/marketing/RoadmapSection";
import { HomePricing } from "@/components/marketing/HomePricing";
import { ConvictionPanel } from "@/components/brand/conviction-panel";
import { Logo } from "@/components/logo";
import { cn } from "@/lib/utils";
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

const CTA = ({ text = "Start Free", large = false }: { text?: string; large?: boolean }) => (
  <Link
    href="/register"
    className={cn(
      "inline-flex items-center gap-2 rounded-xl font-semibold text-white bg-gradient-to-r from-accent-blue to-accent-purple hover:shadow-[0_0_30px_rgba(59,130,246,0.4)] transition-all",
      large ? "px-8 py-4 text-lg" : "px-6 py-3 text-sm"
    )}
  >
    {text} <ArrowRight className={large ? "h-5 w-5" : "h-4 w-4"} />
  </Link>
);

/* ═══════════════════════════════════════════════════════════════════════ */

export default function HomePage() {
  return (
    <>
      {/* ── SECTION 1: HERO ──────────────────────────────────────────── */}
      <section className="relative min-h-screen flex flex-col justify-center pt-24 pb-12 px-4 md:px-6 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-accent-blue/5 via-transparent to-accent-purple/5" />
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-accent-blue/5 blur-3xl" />

        <div className="max-w-7xl mx-auto w-full grid lg:grid-cols-2 gap-12 items-center relative z-10">
          <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
            {/* Brand logo — same component as /login and /showcase */}
            <div className="flex items-center gap-2 mb-6">
              <Logo variant="icon" width={48} height={48} priority />
              <Logo variant="wordmark" height={46} />
            </div>

            <p className="text-[11px] font-mono tracking-[0.25em] text-accent-gold/70 uppercase mb-3">
              Glass Box · Transparent Algo Trading
            </p>

            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold leading-[1.05] tracking-tight">
              Backtest nahi.{" "}
              <span className="bg-gradient-to-b from-[#FFD700] to-[#00FF88] bg-clip-text text-transparent">
                Proof.
              </span>
            </h1>

            <p className="text-base md:text-lg text-foreground/85 mt-5 max-w-xl leading-relaxed">
              TRADETRI is a transparent, white-box algo-trading platform. Every signal gets an AI conviction score — a rule-based validator that only trades when it clears the threshold. Every trade routes through your own registered broker; we never hold your funds. And the track record is shown honestly — risk next to return.
            </p>

            <p className="text-[12px] md:text-[13px] text-muted-foreground font-mono tracking-[0.06em] mt-4">
              Built by an L&amp;T engineer · 24 years engineering · 20 yrs NSE data · 6 broker APIs · AWS Mumbai
            </p>

            {/* Honest stat row — no fabricated performance numbers */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8 max-w-xl">
              {[
                { icon: Eye, value: "White-box", label: "Every signal scored" },
                { icon: Landmark, value: "6", label: "Broker integrations" },
                { icon: Wallet, value: "Your broker", label: "Funds stay with you" },
                { icon: ShieldCheck, value: "SEBI-aware", label: "Algo framework" },
              ].map((s) => (
                <div key={s.label} className="text-center sm:text-left">
                  <s.icon className="h-5 w-5 mx-auto sm:mx-0 text-accent-blue mb-1.5" />
                  <div className="text-sm font-bold leading-tight">{s.value}</div>
                  <div className="text-[11px] text-muted-foreground leading-tight">{s.label}</div>
                </div>
              ))}
            </div>

            <div className="mt-8 flex flex-col sm:flex-row sm:items-center gap-4">
              <CTA large />
              <Link
                href="/showcase"
                className="inline-flex items-center gap-1.5 text-sm font-medium text-accent-blue hover:underline"
              >
                Dekho verified Track Record →
              </Link>
            </div>
            <p className="text-xs text-muted-foreground mt-3">No credit card required.</p>
          </motion.div>

          {/* Right column — honest white-box conviction demo (replaces the
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
          <p className="text-xs text-muted-foreground text-center mb-3">Works with your broker</p>
          <div className="flex justify-center flex-wrap gap-x-8 gap-y-2 text-sm text-muted-foreground">
            {["Fyers", "Dhan", "Zerodha", "Upstox", "AngelOne", "Shoonya"].map((b) => (
              <span key={b} className="opacity-60 hover:opacity-100 transition-opacity">{b}</span>
            ))}
          </div>
        </div>
      </section>

      {/* ── SECTION 2: PROBLEM → DIFFERENT ───────────────────────────── */}
      <Section className="bg-gradient-to-b from-transparent via-loss/[0.02] to-transparent">
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-12">Most algo platforms ask for blind trust</h2>
        <div className="grid md:grid-cols-3 gap-6 mb-12">
          {[
            { icon: EyeOff, title: "OPAQUE", desc: "Black-box signals. You can't see why a trade was taken — or skipped.", color: "text-loss" },
            { icon: Wallet, title: "CUSTODIAL RISK", desc: "Some platforms touch your funds or hide their logic behind a paywall.", color: "text-loss" },
            { icon: Code2, title: "COMPLEX", desc: "Coding required. English-only docs. No regional-language help.", color: "text-loss" },
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
          <span className="bg-gradient-to-r from-accent-blue to-profit bg-clip-text text-transparent">TRADETRI</span> — built different
        </h2>
        <div className="grid md:grid-cols-3 gap-6">
          {[
            { icon: Eye, title: "White-box", desc: "Every signal shows its AI conviction score and why it passed or failed the threshold.", color: "text-profit" },
            { icon: Landmark, title: "Your broker", desc: "Trades route through your own registered broker. We never hold your funds.", color: "text-profit" },
            { icon: Languages, title: "Simple + Hindi", desc: "No-code builder, Hinglish coach, and 10 regional languages.", color: "text-profit" },
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
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">Built on transparency, not hype</h2>
        <p className="text-muted-foreground text-center mb-12 max-w-2xl mx-auto">Every feature built with L&amp;T engineering discipline. No shortcuts, no black boxes.</p>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[
            { icon: Eye, title: "White-box AI conviction", desc: "Every signal gets a transparent conviction score and only trades when it clears the threshold. You see why each trade was taken or skipped." },
            { icon: ShieldAlert, title: "Kill switch", desc: "Auto-stops trading when YOUR loss limit is hit and squares off positions instantly. Never lose more than you set." },
            { icon: Landmark, title: "6 broker integrations", desc: "Fyers, Dhan, Zerodha, Upstox, AngelOne, Shoonya. One platform — your own broker, and your funds never leave it." },
            { icon: Bot, title: "No-code strategy builder", desc: "Build and paper-test strategies without writing code. Pre-built templates, one-click deploy." },
            { icon: BarChart3, title: "Honest analytics", desc: "Win rate, P&L, slippage and latency on YOUR own trades — clearly labelled, never invented." },
            { icon: Lock, title: "Encryption & HMAC", desc: "AES-256 encrypted broker credentials, HMAC-signed webhooks, and brute-force protection." },
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
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-12">Start in 3 simple steps</h2>
        <div className="grid md:grid-cols-3 gap-8 mb-12">
          {[
            { step: "1", title: "Connect", desc: "Link your broker account (Fyers / Dhan and more). Credentials are encrypted with AES-256." },
            { step: "2", title: "Set up", desc: "Create a webhook in one click, get your unique URL, and paste it into TradingView." },
            { step: "3", title: "Trade", desc: "TradingView sends a signal → it's conviction-scored → if it clears the threshold, the order routes to your broker. Kill switch always on." },
          ].map((s) => (
            <div key={s.step} className="text-center">
              <div className="h-14 w-14 rounded-2xl bg-gradient-to-br from-accent-blue to-accent-purple text-white font-bold text-2xl flex items-center justify-center mx-auto mb-4">{s.step}</div>
              <h3 className="font-semibold text-xl mb-2">{s.title}</h3>
              <p className="text-sm text-muted-foreground">{s.desc}</p>
            </div>
          ))}
        </div>
        <div className="text-center"><CTA text="Start Free" large /></div>
      </Section>

      {/* ── SECTION 5: PROOF (replaces the fabricated performance table) ─ */}
      <Section>
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Proof, not{" "}
            <span className="bg-gradient-to-b from-[#FFD700] to-[#00FF88] bg-clip-text text-transparent">promises</span>
          </h2>
          <p className="text-muted-foreground leading-relaxed mb-3">
            We don&apos;t paste invented returns on a landing page. The real record lives on our public Track Record — risk shown next to return, with in-sample backtests clearly labelled hypothetical.
          </p>
          <p className="text-xs text-muted-foreground/70 mb-8">
            Past performance is not indicative of future results. Backtests are hypothetical and exclude slippage.
          </p>
          <Link
            href="/showcase"
            className="inline-flex items-center gap-2 rounded-xl font-semibold text-white bg-gradient-to-r from-accent-blue to-accent-purple hover:shadow-[0_0_30px_rgba(59,130,246,0.4)] transition-all px-8 py-4 text-lg"
          >
            Dekho verified Track Record <ArrowRight className="h-5 w-5" />
          </Link>
        </div>
      </Section>

      {/* ── SECTION 6: FOUNDER STORY ─────────────────────────────────── */}
      <Section className="bg-gradient-to-b from-transparent via-accent-purple/[0.02] to-transparent">
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-12">Built by an engineer, not an influencer.</h2>
        <div className="grid md:grid-cols-5 gap-8 items-center">
          <div className="md:col-span-1 text-center">
            <div className="h-28 w-28 rounded-full bg-gradient-to-br from-accent-blue to-accent-purple mx-auto flex items-center justify-center text-4xl font-bold text-white">JP</div>
          </div>
          <div className="md:col-span-4">
            <blockquote className="text-lg md:text-xl italic text-muted-foreground leading-relaxed">
              &ldquo;I spent 24 years at L&amp;T building real infrastructure — Atal Setu, power plants — systems millions depend on. I brought that same engineering discipline to algo trading: transparent logic, your funds in your own broker, and a track record shown honestly.
              <br /><br />
              I don&apos;t sell courses. I don&apos;t make promises. I build systems that work — and show you exactly how they work.&rdquo;
            </blockquote>
            <div className="mt-4">
              <div className="font-semibold">Jayesh Parekh</div>
              <div className="text-sm text-muted-foreground">Founder &amp; Engineer · Ex-L&amp;T · 24 Years</div>
            </div>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-6 mt-12">
          {[
            { value: 24, label: "Years engineering (Ex-L&T)" },
            { value: 20, label: "Years NSE data" },
            { value: 6, label: "Broker integrations" },
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
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">Simple, transparent pricing</h2>
        <p className="text-muted-foreground text-center mb-10">All plans include a 7-day free trial. No credit card required.</p>
        <HomePricing />
        <p className="text-center text-sm text-accent-gold mt-8 font-medium">
          🎉 First 3 months free for early adopters.
        </p>
      </Section>

      {/* ── SECTION 9: FINAL CTA + HONEST RISK DISCLAIMER ────────────── */}
      <Section className="text-center bg-gradient-to-b from-transparent via-accent-blue/[0.03] to-transparent">
        <h2 className="text-3xl md:text-4xl font-bold mb-4">Trade with proof, not promises.</h2>
        <p className="text-muted-foreground mb-8 max-w-lg mx-auto">
          Transparent, white-box algo trading — your strategy, your broker, your funds. Start free today.
        </p>
        <CTA text="Start Free" large />
        <p className="text-xs text-muted-foreground mt-3">No credit card required.</p>

        <p className="text-[11px] leading-relaxed text-muted-foreground/55 max-w-3xl mx-auto mt-12">
          Trading involves a substantial risk of capital loss. Past performance is not indicative of future results, and nothing here is investment advice. TRADETRI provides white-box strategies and makes no guaranteed-return claims. Trades are routed through your own exchange-registered broker, in line with SEBI&apos;s algo-trading framework.
        </p>
      </Section>
    </>
  );
}
