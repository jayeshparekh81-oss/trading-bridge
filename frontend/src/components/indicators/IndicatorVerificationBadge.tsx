/**
 * IndicatorVerificationBadge — surfaces an indicator's verification
 * classification (Verified / Verified* / Best-effort / Convention
 * varies / Under review) per the spec in
 * ``docs/INDICATOR_LIBRARY_VERIFICATION_SPEC.md``.
 *
 * Distinct from the existing :file:`IndicatorBadge.tsx`, which surfaces
 * the indicator's *category* (Momentum / Trend / etc.). Both can render
 * on the same card.
 *
 * Reads from the build-time-static JSON at
 * ``frontend/src/data/indicator_library_badges.json`` (mirrored from
 * Sprint 8c's docs artifact). Returns ``null`` for slugs not in the
 * artifact — caller renders nothing in that case.
 */

"use client";

import { Shield, ShieldCheck, ShieldQuestion, AlertTriangle } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  getVerificationBadge,
  type VerificationBadgeKind,
} from "@/lib/indicators/verification";
import { cn } from "@/lib/utils";

interface BadgeVisual {
  icon: ReactNode;
  label: string;
  classes: string;
  help: string;
}

// Generic per-kind help text from spec §2. Per-indicator divergence_note
// is appended below the generic text inside the tooltip when present.
const BADGE_VISUAL: Record<VerificationBadgeKind, BadgeVisual> = {
  Verified: {
    icon: <ShieldCheck className="h-3 w-3" aria-hidden="true" />,
    label: "Verified",
    classes: "bg-profit/15 text-profit border-profit/30",
    help: "Cross-validated against TradingView Pine reference. Output matches industry convention.",
  },
  "Verified*": {
    icon: <ShieldCheck className="h-3 w-3" aria-hidden="true" />,
    label: "Verified*",
    classes: "bg-profit/15 text-profit border-profit/30",
    help: "Cross-validated; minor numerical drift on warmup bars only (does not affect signals on closed candles).",
  },
  "Best-effort": {
    icon: <Shield className="h-3 w-3" aria-hidden="true" />,
    label: "Best-effort",
    classes: "bg-accent-blue/15 text-accent-blue border-accent-blue/30",
    help: "Tier-B match — small numeric drift within tolerance; signal-equivalent on real data.",
  },
  "Convention varies": {
    icon: <AlertTriangle className="h-3 w-3" aria-hidden="true" />,
    label: "Convention varies",
    classes: "bg-amber-500/10 text-amber-300 border-amber-500/30",
    help: "Two valid conventions exist for this indicator. Our output matches TradingView; TA-Lib uses a different rule.",
  },
  "Under review": {
    icon: <ShieldQuestion className="h-3 w-3" aria-hidden="true" />,
    label: "Under review",
    classes: "bg-white/[0.03] text-muted-foreground border-white/[0.08]",
    help: "Not yet promoted from D-tier — internal verification gap; do not select for new strategies.",
  },
};

export interface IndicatorVerificationBadgeProps {
  /** Indicator slug (matches ``IndicatorMetadata.id`` from the backend). */
  slug: string;
  /**
   * When ``true`` the tooltip is suppressed and only the pill renders
   * — useful in autosuggest dropdowns where popover-on-popover would
   * be visual noise. Defaults to ``false``.
   */
  compact?: boolean;
  /** Additional classes appended to the pill. */
  className?: string;
}

export function IndicatorVerificationBadge({
  slug,
  compact = false,
  className,
}: IndicatorVerificationBadgeProps) {
  const entry = getVerificationBadge(slug);
  if (!entry) return null;

  const visual = BADGE_VISUAL[entry.badge];

  const pill = (
    <Badge
      data-testid="indicator-verification-badge"
      data-slug={slug}
      data-badge={entry.badge}
      className={cn(visual.classes, "gap-1 border", className)}
    >
      {visual.icon}
      {visual.label}
    </Badge>
  );

  if (compact) return pill;

  return (
    <TooltipProvider delay={150}>
      <Tooltip>
        <TooltipTrigger
          type="button"
          aria-label={`Verification: ${visual.label}`}
          className="inline-flex cursor-default border-0 bg-transparent p-0"
        >
          {pill}
        </TooltipTrigger>
        <TooltipContent
          className="max-w-xs whitespace-normal text-left"
          data-testid="indicator-verification-badge-tooltip"
        >
          <span className="block font-semibold mb-1">{visual.label}</span>
          <span className="block">{visual.help}</span>
          {entry.divergence_note ? (
            <span className="block mt-1 opacity-80">
              {entry.divergence_note}
            </span>
          ) : null}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
