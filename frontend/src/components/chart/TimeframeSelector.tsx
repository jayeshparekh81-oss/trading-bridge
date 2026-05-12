/**
 * TimeframeSelector — button group matching the backend allowlist.
 *
 * Supported values match :data:`SUPPORTED_TIMEFRAMES` in
 * ``@/lib/chart/types``. Backend rejects 3m and 30m for historical
 * (see backend PATCH_INSTRUCTIONS_INDICATORS.md §8) so we don't
 * expose them in the UI.
 *
 * Day-5 minimum: five buttons in a row. Day-4 polish may swap this
 * for a shadcn ``<Tabs>`` if the visual treatment needs it.
 */

"use client";

import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { SUPPORTED_TIMEFRAMES, type Timeframe } from "@/lib/chart/types";
import { cn } from "@/lib/utils";

const LABEL: Record<Timeframe, string> = {
  "1m": "1m",
  "3m": "3m",
  "5m": "5m",
  "15m": "15m",
  "30m": "30m",
  "1h": "1h",
  "1d": "1D",
};

export interface TimeframeSelectorProps {
  value: Timeframe;
  onChange: (value: Timeframe) => void;
  className?: string;
}

export function TimeframeSelector({
  value,
  onChange,
  className,
}: TimeframeSelectorProps) {
  // Overnight #2 / Phase 4 — on mobile (< md, where the row may not
  // fit horizontally) the container becomes scrollable. We auto-
  // scroll the currently-selected button into view so the user
  // doesn't have to swipe to find their current selection.
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const selectedRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    const btn = selectedRef.current;
    if (!btn) return;
    if (typeof btn.scrollIntoView !== "function") return;
    btn.scrollIntoView({ block: "nearest", inline: "center" });
  }, [value]);

  return (
    <div
      role="radiogroup"
      aria-label="Timeframe"
      ref={scrollRef}
      className={cn(
        // Mobile: horizontal scroll, hide the bar so it doesn't
        // crowd the chart (chrome scrollbar is ugly on this small
        // strip). Desktop: regular inline-flex, no scroll needed
        // since 5 buttons fit easily.
        "flex max-w-full items-center gap-1 overflow-x-auto scrollbar-none md:inline-flex md:overflow-visible",
        className,
      )}
      data-testid="timeframe-selector"
    >
      {SUPPORTED_TIMEFRAMES.map((tf) => {
        const selected = tf === value;
        return (
          <Button
            key={tf}
            ref={selected ? selectedRef : undefined}
            type="button"
            variant={selected ? "default" : "outline"}
            size="sm"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(tf)}
            data-testid={`timeframe-${tf}`}
            className="shrink-0"
          >
            {LABEL[tf]}
          </Button>
        );
      })}
    </div>
  );
}
