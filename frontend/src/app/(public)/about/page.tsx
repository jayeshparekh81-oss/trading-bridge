"use client";

import { motion } from "framer-motion";
import { Building2, Landmark, Eye, ShieldCheck, Wallet, LineChart, ArrowRight } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Logo } from "@/components/logo";
import Link from "next/link";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.5 } } };

export default function AboutPage() {
  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="pt-24 pb-16 px-4 md:px-6">
      <div className="max-w-4xl mx-auto space-y-16">
        {/* Hero */}
        <motion.div variants={fadeUp} className="text-center">
          <div className="flex items-center justify-center gap-2 mb-6">
            <Logo variant="icon" width={44} height={44} priority />
            <Logo variant="wordmark" height={40} />
          </div>
          <p className="text-[11px] font-mono tracking-[0.25em] text-accent-gold/70 uppercase mb-3">
            Glass Box · Transparent Algo Trading
          </p>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight leading-[1.1]">
            Built by an{" "}
            <span className="bg-gradient-to-b from-[#FFD700] to-[#00FF88] bg-clip-text text-transparent">
              engineer
            </span>
            , not an influencer.
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto mt-5 leading-relaxed">
            TRADETRI is built by an ex-L&amp;T engineer with 24 years of engineering experience — bridges, power plants, and infrastructure millions depend on — now applied to transparent, white-box algo trading. Based in Vadodara, India.
          </p>
        </motion.div>

        {/* Founder */}
        <motion.div variants={fadeUp}>
          <GlassmorphismCard hover={false}>
            <div className="flex flex-col md:flex-row gap-8 items-center">
              <div className="h-32 w-32 rounded-full bg-gradient-to-br from-accent-blue to-accent-purple flex items-center justify-center text-5xl font-bold text-white shrink-0">JP</div>
              <div>
                <h2 className="text-2xl font-bold mb-2">Jayesh Parekh</h2>
                <p className="text-accent-blue font-medium mb-4">Founder &amp; Engineer · Ex-L&amp;T · 24 Years</p>
                <div className="space-y-3 text-muted-foreground">
                  <p>
                    For 24 years, I built bridges, power plants, and industrial infrastructure at L&amp;T — projects where failure was not an option. That same discipline shapes how I build software.
                  </p>
                  <p>
                    When I started trading, the platforms frustrated me: opaque black-box signals, needless complexity, and a constant ask to just trust them. Most retail traders are left guessing why a trade was taken or skipped.
                  </p>
                  <p>
                    So I built what I wanted to use — a transparent, white-box platform. Every signal carries a rule-based AI conviction score you can see, trades route through your own broker so your funds never leave it, and the track record is shown honestly. No courses, no hollow promises — just systems that work, and that show you how they work.
                  </p>
                </div>
              </div>
            </div>
          </GlassmorphismCard>
        </motion.div>

        {/* Mission */}
        <motion.div variants={fadeUp} className="text-center">
          <h2 className="text-3xl font-bold mb-4">Our Mission</h2>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto italic">
            &ldquo;Democratize algo-trading for India&apos;s retail traders — give the 95% the same caliber of transparent tools the top 5% already have.&rdquo;
          </p>
        </motion.div>

        {/* Highlights — TRUE facts only */}
        <motion.div variants={fadeUp} className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { icon: Building2, value: "24 yrs", label: "Engineering (Ex-L&T)", color: "text-accent-blue" },
            { icon: Landmark, value: "6", label: "Broker integrations", color: "text-profit" },
            { icon: Eye, value: "White-box", label: "Every signal scored", color: "text-accent-gold" },
            { icon: ShieldCheck, value: "SEBI-aware", label: "Algo framework", color: "text-accent-purple" },
          ].map((s) => (
            <GlassmorphismCard key={s.label} className="text-center py-6">
              <s.icon className={`h-6 w-6 mx-auto mb-2 ${s.color}`} />
              <div className="text-lg font-bold leading-tight">{s.value}</div>
              <div className="text-xs text-muted-foreground mt-1">{s.label}</div>
            </GlassmorphismCard>
          ))}
        </motion.div>

        {/* What TRADETRI is */}
        <motion.div variants={fadeUp}>
          <h2 className="text-2xl font-bold text-center mb-8">What TRADETRI actually is</h2>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              { icon: Eye, title: "White-box AI conviction", desc: "Every signal gets a transparent, rule-based conviction score (not deep-learning) and only trades when it clears the threshold — you see why each trade was taken or skipped." },
              { icon: Wallet, title: "Your broker, your funds", desc: "Trades route through your own registered broker. TRADETRI never holds your money." },
              { icon: LineChart, title: "Honest track record", desc: "Real results shown with risk next to return, and backtests clearly labelled hypothetical." },
            ].map((f) => (
              <GlassmorphismCard key={f.title}>
                <f.icon className="h-8 w-8 text-accent-blue mb-3" />
                <h3 className="font-semibold text-lg mb-2">{f.title}</h3>
                <p className="text-sm text-muted-foreground">{f.desc}</p>
              </GlassmorphismCard>
            ))}
          </div>
          <div className="text-center mt-8">
            <Link
              href="/showcase"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-accent-blue hover:underline"
            >
              Dekho verified Track Record →
            </Link>
          </div>
        </motion.div>

        {/* Timeline — honest, no fabricated metrics */}
        <motion.div variants={fadeUp}>
          <h2 className="text-2xl font-bold text-center mb-8">Our Journey</h2>
          <div className="space-y-6">
            {[
              { date: "Jan 2026", title: "The Idea", desc: "Frustrated with opaque, over-complex trading platforms. Decided to build one with L&T-grade engineering discipline." },
              { date: "Feb 2026", title: "Architecture", desc: "Transparent conviction scoring, a kill switch, and a multi-broker abstraction — designed from day one." },
              { date: "Mar 2026", title: "Backend", desc: "FastAPI + PostgreSQL + Redis, broker integrations, and the signal pipeline." },
              { date: "Apr 2026", title: "Frontend", desc: "A dark-mode, mobile-first dashboard with a glassmorphism design system." },
              { date: "May 2026", title: "Launch", desc: "Live on tradetri.com — paper trading, real broker connections, and honest track-record reporting. Collecting feedback, iterating." },
            ].map((item, i) => (
              <div key={i} className="flex gap-4">
                <div className="flex flex-col items-center">
                  <div className="h-3 w-3 rounded-full bg-accent-blue" />
                  {i < 4 && <div className="w-px flex-1 bg-border" />}
                </div>
                <div className="pb-6">
                  <span className="text-xs text-accent-blue font-medium">{item.date}</span>
                  <h3 className="font-semibold mt-0.5">{item.title}</h3>
                  <p className="text-sm text-muted-foreground mt-1">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Get in touch */}
        <motion.div variants={fadeUp} className="text-center">
          <GlassmorphismCard glow="blue" className="py-10">
            <h2 className="text-2xl font-bold mb-2">Questions or ideas?</h2>
            <p className="text-muted-foreground mb-6 max-w-md mx-auto">
              Feedback, partnership ideas, or just want to talk shop? We&apos;d love to hear from you.
            </p>
            <Link href="/contact" className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-white bg-gradient-to-r from-accent-blue to-accent-purple hover:shadow-[0_0_25px_rgba(59,130,246,0.4)] transition-all">
              Get in Touch <ArrowRight className="h-4 w-4" />
            </Link>
          </GlassmorphismCard>
        </motion.div>

        {/* Honest risk disclaimer */}
        <motion.p variants={fadeUp} className="text-[11px] leading-relaxed text-muted-foreground/55 max-w-3xl mx-auto text-center">
          Trading involves a substantial risk of capital loss. Past performance is not indicative of future results, and nothing here is investment advice. TRADETRI provides white-box strategies and makes no guaranteed-return claims. Trades are routed through your own exchange-registered broker, in line with SEBI&apos;s algo-trading framework.
        </motion.p>
      </div>
    </motion.div>
  );
}
