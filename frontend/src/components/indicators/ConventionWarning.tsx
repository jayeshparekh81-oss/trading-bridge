/**
 * ConventionWarning — composable helper that surfaces the
 * Convention-varies tooltip on any UI surface (dropdown, modal,
 * strategy detail). Returns ``null`` when the slug isn't one of the
 * 6 Convention-varies indicators, so callers can render it
 * unconditionally.
 *
 * Three variants per Sprint 8d §2:
 *   - ``inline`` (default): an ⚠ icon + the existing Tooltip primitive
 *     (from ``@/components/ui/tooltip``). Hover/focus opens the
 *     ``tooltip_short`` (first-sentence chart-hover variant).
 *   - ``compact``: just the ⚠ icon, no tooltip (autosuggest contexts
 *     per spec §4 — no popover-on-popover noise).
 *   - ``full``: renders an inline block with the full 50-80 word
 *     ``tooltip_full`` text (the indicator detail modal variant).
 *
 * This is NOT a new tooltip primitive — it composes ``@base-ui/react``
 * via the existing ``Tooltip`` wrapper.
 */

"use client";

import { AlertTriangle } from "lucide-react";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { getConventionTooltip } from "@/lib/indicators/convention-tooltips";
import { cn } from "@/lib/utils";

export interface ConventionWarningProps {
  /** Indicator slug. Lookup is silent — returns null when not found. */
  slug: string;
  /** Display variant. See module docstring. */
  variant?: "inline" | "compact" | "full";
  /** Render the inline trigger as a plain ``<span>`` instead of the
   *  default ``<button>``. Required when the caller sits inside an
   *  interactive element (e.g. a clickable row ``<button>``) — nested
   *  buttons are invalid HTML and React logs hydration errors. The
   *  tooltip becomes hover-only; keyboard users still get the full
   *  text in the indicator detail modal. */
  nonInteractive?: boolean;
  /** Extra classes appended to the root element. */
  className?: string;
}

export function ConventionWarning({
  slug,
  variant = "inline",
  nonInteractive = false,
  className,
}: ConventionWarningProps) {
  const entry = getConventionTooltip(slug);
  if (!entry) return null;

  if (variant === "full") {
    return (
      <div
        data-testid="convention-warning-full"
        data-slug={slug}
        className={cn(
          "rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs leading-relaxed text-amber-100",
          className,
        )}
      >
        <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-amber-300">
          <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
          Convention varies
        </p>
        <p>{entry.tooltip_full}</p>
      </div>
    );
  }

  if (variant === "compact") {
    return (
      <span
        data-testid="convention-warning-compact"
        data-slug={slug}
        className={cn("inline-flex text-amber-400", className)}
        aria-label={`Convention varies: ${slug}`}
      >
        <AlertTriangle className="h-3 w-3" aria-hidden="true" />
      </span>
    );
  }

  return (
    <TooltipProvider delay={150}>
      <Tooltip>
        <TooltipTrigger
          render={nonInteractive ? <span role="img" /> : undefined}
          type={nonInteractive ? undefined : "button"}
          aria-label={`Convention varies: ${slug}`}
          className={cn(
            "inline-flex cursor-default items-center border-0 bg-transparent p-0 text-amber-400 hover:text-amber-300",
            className,
          )}
        >
          <AlertTriangle
            data-testid="convention-warning-inline"
            data-slug={slug}
            className="h-3 w-3"
            aria-hidden="true"
          />
        </TooltipTrigger>
        <TooltipContent
          className="max-w-xs whitespace-normal text-left"
          data-testid="convention-warning-tooltip"
        >
          <span className="mb-1 block font-semibold text-amber-200">
            Convention varies
          </span>
          <span className="block">{entry.tooltip_short}</span>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
