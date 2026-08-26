"use client";

/**
 * Risk chip + educational legend for the three trading segments.
 *
 * DESIGN CONSTRAINT (not cosmetic — it is the honesty mechanism):
 * the chip must NOT look like a measured metric. So it renders:
 *   - no number, no "/100", no AnimatedNumber, no tabular-nums
 *   - a pill outline, not the rounded stat-tile used by certified numbers
 * See src/lib/risk-labels.ts for the full rationale.
 *
 * `RiskLegend` shows ALL THREE segments together. That is deliberate: the
 * marketplace API does not expose a strategy's instrument_type, so a single
 * chip there would be claiming something about a strategy we cannot verify.
 * The legend is educational — "here is what each segment is like" — not a
 * rating of the strategy being viewed.
 */

import { AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn, formatCurrency } from "@/lib/utils";
import {
  EDITORIAL_NOTE,
  MIN_CAPITAL_NOTE,
  RISK_SEGMENTS,
  RISK_TONE,
  SEGMENT_MIN_CAPITAL,
  SEGMENT_RISK,
  type RiskSegment,
} from "@/lib/risk-labels";

interface RiskChipProps {
  segment: RiskSegment;
  /** Prefix the chip with the segment name (used by the legend). */
  showSegmentName?: boolean;
  className?: string;
}

export function RiskChip({ segment, showSegmentName = false, className }: RiskChipProps) {
  const risk = SEGMENT_RISK[segment];
  return (
    <Badge
      data-testid={`risk-chip-${segment}`}
      data-risk-level={risk.level}
      className={cn(
        // Pill, uppercase, no numeric styling — must not read as a stat tile.
        "rounded-full uppercase text-[10px] tracking-wide font-semibold whitespace-nowrap",
        RISK_TONE[risk.level],
        className,
      )}
    >
      {showSegmentName ? `${risk.segmentLabel} · ${risk.label}` : risk.label}
    </Badge>
  );
}

interface RiskLegendProps {
  /**
   * When the customer has selected a segment whose metrics we do NOT have
   * (cash / options), pass it so the legend can subtly mark the active row.
   * This never changes what the labels say.
   */
  activeSegment?: RiskSegment;
  className?: string;
}

/**
 * Educational legend: all three segments, each with its label + one-line why,
 * followed by the EDITORIAL_NOTE as VISIBLE copy (never tooltip-only).
 */
export function RiskLegend({ activeSegment, className }: RiskLegendProps) {
  return (
    <div
      data-testid="risk-legend"
      className={cn(
        "rounded-lg border border-white/[0.06] bg-white/[0.02] p-3 space-y-2.5",
        className,
      )}
    >
      <div className="text-[11px] font-medium text-foreground/90">
        Segment ke hisaab se risk
      </div>

      <ul className="space-y-2">
        {RISK_SEGMENTS.map((seg) => {
          const risk = SEGMENT_RISK[seg];
          return (
            <li
              key={seg}
              data-testid={`risk-legend-row-${seg}`}
              className={cn(
                "flex items-start gap-2",
                activeSegment === seg && "opacity-100",
                activeSegment && activeSegment !== seg && "opacity-70",
              )}
            >
              <RiskChip segment={seg} showSegmentName className="shrink-0 mt-px" />
              <span className="text-[10px] text-muted-foreground leading-relaxed">
                {risk.why}{" "}
                {/* Minimum capital — plain inline guidance copy, deliberately
                    NOT a stat tile (no tile, no border, no numeric emphasis). */}
                <span
                  data-testid={`min-capital-${seg}`}
                  className="text-foreground/70 whitespace-nowrap"
                >
                  Minimum ~{formatCurrency(SEGMENT_MIN_CAPITAL[seg], { compact: true })}.
                </span>
              </span>
            </li>
          );
        })}
      </ul>

      {/* The honesty line — VISIBLE, not behind a tooltip. */}
      <p
        data-testid="risk-editorial-note"
        className="text-[10px] text-amber-300/80 leading-relaxed flex gap-1.5"
      >
        <AlertTriangle className="h-3 w-3 shrink-0 mt-px" aria-hidden />
        <span>
          {EDITORIAL_NOTE} Ye kisi ek strategy ki rating nahi hai — sirf segment
          ki nature batata hai.
        </span>
      </p>

      {/* Capital minimums are guidance too — say so, visibly, so they can't be
          read as a live broker margin. */}
      <p
        data-testid="min-capital-note"
        className="text-[10px] text-muted-foreground/80 leading-relaxed"
      >
        {MIN_CAPITAL_NOTE}
      </p>
    </div>
  );
}
