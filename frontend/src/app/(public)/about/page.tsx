"use client";

import { motion } from "framer-motion";
import { Zap, Shield, Code2, TestTube, Clock, Target, Heart, Users } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { AnimatedNumber } from "@/components/ui/animated-number";
import Link from "next/link";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.5 } } };

export default function AboutPage() {
  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="pt-24 pb-16 px-4 md:px-6">
      <div className="max-w-4xl mx-auto space-y-16">
        {/* Hero */}
        <motion.div variants={fadeUp} className="text-center">
          <h1 className="text-4xl md:text-5xl font-bold mb-4">The Story Behind TRADETRI</h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            From building India&apos;s real bridges to building India&apos;s fastest trading bridge.
          </p>
        </motion.div>

        {/* Founder */}
        <motion.div variants={fadeUp}>
          <GlassmorphismCard hover={false}>
            <div className="flex flex-col md:flex-row gap-8 items-center">
              <div className="h-32 w-32 rounded-full bg-gradient-to-br from-accent-blue to-accent-purple flex items-center justify-center text-5xl font-bold text-white shrink-0">JP</div>
              <div>
                <h2 className="text-2xl font-bold mb-2">Jayesh Parekh</h2>
                <p className="text-accent-blue font-medium mb-4">Founder &amp; Engineer | Ex-L&amp;T | 24 Years</p>
                <div className="space-y-3 text-muted-foreground">
                  <p>
                    For 24 years, I built bridges, power plants, and infrastructure at L&amp;T that millions of Indians depend on every day. Atal Setu, transmission lines, industrial facilities &mdash; each project demanded zero tolerance for failure.
                  </p>
                  <p>
                    When I started trading, I was shocked. The platforms were slow, insecure, and built for tech experts. 95% of retail traders were left behind &mdash; overwhelmed by complexity, losing money to latency, with no safety nets.
                  </p>
                  <p>
                    So I did what any L&amp;T engineer would do: I built something better. Not a flashy app with hollow promises &mdash; a real, tested, secure trading engine with 785 automated tests and 97% code coverage. The same quality standard I used for bridges that carry 100,000 vehicles a day.
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
            &ldquo;Democratize trading for the 95% of retail traders who lack access to professional-grade algorithmic trading tools.&rdquo;
          </p>
        </motion.div>

        {/* Stats */}
        <motion.div variants={fadeUp} className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { icon: TestTube, value: 785, label: "Tests Passing", color: "text-profit" },
            { icon: Shield, value: 97, label: "% Code Coverage", suffix: "%", color: "text-accent-blue" },
            { icon: Zap, value: 50, label: "ms Max Latency", prefix: "<", color: "text-accent-gold" },
            { icon: Code2, value: 15, label: "Security Layers", color: "text-accent-purple" },
          ].map((s) => (
            <GlassmorphismCard key={s.label} className="text-center py-6">
              <s.icon className={`h-6 w-6 mx-auto mb-2 ${s.color}`} />
              <div className="text-2xl font-bold">
                <AnimatedNumber value={s.value} prefix={s.prefix} suffix={s.suffix} />
              </div>
              <div className="text-xs text-muted-foreground mt-1">{s.label}</div>
            </GlassmorphismCard>
          ))}
        </motion.div>

        {/* Timeline */}
        <motion.div variants={fadeUp}>
          <h2 className="text-2xl font-bold text-center mb-8">Our Journey</h2>
          <div className="space-y-6">
            {[
              { date: "Jan 2026", title: "The Idea", desc: "Frustrated with slow, insecure trading platforms. Decided to build something worthy of L&T quality." },
              { date: "Feb 2026", title: "Architecture", desc: "Designed 15-layer security, kill switch system, multi-broker abstraction. 785 tests from day one." },
              { date: "Mar 2026", title: "Backend Complete", desc: "FastAPI + PostgreSQL + Redis. 48+ API endpoints. 97% code coverage. <50ms latency." },
              { date: "Apr 2026", title: "Frontend Launch", desc: "Hypnotic dark-mode dashboard. 17 pages. Glassmorphism design. Mobile-first." },
              { date: "May 2026", title: "Beta Launch", desc: "First 100 traders. Free for 3 months. Collecting feedback, iterating fast." },
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

        {/* Join */}
        <motion.div variants={fadeUp} className="text-center">
          <GlassmorphismCard glow="blue" className="py-10">
            <Users className="h-10 w-10 text-accent-blue mx-auto mb-4" />
            <h2 className="text-2xl font-bold mb-2">Join the Team</h2>
            <p className="text-muted-foreground mb-6 max-w-md mx-auto">
              We&apos;re building India&apos;s best trading platform. Looking for engineers who build things that matter.
            </p>
            <Link href="/contact" className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-white bg-gradient-to-r from-accent-blue to-accent-purple hover:shadow-[0_0_25px_rgba(59,130,246,0.4)] transition-all">
              Get in Touch
            </Link>
          </GlassmorphismCard>
        </motion.div>
      </div>
    </motion.div>
  );
}
