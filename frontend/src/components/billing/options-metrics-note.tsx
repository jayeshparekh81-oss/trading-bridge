"use client";

/**
 * The mandatory honesty note beside an OPTIONS plan feature.
 *
 * ⚠️ WHY THIS EXISTS: every certified performance number we publish is
 * FUTURES-basis (NRML). A tier that advertises OPTIONS next to those numbers,
 * with no note, invites a customer to read futures-derived drawdown/win-rate as
 * if it described options. This renders automatically wherever a plan mentions
 * options, so the guard is in place BEFORE any tier starts advertising them.
 *
 * Copy comes from `@/lib/risk-labels` — the same single source as the risk
 * legend, so the two can never drift apart.
 */

import { Info } from "lucide-react";
import { OPTIONS_TIER_NOTE, mentionsOptions } from "@/lib/risk-labels";
import { cn } from "@/lib/utils";

interface Props {
  /** Any feature strings for this plan (bullets, segment labels, …). */
  features?: readonly (string | null | undefined)[] | null;
  /** Force-render regardless of detection (for a segment column that IS options). */
  force?: boolean;
  className?: string;
}

export function OptionsMetricsNote({ features, force, className }: Props) {
  if (!force && !mentionsOptions(features)) return null;

  return (
    <p
      data-testid="options-metrics-note"
      className={cn(
        "text-[10px] text-amber-300/85 leading-relaxed flex gap-1.5",
        className,
      )}
    >
      <Info className="h-3 w-3 shrink-0 mt-px" aria-hidden />
      <span>{OPTIONS_TIER_NOTE}</span>
    </p>
  );
}
