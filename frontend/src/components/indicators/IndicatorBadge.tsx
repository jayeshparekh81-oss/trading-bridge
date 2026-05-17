/**
 * IndicatorBadge — visual pill showing an indicator's category with
 * a category-specific colour. Standalone: takes a category enum,
 * renders a styled span.
 *
 * Used by the IndicatorTooltip header, the glossary grid card, and
 * the IndicatorDetailModal title row. Doesn't open or trigger
 * anything — pure presentation.
 */

"use client";

import type { IndicatorCategory } from "@/lib/indicators/registry";

const CATEGORY_STYLES: Record<
  IndicatorCategory,
  { label: string; classes: string }
> = {
  momentum: {
    label: "Momentum",
    classes: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  },
  trend: {
    label: "Trend",
    classes: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  },
  volatility: {
    label: "Volatility",
    classes: "border-purple-500/30 bg-purple-500/10 text-purple-300",
  },
  volume: {
    label: "Volume",
    classes: "border-blue-500/30 bg-blue-500/10 text-blue-300",
  },
  rate: {
    label: "Rate",
    classes: "border-cyan-500/30 bg-cyan-500/10 text-cyan-300",
  },
  pattern: {
    label: "Pattern",
    classes: "border-pink-500/30 bg-pink-500/10 text-pink-300",
  },
  advanced: {
    label: "Advanced",
    classes: "border-red-500/30 bg-red-500/10 text-red-300",
  },
};

export interface IndicatorBadgeProps {
  category: IndicatorCategory;
  /** Optional override label — defaults to the canonical category label. */
  label?: string;
}

export function IndicatorBadge({ category, label }: IndicatorBadgeProps) {
  const style = CATEGORY_STYLES[category];
  return (
    <span
      data-testid="indicator-badge"
      data-category={category}
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${style.classes}`}
    >
      {label ?? style.label}
    </span>
  );
}
