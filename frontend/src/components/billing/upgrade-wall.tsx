"use client";

/**
 * Phase 2 Billing B3.4 — reactive premium upgrade wall.
 *
 * Presentational only. It is rendered by a surface ONLY in reaction to a
 * backend signal — a 402 PLAN_REQUIRED (via ``useApi().paywalled``) or the
 * backtest response's explicit ``premium_gated`` flag. It is NEVER shown
 * proactively from ``plan_status``, so with the paywall flag OFF (no 402s,
 * ``premium_gated`` false) it stays dormant everywhere.
 */

import Link from "next/link";
import { Lock, Sparkles } from "lucide-react";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { cn } from "@/lib/utils";

interface UpgradeWallProps {
  /** What's locked, e.g. "Full analytics", "Trade history". */
  feature?: string;
  /** Sub-copy under the heading. */
  description?: string;
  /** ``section`` = standalone block (default); ``inline`` = compact, for a
   *  panel slot inside a grid. */
  variant?: "section" | "inline";
  /** CTA target. 402-driven walls pass the server's ``detail.upgrade_url``
   *  (B3.0 contract); defaults to ``/pricing``. */
  upgradeUrl?: string;
  className?: string;
}

export function UpgradeWall({
  feature = "This feature",
  description = "Upgrade to a paid plan to unlock it.",
  variant = "section",
  upgradeUrl = "/pricing",
  className,
}: UpgradeWallProps) {
  return (
    <GlassmorphismCard
      hover={false}
      className={cn(
        "flex flex-col items-center justify-center text-center",
        variant === "section" ? "p-8 gap-3" : "p-5 gap-2",
        className,
      )}
    >
      <div
        className={cn(
          "grid place-items-center rounded-full bg-accent-blue/10 text-accent-blue",
          variant === "section" ? "h-12 w-12" : "h-9 w-9",
        )}
      >
        <Lock className={variant === "section" ? "h-5 w-5" : "h-4 w-4"} />
      </div>
      <div className="space-y-1">
        <h3 className={cn("font-semibold", variant === "section" ? "text-base" : "text-sm")}>
          {feature} is a premium feature
        </h3>
        <p className="text-xs text-muted-foreground max-w-sm">{description}</p>
      </div>
      <Link
        href={upgradeUrl}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-lg border border-accent-blue/30",
          "bg-accent-blue/15 text-accent-blue font-medium transition-colors hover:bg-accent-blue/25",
          variant === "section" ? "px-4 py-2 text-sm" : "px-3 py-1.5 text-xs",
        )}
      >
        <Sparkles className={variant === "section" ? "h-4 w-4" : "h-3.5 w-3.5"} />
        Upgrade to unlock
      </Link>
    </GlassmorphismCard>
  );
}
