"use client";

import { motion } from "framer-motion";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";

/**
 * LegalPage — shared on-brand shell for the interim legal pages
 * (/terms, /privacy, /disclaimer, /sebi). These are HONEST INTERIM
 * SUMMARIES, not final binding documents — the banner says so, and the
 * content is drawn only from facts we know to be true about TRADETRI.
 * Real CA/lawyer-drafted content will replace these later.
 */

const SUPPORT_EMAIL = "jayeshparekh81@gmail.com";

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.5 } } };

interface LegalPageProps {
  /** First word of the title, rendered in the gold→green brand gradient (e.g. "Terms"). */
  accent: string;
  /** Remainder of the title (e.g. " of Service"). */
  rest: string;
  /** Phrase used in the interim banner (e.g. "Terms of Service"). */
  kind: string;
  children: React.ReactNode;
}

export function LegalPage({ accent, rest, kind, children }: LegalPageProps) {
  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="pt-24 pb-16 px-4 md:px-6">
      <div className="max-w-3xl mx-auto space-y-8">
        {/* Header */}
        <motion.div variants={fadeUp} className="text-center">
          <p className="text-[11px] font-mono tracking-[0.25em] text-accent-gold/70 uppercase mb-3">
            Glass Box · Transparent Algo Trading
          </p>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
            <span className="bg-gradient-to-b from-[#FFD700] to-[#00FF88] bg-clip-text text-transparent">
              {accent}
            </span>
            {rest}
          </h1>
        </motion.div>

        {/* Honest interim banner */}
        <motion.div variants={fadeUp}>
          <div className="rounded-xl border border-accent-gold/30 bg-accent-gold/10 px-4 py-3 text-sm text-foreground/90 leading-relaxed">
            <span className="font-semibold text-accent-gold">Interim summary.</span>{" "}
            This is a plain-language summary, not the final binding document. A detailed {kind} is being finalised. For any questions, email{" "}
            <a href={`mailto:${SUPPORT_EMAIL}`} className="text-accent-blue hover:underline">
              {SUPPORT_EMAIL}
            </a>
            .
          </div>
        </motion.div>

        {/* Body */}
        <motion.div variants={fadeUp}>
          <GlassmorphismCard hover={false} className="space-y-5 text-sm text-muted-foreground leading-relaxed">
            {children}
          </GlassmorphismCard>
        </motion.div>

        {/* Contact */}
        <motion.p variants={fadeUp} className="text-center text-sm text-muted-foreground">
          Questions? Email{" "}
          <a href={`mailto:${SUPPORT_EMAIL}`} className="text-accent-blue hover:underline font-medium">
            {SUPPORT_EMAIL}
          </a>
        </motion.p>

        {/* Risk disclaimer footer — consistent with the rest of the site */}
        <motion.p variants={fadeUp} className="text-[11px] leading-relaxed text-muted-foreground/55 text-center">
          Trading involves a substantial risk of capital loss. Past performance is not indicative of future results, and nothing here is investment advice. TRADETRI provides white-box strategies and makes no guaranteed-return claims. Trades are routed through your own exchange-registered broker, in line with SEBI&apos;s algo-trading framework.
        </motion.p>
      </div>
    </motion.div>
  );
}

export function LegalSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="font-semibold text-foreground text-[15px] mb-1.5">{title}</h2>
      <div className="space-y-2">{children}</div>
    </section>
  );
}
