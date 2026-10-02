"use client";

import { motion } from "framer-motion";
import { Building2, Landmark, Eye, ShieldCheck, Wallet, LineChart, ArrowRight } from "lucide-react";
import { GlassmorphismCard } from "@/shared/ui/glassmorphism-card";
import { Logo } from "@/components/logo";
import Link from "next/link";
import { publicCopy } from "@/lib/i18n/copy/public";
import { useCopy } from "@/lib/i18n/core";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.5 } } };

export default function AboutPage() {
  const { c } = useCopy(publicCopy);
  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="pt-24 pb-16 px-4 md:px-6">
      <div className="max-w-4xl mx-auto space-y-16">
        {/* Hero */}
        <motion.div variants={fadeUp} className="text-center">
          <div className="flex items-center justify-center gap-2 mb-6">
            <Logo variant="icon" width={44} height={44} priority />
            <Logo variant="wordmark" height={40} />
          </div>
          <p className="text-xs font-mono tracking-[0.25em] text-accent-gold/70 uppercase mb-3">
            {c.ab_eyebrow}
          </p>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight leading-[1.1]">
            {c.ab_h1_a}{" "}
            <span className="bg-gradient-to-b from-brand-gold to-brand-green bg-clip-text text-transparent">
              {c.ab_h1_b}
            </span>
            {c.ab_h1_c}
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto mt-5 leading-relaxed">{c.ab_lead}</p>
        </motion.div>

        {/* Founder */}
        <motion.div variants={fadeUp}>
          <GlassmorphismCard hover={false}>
            <div className="flex flex-col md:flex-row gap-8 items-center">
              <div className="h-32 w-32 rounded-full bg-gradient-to-br from-accent-blue to-accent-purple flex items-center justify-center text-5xl font-bold text-white shrink-0">JP</div>
              <div>
                <h2 className="text-2xl font-bold mb-2">{c.founder_name}</h2>
                <p className="text-accent-blue font-medium mb-4">{c.ab_role}</p>
                <div className="space-y-3 text-muted-foreground">
                  <p>{c.ab_p1}</p>
                  <p>{c.ab_p2}</p>
                  <p>{c.ab_p3}</p>
                </div>
              </div>
            </div>
          </GlassmorphismCard>
        </motion.div>

        {/* Mission */}
        <motion.div variants={fadeUp} className="text-center">
          <h2 className="text-3xl font-bold mb-4">{c.ab_mission_h2}</h2>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto italic">{c.ab_mission}</p>
        </motion.div>

        {/* Highlights — TRUE facts only */}
        <motion.div variants={fadeUp} className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { icon: Building2, value: c.ab_s1_v, label: c.ab_s1_l, color: "text-accent-blue" },
            { icon: Landmark, value: c.ab_s2_v, label: c.ab_s2_l, color: "text-profit" },
            { icon: Eye, value: c.ab_s3_v, label: c.ab_s3_l, color: "text-accent-gold" },
            { icon: ShieldCheck, value: c.ab_s4_v, label: c.ab_s4_l, color: "text-accent-purple" },
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
          <h2 className="text-2xl font-bold text-center mb-8">{c.ab_what_h2}</h2>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              { icon: Eye, title: c.ab_w1_t, desc: c.ab_w1_d },
              { icon: Wallet, title: c.ab_w2_t, desc: c.ab_w2_d },
              { icon: LineChart, title: c.ab_w3_t, desc: c.ab_w3_d },
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
              {c.see_proof}
            </Link>
          </div>
        </motion.div>

        {/* Timeline — honest, no fabricated metrics */}
        <motion.div variants={fadeUp}>
          <h2 className="text-2xl font-bold text-center mb-8">{c.ab_journey_h2}</h2>
          <div className="space-y-6">
            {[
              { date: "Jan 2026", title: c.ab_t1_t, desc: c.ab_t1_d },
              { date: "Feb 2026", title: c.ab_t2_t, desc: c.ab_t2_d },
              { date: "Mar 2026", title: c.ab_t3_t, desc: c.ab_t3_d },
              { date: "Apr 2026", title: c.ab_t4_t, desc: c.ab_t4_d },
              { date: "May 2026", title: c.ab_t5_t, desc: c.ab_t5_d },
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
            <h2 className="text-2xl font-bold mb-2">{c.ab_contact_h2}</h2>
            <p className="text-muted-foreground mb-6 max-w-md mx-auto">{c.ab_contact_p}</p>
            <Link href="/contact" className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-white bg-gradient-to-r from-accent-blue to-accent-purple hover:shadow-glow-profit transition-all">
              {c.ab_contact_cta} <ArrowRight className="h-4 w-4" />
            </Link>
          </GlassmorphismCard>
        </motion.div>

        {/* Honest risk disclaimer */}
        <motion.p variants={fadeUp} className="text-xs leading-relaxed text-muted-foreground/55 max-w-3xl mx-auto text-center">
          {c.risk_line}
        </motion.p>
      </div>
    </motion.div>
  );
}
