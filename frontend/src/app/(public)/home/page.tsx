"use client";

import { useRef } from "react";
import { motion, useInView } from "framer-motion";
import { Zap, Shield, Landmark, Bot, BarChart3, Lock, Turtle, ShieldAlert, Brain, Star, ArrowRight, CheckCircle, XCircle, Trophy } from "lucide-react";
import { AnimatedNumber } from "@/components/ui/animated-number";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { cn } from "@/lib/utils";
import Link from "next/link";
import type { Metadata } from "next";

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

const CTA = ({ text = "Start Free \u2014 7 Day Trial", large = false }: { text?: string; large?: boolean }) => (
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
      <section className="relative min-h-screen flex items-center pt-16 px-4 md:px-6 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-accent-blue/5 via-transparent to-accent-purple/5" />
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-accent-blue/5 blur-3xl" />

        <div className="max-w-7xl mx-auto w-full grid lg:grid-cols-2 gap-12 items-center relative z-10">
          <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold leading-tight tracking-tight">
              India&apos;s Fastest{" "}
              <span className="bg-gradient-to-r from-accent-blue to-accent-purple bg-clip-text text-transparent">
                Algo Trading
              </span>{" "}
              Platform
            </h1>
            <p className="text-lg text-muted-foreground mt-4 max-w-lg">
              Built by an L&amp;T Engineer. 24 years of engineering excellence, now powering your trades.
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8">
              {[
                { icon: Zap, label: "Execution", value: "<50ms" },
                { icon: Shield, label: "Security", value: "15-Layer" },
                { icon: Landmark, label: "Brokers", value: "6" },
                { icon: Bot, label: "Strategies", value: "200+" },
              ].map((s) => (
                <div key={s.label} className="text-center">
                  <s.icon className="h-5 w-5 mx-auto text-accent-blue mb-1" />
                  <div className="text-xl font-bold">{s.value}</div>
                  <div className="text-xs text-muted-foreground">{s.label}</div>
                </div>
              ))}
            </div>

            <div className="mt-8 flex flex-col sm:flex-row items-start gap-4">
              <CTA large />
              <p className="text-xs text-muted-foreground self-center">No credit card required. 4,000+ traders trust us.</p>
            </div>
          </motion.div>

          {/* Dashboard Preview */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.3 }}
            className="hidden lg:block"
          >
            <div className="glass rounded-2xl p-6 glow-border-blue">
              <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Today&apos;s P&amp;L</div>
              <div className="text-4xl font-bold text-profit glow-profit mb-4">
                +<AnimatedNumber value={12450} prefix={"\u20B9"} />
              </div>
              <div className="h-2 rounded-full bg-white/[0.05] mb-3 overflow-hidden">
                <motion.div initial={{ width: 0 }} animate={{ width: "72%" }} transition={{ duration: 1.5 }} className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-profit" />
              </div>
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Realized: <span className="text-profit">+\u20B98,200</span></span>
                <span>Win Rate: <span className="text-profit">80%</span></span>
                <span>Trades: 12</span>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Broker logos */}
        <div className="absolute bottom-8 left-0 right-0">
          <div className="max-w-7xl mx-auto px-4">
            <p className="text-xs text-muted-foreground text-center mb-3">Trusted by traders using</p>
            <div className="flex justify-center gap-8 text-sm text-muted-foreground">
              {["Fyers", "Dhan", "Zerodha", "Upstox", "AngelOne", "Shoonya"].map((b) => (
                <span key={b} className="opacity-50 hover:opacity-100 transition-opacity">{b}</span>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── SECTION 2: PROBLEM → SOLUTION ────────────────────────────── */}
      <Section className="bg-gradient-to-b from-transparent via-loss/[0.02] to-transparent">
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-12">Trading Platforms Today</h2>
        <div className="grid md:grid-cols-3 gap-6 mb-12">
          {[
            { icon: Turtle, title: "SLOW", desc: "500-1500ms latency. Your order arrives after the move.", color: "text-loss" },
            { icon: ShieldAlert, title: "UNSAFE", desc: "3-5 layers security. One breach = account wiped.", color: "text-loss" },
            { icon: Brain, title: "COMPLEX", desc: "Coding required. Docs in English only. No Hindi support.", color: "text-loss" },
          ].map((p) => (
            <GlassmorphismCard key={p.title} hover={false} className="text-center border-loss/10">
              <p.icon className={cn("h-8 w-8 mx-auto mb-3", p.color)} />
              <h3 className="font-bold text-lg mb-1">{p.title}</h3>
              <p className="text-sm text-muted-foreground">{p.desc}</p>
            </GlassmorphismCard>
          ))}
        </div>
        <div className="text-center text-3xl mb-8">&darr;</div>
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-8">
          <span className="bg-gradient-to-r from-accent-blue to-profit bg-clip-text text-transparent">TradeForge</span> &mdash; Built Different
        </h2>
        <div className="grid md:grid-cols-3 gap-6">
          {[
            { icon: Zap, title: "<50ms", desc: "Lightning fast. 10x faster than competitors.", color: "text-profit" },
            { icon: Shield, title: "15 Layers", desc: "Bank-grade encryption. Fort Knox level security.", color: "text-profit" },
            { icon: CheckCircle, title: "3-Click", desc: "So simple, anyone can trade. Hindi support.", color: "text-profit" },
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
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">Why 4,000+ Traders Choose TradeForge</h2>
        <p className="text-muted-foreground text-center mb-12 max-w-2xl mx-auto">Every feature built with L&amp;T engineering discipline. No shortcuts.</p>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[
            { icon: Zap, title: "Sub-50ms Execution", desc: "Lightning fast order placement. 10x faster than Tradetron. Your edge in volatile markets." },
            { icon: ShieldAlert, title: "Kill Switch", desc: "Auto-stops trading when YOUR loss limit is hit. Positions squared off instantly. Never lose more than you set." },
            { icon: Landmark, title: "6 Brokers", desc: "Fyers, Dhan, Zerodha, Upstox, AngelOne, Shoonya. One platform, all brokers." },
            { icon: Bot, title: "200+ AI Strategies", desc: "Pre-built, backtested, profitable strategies. One-click deploy. No coding required." },
            { icon: BarChart3, title: "Full Analytics", desc: "Win rate, P&L, slippage, latency \u2014 all in real-time. Know exactly how you\u0027re performing." },
            { icon: Lock, title: "Bank-Grade Security", desc: "AES-256 encryption, HMAC signatures, brute-force protection. 15 security layers. Sleep peacefully." },
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
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-12">Start Trading in 3 Minutes</h2>
        <div className="grid md:grid-cols-3 gap-8 mb-12">
          {[
            { step: "1", title: "Connect", desc: "Link your broker account (Fyers/Dhan). Takes 2 minutes. Credentials encrypted with AES-256." },
            { step: "2", title: "Set Up", desc: "Create a webhook in 1 click. Get your unique URL. Paste it into TradingView." },
            { step: "3", title: "Trade", desc: "TradingView sends signal \u2192 order placed in <50ms. Kill switch protects you 24/7." },
          ].map((s) => (
            <div key={s.step} className="text-center">
              <div className="h-14 w-14 rounded-2xl bg-gradient-to-br from-accent-blue to-accent-purple text-white font-bold text-2xl flex items-center justify-center mx-auto mb-4">{s.step}</div>
              <h3 className="font-semibold text-xl mb-2">{s.title}</h3>
              <p className="text-sm text-muted-foreground">{s.desc}</p>
            </div>
          ))}
        </div>
        <div className="text-center"><CTA text="Start Free \u2014 Takes 2 Minutes" large /></div>
      </Section>

      {/* ── SECTION 5: PERFORMANCE ───────────────────────────────────── */}
      <Section>
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">Live Strategy Performance</h2>
        <p className="text-muted-foreground text-center mb-10 text-sm">Updated daily. Verified by system. Past performance \u2260 future results.</p>
        <GlassmorphismCard hover={false} className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/[0.08]">
                  {["Strategy", "1 Month", "3 Months", "6 Months", "1 Year"].map((h) => (
                    <th key={h} className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  { name: "Nifty Scalper", m1: 8.4, m3: 24.7, m6: 52.3, y1: 118 },
                  { name: "BankNifty Swing", m1: 4.2, m3: 12.8, m6: 28.1, y1: 55 },
                  { name: "Options Theta", m1: 6.1, m3: 18.5, m6: 38.2, y1: 72 },
                  { name: "Gap Strategy", m1: 3.8, m3: 11.2, m6: 22.5, y1: 48 },
                ].map((s) => (
                  <tr key={s.name} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                    <td className="py-3 px-4 font-medium">{s.name}</td>
                    {[s.m1, s.m3, s.m6, s.y1].map((v, i) => (
                      <td key={i} className="py-3 px-4 text-profit font-semibold">+{v}%</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassmorphismCard>
      </Section>

      {/* ── SECTION 6: FOUNDER STORY ─────────────────────────────────── */}
      <Section className="bg-gradient-to-b from-transparent via-accent-purple/[0.02] to-transparent">
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-12">Built by an Engineer, Not an Influencer.</h2>
        <div className="grid md:grid-cols-5 gap-8 items-center">
          <div className="md:col-span-1 text-center">
            <div className="h-28 w-28 rounded-full bg-gradient-to-br from-accent-blue to-accent-purple mx-auto flex items-center justify-center text-4xl font-bold text-white">JP</div>
          </div>
          <div className="md:col-span-4">
            <blockquote className="text-lg md:text-xl italic text-muted-foreground leading-relaxed">
              &ldquo;I spent 24 years at L&amp;T building real bridges &mdash; Atal Setu, power plants, infrastructure that millions depend on. I brought that same engineering discipline to algo trading.
              <br /><br />
              785 tests. 97% code coverage. 15-layer security. &lt;50ms speed.
              <br /><br />
              I don&apos;t sell courses. I don&apos;t make promises. I build systems that work.&rdquo;
            </blockquote>
            <div className="mt-4">
              <div className="font-semibold">Jayesh Parekh</div>
              <div className="text-sm text-muted-foreground">Founder &amp; Engineer &bull; Ex-L&amp;T &bull; 24 Years</div>
            </div>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-6 mt-12">
          {[
            { value: 785, label: "Tests Passing" },
            { value: 97, label: "% Code Coverage", suffix: "%" },
            { value: 50, label: "ms Latency", prefix: "<" },
          ].map((s) => (
            <GlassmorphismCard key={s.label} className="text-center py-6">
              <div className="text-3xl font-bold text-accent-blue">
                <AnimatedNumber value={s.value} prefix={s.prefix} suffix={s.suffix} />
              </div>
              <div className="text-sm text-muted-foreground mt-1">{s.label}</div>
            </GlassmorphismCard>
          ))}
        </div>
      </Section>

      {/* ── SECTION 7: COMPARISON ────────────────────────────────────── */}
      <Section>
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-10">How We Compare</h2>
        <GlassmorphismCard hover={false} className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.08]">
                  <th className="text-left py-3 px-4 text-xs text-muted-foreground uppercase">Feature</th>
                  <th className="text-center py-3 px-4 text-xs uppercase text-accent-blue font-bold">TradeForge</th>
                  <th className="text-center py-3 px-4 text-xs text-muted-foreground uppercase">Tradetron</th>
                  <th className="text-center py-3 px-4 text-xs text-muted-foreground uppercase">StrykeX</th>
                  <th className="text-center py-3 px-4 text-xs text-muted-foreground uppercase">AlgoTest</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { feature: "Speed", us: "\u26A1 <50ms", t: "\uD83D\uDC22 1000ms", s: "\uD83D\uDC22 500ms", a: "\uD83D\uDC22 800ms" },
                  { feature: "Brokers", us: "\uD83C\uDFC6 6", t: "8", s: "1", a: "6" },
                  { feature: "Security", us: "\uD83C\uDFC6 15-layer", t: "Basic", s: "Basic", a: "Basic" },
                  { feature: "Kill Switch", us: "\uD83C\uDFC6 Advanced", t: "None", s: "None", a: "Basic" },
                  { feature: "AI Strategies", us: "\uD83C\uDFC6 200+", t: "User", s: "35", a: "None" },
                  { feature: "Languages", us: "\uD83C\uDFC6 11", t: "1", s: "2", a: "1" },
                  { feature: "Price", us: "\u20B9999/mo", t: "\u20B91,500+", s: "\u20B925K life", a: "\u20B91,500+" },
                ].map((r) => (
                  <tr key={r.feature} className="border-b border-white/[0.04]">
                    <td className="py-3 px-4 font-medium">{r.feature}</td>
                    <td className="py-3 px-4 text-center font-semibold text-accent-blue">{r.us}</td>
                    <td className="py-3 px-4 text-center text-muted-foreground">{r.t}</td>
                    <td className="py-3 px-4 text-center text-muted-foreground">{r.s}</td>
                    <td className="py-3 px-4 text-center text-muted-foreground">{r.a}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassmorphismCard>
        <div className="text-center mt-8"><CTA text="Start Free \u2014 See the Difference" /></div>
      </Section>

      {/* ── SECTION 8: PRICING ───────────────────────────────────────── */}
      <Section id="pricing" className="bg-gradient-to-b from-transparent via-accent-gold/[0.02] to-transparent">
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">Simple, Transparent Pricing</h2>
        <p className="text-muted-foreground text-center mb-10">All plans include 7-day free trial. No credit card required.</p>
        <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
          {[
            { name: "Starter", price: 999, features: ["1 broker", "5 strategies", "Kill Switch", "Email alerts", "Community support"], popular: false },
            { name: "Pro", price: 2499, features: ["3 brokers", "50 strategies", "Kill Switch + Analytics", "Email + Telegram", "CSV export", "Priority support"], popular: true },
            { name: "Premium", price: 4999, features: ["6 brokers", "200+ strategies", "AI Smart Signals", "Shadow Stop-Loss", "All channels", "Dedicated support"], popular: false },
          ].map((plan) => (
            <GlassmorphismCard
              key={plan.name}
              glow={plan.popular ? "blue" : "none"}
              className={cn("relative", plan.popular && "border-accent-blue/40 scale-[1.02]")}
            >
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full bg-accent-blue text-white text-xs font-bold">Most Popular</div>
              )}
              <div className="text-center mb-6">
                <h3 className="font-bold text-xl mb-1">{plan.name}</h3>
                <div className="text-3xl font-bold">{"\u20B9"}{plan.price}<span className="text-base font-normal text-muted-foreground">/mo</span></div>
              </div>
              <ul className="space-y-2.5 mb-6">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-center gap-2 text-sm">
                    <CheckCircle className="h-4 w-4 text-profit shrink-0" />{f}
                  </li>
                ))}
              </ul>
              <Link
                href="/register"
                className={cn(
                  "block text-center py-3 rounded-xl font-semibold transition-all",
                  plan.popular
                    ? "bg-gradient-to-r from-accent-blue to-accent-purple text-white hover:shadow-[0_0_25px_rgba(59,130,246,0.4)]"
                    : "border border-border hover:bg-accent"
                )}
              >
                Start Free
              </Link>
            </GlassmorphismCard>
          ))}
        </div>
        <p className="text-center text-sm text-accent-gold mt-8 font-medium">
          \uD83C\uDF89 First 3 months FREE for early adopters!
        </p>
      </Section>

      {/* ── SECTION 9: TESTIMONIALS ──────────────────────────────────── */}
      <Section>
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-10">What Traders Say</h2>
        <div className="grid md:grid-cols-3 gap-6">
          {[
            { quote: "Pehle Tradetron use karta tha. TradeForge mein orders 10x fast aate hain. Kill Switch ne mera \u20B915,000 bachaya ek din mein.", name: "Rahul S.", role: "Options Trader, Mumbai" },
            { quote: "Hindi mein sab samajh aaya. Mujhe coding nahi aati par strategy bana li 5 minute mein. Dashboard bohot sundar hai.", name: "Priya M.", role: "Swing Trader, Ahmedabad" },
            { quote: "L&T engineer ne banaya hai toh bharosa hai. Security dekh ke dil khush ho gaya. 97% test coverage \u2014 koi aur nahi karta.", name: "Amit K.", role: "F&O Trader, Delhi" },
          ].map((t) => (
            <GlassmorphismCard key={t.name}>
              <div className="flex gap-0.5 mb-3">
                {Array.from({ length: 5 }).map((_, i) => <Star key={i} className="h-4 w-4 fill-accent-gold text-accent-gold" />)}
              </div>
              <p className="text-sm italic text-muted-foreground mb-4">&ldquo;{t.quote}&rdquo;</p>
              <div className="font-medium text-sm">{t.name}</div>
              <div className="text-xs text-muted-foreground">{t.role}</div>
            </GlassmorphismCard>
          ))}
        </div>
      </Section>

      {/* ── SECTION 10: FINAL CTA ────────────────────────────────────── */}
      <Section className="text-center bg-gradient-to-b from-transparent via-accent-blue/[0.03] to-transparent">
        <h2 className="text-3xl md:text-4xl font-bold mb-4">Ready to Trade Like a Pro?</h2>
        <p className="text-muted-foreground mb-8 max-w-lg mx-auto">
          Join 4,000+ traders using India&apos;s fastest bridge. Start free today. No credit card required.
        </p>
        <CTA text="Start Free \u2014 7 Day Trial" large />
      </Section>
    </>
  );
}
