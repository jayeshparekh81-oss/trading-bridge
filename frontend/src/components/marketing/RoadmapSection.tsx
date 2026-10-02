/**
 * RoadmapSection — landing-page "What ships when" section.
 *
 * Three-column glassmorphism card layout communicating what is live
 * today, what is in progress, and what comes later. No dates are
 * rendered or promised.
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

import { GlassmorphismCard } from "@/shared/ui/glassmorphism-card";
import { cn } from "@/shared/lib/utils";
import { publicCopy } from "@/lib/i18n/copy/public";
import { useCopy } from "@/lib/i18n/core";

type PhaseStatus = "live" | "near" | "far";

interface RoadmapPhase {
  status: PhaseStatus;
  badge: string;
  title: string;
  subtitle: string;
  items: string[];
}

type C = Record<keyof typeof publicCopy.dicts.en, string>;
function phases(c: C): RoadmapPhase[] {
  return [
    { status: "live", badge: c.road_live_badge, title: c.road_live_title, subtitle: c.road_live_sub,
      items: [c.road_live_1, c.road_live_2, c.road_live_3, c.road_live_4, c.road_live_5, c.road_live_6, c.road_live_7, c.road_live_8, c.road_live_9] },
    { status: "near", badge: c.road_near_badge, title: c.road_near_title, subtitle: c.road_near_sub, items: [c.road_near_1, c.road_near_2, c.road_near_3] },
    { status: "far", badge: c.road_far_badge, title: c.road_far_title, subtitle: c.road_far_sub, items: [c.road_far_1, c.road_far_2, c.road_far_3] },
  ];
}

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
  const { c } = useCopy(publicCopy);
  const PHASES = phases(c);

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
          {c.road_h2}
        </h2>
        <p className="text-muted-foreground text-center mb-12 max-w-2xl mx-auto">{c.road_sub}</p>

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
                      "rounded-full border px-2.5 py-0.5 text-10 font-semibold uppercase tracking-wide",
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
          {c.road_foot}
        </p>
      </div>
    </motion.section>
  );
}
