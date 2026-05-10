"use client";

/**
 * Warning Evidence Card — one row per Truth-engine warning string.
 *
 * Embedded inside ``StrategyTruthPanel``'s drill-down section. Click
 * surfaces the full evidence + fix steps in a
 * :class:`TruthDrillDownModal`. The card itself is presentational —
 * it owns no state and emits a single ``onClick`` event.
 */

import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  BUCKET_META,
  type DrillDownWarning,
  type WarningBucketId,
} from "./truth-drill-down-modal";

interface WarningEvidenceCardProps {
  bucket: WarningBucketId;
  message: string;
  onOpen: (warning: DrillDownWarning) => void;
}

export function WarningEvidenceCard({
  bucket,
  message,
  onOpen,
}: WarningEvidenceCardProps) {
  const meta = BUCKET_META[bucket];
  const Icon = meta.icon;
  const tone = severityTone(meta.severity);
  const oneLineSummary = summarise(message);

  return (
    <motion.button
      type="button"
      whileHover={{ scale: 1.01 }}
      whileTap={{ scale: 0.99 }}
      onClick={() => onOpen({ bucket, message })}
      className={cn(
        "w-full text-left rounded-md border p-3 transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-blue/40",
        tone.bg,
      )}
    >
      <div className="flex items-start gap-3">
        <Icon className={cn("h-4 w-4 shrink-0 mt-0.5", tone.icon)} />
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold uppercase tracking-wide">
              {meta.label}
            </span>
            <Badge className={cn("uppercase text-[10px]", tone.badge)}>
              {severityEmoji(meta.severity)} {meta.severity}
            </Badge>
          </div>
          <p
            className={cn(
              "text-[11px] leading-relaxed line-clamp-2",
              tone.text,
            )}
          >
            {oneLineSummary}
          </p>
        </div>
        <span
          className={cn(
            "shrink-0 inline-flex items-center gap-0.5 text-[10px] font-medium",
            tone.icon,
          )}
        >
          Details dekho
          <ArrowRight className="h-3 w-3" />
        </span>
      </div>
    </motion.button>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────

interface SeverityTone {
  bg: string;
  badge: string;
  icon: string;
  text: string;
}

function severityTone(sev: "critical" | "warning" | "info"): SeverityTone {
  switch (sev) {
    case "critical":
      return {
        bg: "bg-loss/[0.05] border-loss/25 hover:bg-loss/[0.08]",
        badge: "bg-loss/15 text-loss border-loss/30",
        icon: "text-loss",
        text: "text-loss/90",
      };
    case "warning":
      return {
        bg: "bg-yellow-500/[0.05] border-yellow-500/25 hover:bg-yellow-500/[0.08]",
        badge: "bg-yellow-500/15 text-yellow-200 border-yellow-500/30",
        icon: "text-yellow-300",
        text: "text-yellow-200/90",
      };
    case "info":
      return {
        bg: "bg-accent-blue/[0.05] border-accent-blue/25 hover:bg-accent-blue/[0.08]",
        badge: "bg-accent-blue/15 text-accent-blue border-accent-blue/30",
        icon: "text-accent-blue",
        text: "text-accent-blue/90",
      };
  }
}

function severityEmoji(sev: "critical" | "warning" | "info"): string {
  switch (sev) {
    case "critical":
      return "⚠️🚨";
    case "warning":
      return "⚠️";
    case "info":
      return "ℹ️";
  }
}

/** Truncate the warning string to its first sentence for the card
 *  preview. Full text is rendered in the drill-down modal. */
function summarise(message: string): string {
  const trimmed = message.trim();
  const firstSentence = trimmed.split(/[.;]\s/)[0];
  if (firstSentence.length === 0) return trimmed;
  if (firstSentence.length === trimmed.length) return trimmed;
  return `${firstSentence}.`;
}
