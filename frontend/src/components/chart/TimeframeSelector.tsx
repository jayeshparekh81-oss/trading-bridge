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
  return (
    <div
      role="radiogroup"
      aria-label="Timeframe"
      className={cn("inline-flex items-center gap-1", className)}
      data-testid="timeframe-selector"
    >
      {SUPPORTED_TIMEFRAMES.map((tf) => {
        const selected = tf === value;
        return (
          <Button
            key={tf}
            type="button"
            variant={selected ? "default" : "outline"}
            size="sm"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(tf)}
            data-testid={`timeframe-${tf}`}
          >
            {LABEL[tf]}
          </Button>
        );
      })}
    </div>
  );
}
