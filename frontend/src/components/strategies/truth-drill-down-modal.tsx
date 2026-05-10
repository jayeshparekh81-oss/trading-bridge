"use client";

/**
 * Truth Drill-Down Modal — per-warning evidence + contextual fix.
 *
 * Backend reality (post-discovery): the Phase 6 ``TruthReport`` ships
 * four warning buckets — ``fakeBacktestWarnings``,
 * ``overfittingWarnings``, ``executionWarnings``, ``costWarnings`` —
 * where each entry is a free-form Hinglish/English string that inlines
 * its own numeric evidence (e.g. "Risk-reward ratio 0.85 is below
 * 1.0…", "Out-of-sample result dropped 32.5 %"). There are no
 * structured per-warning fields like ``indicator_id`` or
 * ``gross_pnl`` — those would require modifying the Truth engine,
 * which the locked rules forbid.
 *
 * This modal therefore renders the warning string as the primary
 * evidence, the bucket category as the "what is this" frame, and the
 * matching :attr:`TruthReport.recommendedNextActions` (or a sensible
 * default) as the fix steps. The "Apply AI Doctor Fix" CTA emits a
 * Sonner toast pointing the user to the AI Doctor card already on
 * the same backtest page — a true scroll/pulse would require
 * modifying ``ai-doctor-card.tsx`` and that's out of scope here.
 */

import { useEffect } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  FlaskConical,
  Lightbulb,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  Wand2,
  X,
} from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { GlowButton } from "@/components/ui/glow-button";
import { cn } from "@/lib/utils";

// ── Public types (re-exported from the panel for convenience) ─────────

export type WarningBucketId =
  | "fake_backtest"
  | "overfitting"
  | "execution"
  | "cost";

export interface DrillDownWarning {
  bucket: WarningBucketId;
  /** The warning text exactly as the Truth engine produced it. */
  message: string;
}

export interface BucketMeta {
  id: WarningBucketId;
  /** Hinglish display name for the bucket. */
  label: string;
  /** "Yeh Kya Hai" — bucket-level description in Hinglish. */
  description: string;
  /** Severity tone for badges + accent border. */
  severity: "critical" | "warning" | "info";
  /** Lucide icon component for the modal header + card. */
  icon: React.ComponentType<{ className?: string }>;
  /** Hinglish next-step hint when ``recommendedNextActions`` is empty. */
  defaultFix: string;
}

export const BUCKET_META: Record<WarningBucketId, BucketMeta> = {
  fake_backtest: {
    id: "fake_backtest",
    label: "Fake-Backtest Pattern",
    description:
      "Backtest dikhne mein achha hai, par actual trading mein result alag aane ke chances. Statistics mein traps hain — high win rate but bigger losses, low trade count, weak profit factor.",
    severity: "critical",
    icon: ShieldAlert,
    defaultFix:
      "Backtest period extend karo, more candles do, ya entry conditions relax karo to gather statistically significant trade count.",
  },
  overfitting: {
    id: "overfitting",
    label: "Overfitting Risk",
    description:
      "Strategy past data pe over-tuned hai — slight parameter change ya nayi market conditions mein performance girne ke chances. Out-of-sample test mein zyada gap dikhta hai.",
    severity: "warning",
    icon: FlaskConical,
    defaultFix:
      "Walk-forward + Sensitivity toggle on karo Expert Builder mein. Parameter values pick karo jo range mein robust ho — single best in-sample tuning avoid karo.",
  },
  execution: {
    id: "execution",
    label: "Execution Assumptions",
    description:
      "Backtest mein optimistic assumptions hain — same-bar fills perfectly, koi slippage nahi, ya fees zero. Live trading mein ye assumptions hold nahi karenge.",
    severity: "warning",
    icon: Activity,
    defaultFix:
      "Cost settings mein realistic broker fees + slippage configure karo. Ambiguity mode ko 'conservative' rakho.",
  },
  cost: {
    id: "cost",
    label: "Cost Impact",
    description:
      "Brokerage + slippage charges strategy ka edge khaa rahe hain. Profit factor marginal hai — costs adjust karne ke baad, live mein profitable nahi.",
    severity: "critical",
    icon: TrendingDown,
    defaultFix:
      "Strategy edge low hai — target/stop ratios adjust karo, ya frequency reduce karo. Lower-cost broker option dekho.",
  },
};

// ── Component ─────────────────────────────────────────────────────────

interface TruthDrillDownModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  warning: DrillDownWarning | null;
  /** Recommended next actions from the Truth report — passed through
   *  so the modal can show contextual fix steps without re-fetching. */
  recommendedNextActions: string[];
}

