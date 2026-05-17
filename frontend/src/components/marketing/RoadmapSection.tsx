/**
 * RoadmapSection — landing-page "What ships when" section.
 *
 * Three-column glassmorphism card layout communicating the
 * actually-available-today feature set, the near-term Phase F
 * deliverables (target June 9, 2026), and the post-launch Phase G+
 * roadmap (target August 2026). Honest framing — dates are targets,
 * not promises.
 *
 * Visual hierarchy by status:
 *   - ``live`` (today)        → profit-green glow + check icon + assertive badge
 *   - ``near`` (Phase F)      → accent-blue glow + clock icon + medium badge
 *   - ``far``  (Phase G+)     → no glow + sparkles icon + muted badge
 *
 * The progression communicates confidence-about-now and humility-
 * about-distant-future without aggressive "COMING SOON!" shouting.
 *
 * Rendered on the public landing page between SECTION 7 (Comparison)
 * and SECTION 8 (Pricing) — so the prospect sees what's shipped vs
 * what's planned BEFORE they see the pricing card.
 */

"use client";

import { useRef } from "react";
import { motion, useInView } from "framer-motion";
import { CheckCircle, Clock, Sparkles } from "lucide-react";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { cn } from "@/lib/utils";

type PhaseStatus = "live" | "near" | "far";

interface RoadmapPhase {
  status: PhaseStatus;
  badge: string;
  title: string;
  subtitle: string;
  items: string[];
}

const PHASES: RoadmapPhase[] = [
  {
    status: "live",
    badge: "Available Today",
    title: "Launch — May 18, 2026",
    subtitle: "Live now on tradetri.com",
    items: [
      "5+ indicators on chart with real-time data",
      "TradingView signal bridge → paper trading",
      "Multi-broker integration (Dhan live, Fyers active)",
      "AlgoMitra AI coach (Hinglish bhai-tone)",
      "Strategy Tester Panel with paper trade results",
      "Chart entry/exit markers from TV-forwarded signals",
      "10 regional language support",
    ],
  },
  {
    status: "near",
    badge: "Phase F",
    title: "Target — June 9, 2026",
    subtitle: "~3 weeks out",
    items: [
      "Native strategy builder (no-code, drag-drop)",
      "50+ indicators on chart (full chartable subset)",
      "Backtest engine (6-month historical, tick-by-tick)",
      "BACKTEST / PAPER / LIVE mode toggle",
    ],
  },
  {
    status: "far",
    badge: "Phase G+",
    title: "Target — August 2026",
    subtitle: "Post-SEBI empanelment",
    items: [
      "Live trading (post-SEBI empanelment)",
      "Strategy Marketplace (BLACK BOX mode)",
      "Mobile app",
      "Options Strategy Builder (25+ Indian strategies)",
    ],
  },
];

interface StatusVariant {
  Icon: typeof CheckCircle;
  iconClass: string;
  glow: "profit" | "blue" | "none";
  badgeClass: string;
  bulletClass: string;
  itemClass: string;
}

function statusVariant(status: PhaseStatus): StatusVariant {
  switch (status) {
    case "live":
      return {
        Icon: CheckCircle,
        iconClass: "text-profit",
        glow: "profit",
        badgeClass:
          "border-profit/40 bg-profit/10 text-profit",
        bulletClass: "bg-profit",
        itemClass: "text-foreground",
      };
    case "near":
      return {
        Icon: Clock,
        iconClass: "text-accent-blue",
        glow: "blue",
        badgeClass:
          "border-accent-blue/40 bg-accent-blue/10 text-accent-blue",
        bulletClass: "bg-accent-blue",
        itemClass: "text-foreground",
      };
    case "far":
      return {
        Icon: Sparkles,
        iconClass: "text-muted-foreground",
        glow: "none",
        badgeClass:
          "border-border bg-muted/40 text-muted-foreground",
        bulletClass: "bg-muted-foreground/60",
        itemClass: "text-muted-foreground",
      };
  }
}

export function RoadmapSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });

  return (
    <motion.section
      ref={ref}
      id="roadmap"
      initial={{ opacity: 0, y: 40 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.7, ease: "easeOut" }}
      className="py-20 md:py-28 px-4 md:px-6 bg-gradient-to-b from-transparent via-accent-blue/[0.02] to-transparent"
    >
      <div className="max-w-7xl mx-auto">
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">
          What Ships When
        </h2>
        <p className="text-muted-foreground text-center mb-12 max-w-2xl mx-auto">
          Honest roadmap — what&apos;s live today, what&apos;s coming
          next. No surprises, no vapor.
        </p>

        <div className="grid md:grid-cols-3 gap-6">
          {PHASES.map((phase) => {
            const v = statusVariant(phase.status);
            return (
              <GlassmorphismCard
                key={phase.title}
                glow={v.glow}
                className="flex flex-col"
              >
                <div className="flex items-start justify-between mb-4">
                  <v.Icon
                    className={cn("h-8 w-8", v.iconClass)}
                    aria-hidden="true"
                  />
                  <span
                    className={cn(
                      "rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                      v.badgeClass,
                    )}
                  >
                    {phase.badge}
                  </span>
                </div>
                <h3 className="font-semibold text-lg mb-1">
                  {phase.title}
                </h3>
                <p className="text-xs text-muted-foreground mb-4">
                  {phase.subtitle}
                </p>
                <ul className="space-y-2.5 text-sm flex-1">
                  {phase.items.map((item) => (
                    <li
                      key={item}
                      className="flex items-start gap-2"
                    >
                      <span
                        aria-hidden="true"
                        className={cn(
                          "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                          v.bulletClass,
                        )}
                      />
                      <span className={v.itemClass}>{item}</span>
                    </li>
                  ))}
                </ul>
              </GlassmorphismCard>
            );
          })}
        </div>

        <p className="text-center text-xs text-muted-foreground mt-8">
          Dates are targets, not promises. Built with L&amp;T engineer
          discipline — we ship when it&apos;s right.
        </p>
      </div>
    </motion.section>
  );
}
