"use client";

import { ShieldCheck, ShieldAlert, ShieldQuestion } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/**
 * Trust score is computed by the Phase 4 reliability engine after a
 * backtest runs. The badge reads from a strategy's ``strategy_json``
 * blob: when the blob carries a numeric ``trust_score`` field, the
 * pill renders that value with the appropriate colour. Otherwise the
 * pill shows "Not rated" so the user knows a backtest is needed.
 *
 * Threshold bands match Phase 4 / Phase 6 grade ranges:
 *   85-100 strong (green) | 70-84 ok (blue) | 55-69 risky (amber) |
 *   < 55 weak (red).
 */

interface TrustScoreBadgeProps {
  /** The strategy's stored DSL blob (may be ``null`` for legacy rows). */
  strategyJson: Record<string, unknown> | null;
  className?: string;
  /**
   * Opt-in subtle gold pulse on grade-A scores (>= 90). Off by default
   * so high-density list views don't strobe. Surfaces like the dashboard
   * hero and the backtest result page enable it for the dopamine hit.
   */
  pulseOnA?: boolean;
}

function extractTrustScore(blob: Record<string, unknown> | null): number | null {
  if (!blob) return null;
  const raw = blob["trust_score"];
  if (typeof raw === "number" && Number.isFinite(raw)) {
    return Math.max(0, Math.min(100, Math.round(raw)));
  }
  // Forward-compat: future builders may nest reliability under a known key.
  const nested = blob["reliability"];
  if (nested && typeof nested === "object") {
    const n = (nested as Record<string, unknown>)["trust_score"];
    if (typeof n === "number" && Number.isFinite(n)) {
      return Math.max(0, Math.min(100, Math.round(n)));
    }
  }
  return null;
}

export function TrustScoreBadge({
  strategyJson,
  className,
  pulseOnA = false,
}: TrustScoreBadgeProps) {
  const score = extractTrustScore(strategyJson);
  const isGradeA = score !== null && score >= 90;
  const pulseClass = pulseOnA && isGradeA ? "pulse-grade-a" : "";

  if (score === null) {
    return (
      <Badge
        className={cn(
          "bg-white/[0.03] text-muted-foreground border-white/[0.06] gap-1",
          className,
        )}
      >
        <ShieldQuestion className="h-3 w-3" />
        Trust: not rated
      </Badge>
    );
  }

  if (score >= 70) {
    return (
      <Badge
        className={cn(
          "bg-profit/15 text-profit border-profit/30 gap-1",
          // Grade-A pulse uses a warmer gold to read as "premium" — the
          // colour tint comes from the inline custom property so the
          // existing pill greens stay unchanged.
          pulseClass,
          className,
        )}
        style={
          isGradeA && pulseOnA
            ? ({ ["--pulse-color" as string]: "rgba(255, 196, 0, 0.5)" } as React.CSSProperties)
            : undefined
        }
      >
        <ShieldCheck className="h-3 w-3" />
        Trust {score}
        {isGradeA ? <span className="ml-0.5 text-[10px]">★</span> : null}
      </Badge>
    );
  }

  if (score >= 55) {
    return (
      <Badge
        className={cn(
          "bg-accent-blue/15 text-accent-blue border-accent-blue/30 gap-1",
          className,
        )}
      >
        <ShieldCheck className="h-3 w-3" />
        Trust {score}
      </Badge>
    );
  }

  return (
    <Badge
      className={cn(
        "bg-loss/15 text-loss border-loss/30 gap-1",
        className,
      )}
    >
      <ShieldAlert className="h-3 w-3" />
      Trust {score}
    </Badge>
  );
}