export function TruthDrillDownModal({
  open,
  onOpenChange,
  warning,
  recommendedNextActions,
}: TruthDrillDownModalProps) {
  // ESC key support — Base UI's Dialog already handles this, but
  // mirror an explicit listener for the keyboard test pattern the
  // codebase relies on (so a future test of `Escape` keydown works).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onOpenChange(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  if (!warning) return null;

  const meta = BUCKET_META[warning.bucket];
  const Icon = meta.icon;
  const fixHints =
    recommendedNextActions.length > 0
      ? recommendedNextActions
      : [meta.defaultFix];
  const tone = severityTone(meta.severity);

  function applyAiDoctorFix() {
    onOpenChange(false);
    toast.message("AI Doctor card scroll karo neeche ⬇️", {
      description:
        "Backtest page ke neeche AI Doctor card hai — usme is warning ka contextual fix milega. ✨",
      duration: 4500,
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className={cn("sm:max-w-lg space-y-4", tone.border)}
      >
        <DialogHeader>
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <Icon className={cn("h-4 w-4", tone.text)} />
                <DialogTitle className="text-base font-semibold">
                  {meta.label}
                </DialogTitle>
                <Badge className={cn("uppercase text-[10px]", tone.badge)}>
                  {severityEmoji(meta.severity)} {meta.severity}
                </Badge>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Phase 6 deterministic truth engine ne ye flag uthaaya hai.
              </p>
            </div>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => onOpenChange(false)}
              type="button"
              aria-label="Close drill-down"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </DialogHeader>

        <Section title="Yeh Kya Hai">
          <p className="text-sm leading-relaxed text-muted-foreground">
            {meta.description}
          </p>
        </Section>

        <Section title="Evidence">
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.18 }}
            className={cn(
              "rounded-md border p-3 text-sm leading-relaxed",
              tone.evidenceBg,
            )}
          >
            <p className="whitespace-pre-line">{warning.message}</p>
          </motion.div>
          <p className="text-[10px] text-muted-foreground italic">
            Numbers backtest run se aaye hain — Trust Score panel mein full
            metrics dekh sakte ho.
          </p>
        </Section>

        <Section title="Kaise Fix Karo">
          <ol className="space-y-2">
            {fixHints.map((step, idx) => (
              <li
                key={idx}
                className="text-sm leading-relaxed flex items-start gap-2"
              >
                <span className="shrink-0 size-5 rounded-full bg-accent-blue/15 text-accent-blue text-[10px] font-semibold grid place-items-center mt-0.5">
                  {idx + 1}
                </span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
          <div className="flex items-center justify-end gap-2 pt-2 flex-wrap">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onOpenChange(false)}
              type="button"
            >
              Cancel
            </Button>
            <GlowButton
              size="sm"
              onClick={applyAiDoctorFix}
              type="button"
            >
              <Wand2 className="h-3.5 w-3.5" />
              Apply AI Doctor Fix
            </GlowButton>
          </div>
        </Section>
      </DialogContent>
    </Dialog>
  );
}

// ── Sub-pieces ─────────────────────────────────────────────────────────

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-2">
      <h4 className="text-[10px] uppercase tracking-wide text-muted-foreground font-semibold flex items-center gap-1.5">
        {iconFor(title)}
        {title}
      </h4>
      {children}
    </section>
  );
}

function iconFor(title: string): React.ReactNode {
  switch (title) {
    case "Yeh Kya Hai":
      return <AlertTriangle className="h-3 w-3 text-amber-400" />;
    case "Evidence":
      return <Sparkles className="h-3 w-3 text-accent-blue" />;
    case "Kaise Fix Karo":
      return <Lightbulb className="h-3 w-3 text-profit" />;
    default:
      return null;
  }
}

interface SeverityTone {
  text: string;
  badge: string;
  border: string;
  evidenceBg: string;
}

function severityTone(sev: BucketMeta["severity"]): SeverityTone {
  switch (sev) {
    case "critical":
      return {
        text: "text-loss",
        badge: "bg-loss/15 text-loss border-loss/30",
        border: "border-loss/30",
        evidenceBg: "bg-loss/[0.08] border-loss/30",
      };
    case "warning":
      return {
        text: "text-yellow-300",
        badge: "bg-yellow-500/15 text-yellow-200 border-yellow-500/30",
        border: "border-yellow-500/30",
        evidenceBg: "bg-yellow-500/[0.06] border-yellow-500/25",
      };
    case "info":
      return {
        text: "text-accent-blue",
        badge: "bg-accent-blue/15 text-accent-blue border-accent-blue/30",
        border: "border-accent-blue/30",
        evidenceBg: "bg-accent-blue/[0.06] border-accent-blue/25",
      };
  }
}

function severityEmoji(sev: BucketMeta["severity"]): string {
  switch (sev) {
    case "critical":
      return "⚠️🚨";
    case "warning":
      return "⚠️";
    case "info":
      return "ℹ️";
  }
}
