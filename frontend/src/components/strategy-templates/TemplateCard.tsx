/**
 * TemplateCard — one card in the catalog gallery.
 *
 * Renders one of three visual states based on the template's flags:
 *
 *   - ``active-equity``: full glass card with profit-green
 *     "Active" badge and the "Clone & Use" CTA enabled.
 *   - ``inactive-equity-coming-soon``: muted card, amber
 *     "Coming Soon" badge, CTA disabled with tooltip.
 *   - ``options-builder-required``: violet-tinted card, "Options
 *     Phase 7-8" badge, CTA disabled with tooltip about the
 *     options builder.
 *
 * Compact summary (name, category, complexity, indicators, risk +
 * capital) — full detail surfaces via the detail modal.
 */

"use client";

import { Sparkles, Clock, Lock, IndianRupee, Layers, Tag } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { cn } from "@/lib/utils";
import {
  resolveCardState,
  type TemplateCardState,
  type TemplateSummary,
} from "@/lib/strategy-templates/types";

export interface TemplateCardProps {
  template: TemplateSummary;
  onView: (template: TemplateSummary) => void;
  onClone: (template: TemplateSummary) => void;
}

interface StateVariant {
  cardGlow: "profit" | "blue" | "none";
  badgeLabel: string;
  badgeClass: string;
  cloneLabel: string;
  cloneDisabled: boolean;
  cloneTooltip: string;
}

function variantFor(state: TemplateCardState): StateVariant {
  switch (state) {
    case "active-equity":
      return {
        cardGlow: "profit",
        badgeLabel: "Preview",
        badgeClass:
          "border-accent-blue/40 bg-accent-blue/10 text-accent-blue",
        cloneLabel: "Clone (preview only)",
        cloneDisabled: false,
        cloneTooltip:
          "Clone karke template bookmark karo aur config review karo. Full trading Phase 5 Strategy Builder ke saath unlock hoga.",
      };
    case "inactive-equity-coming-soon":
      return {
        cardGlow: "none",
        badgeLabel: "Coming Soon",
        badgeClass:
          "border-amber-500/40 bg-amber-500/10 text-amber-400",
        cloneLabel: "Coming Soon",
        cloneDisabled: true,
        cloneTooltip:
          "Trading config is being finalised — available in a future release.",
      };
    case "options-builder-required":
      return {
        cardGlow: "none",
        badgeLabel: "Options · Phase 7-8",
        badgeClass:
          "border-accent-purple/40 bg-accent-purple/10 text-accent-purple",
        cloneLabel: "Needs Options Builder",
        cloneDisabled: true,
        cloneTooltip:
          "Options strategies require the options builder (Phase 7-8). We'll notify you when it ships.",
      };
  }
}

function ComplexityBadge({
  complexity,
}: {
  complexity: TemplateSummary["complexity"];
}) {
  const styles: Record<TemplateSummary["complexity"], string> = {
    beginner: "border-emerald-500/30 text-emerald-400 bg-emerald-500/5",
    intermediate: "border-blue-500/30 text-blue-400 bg-blue-500/5",
    advanced: "border-orange-500/30 text-orange-400 bg-orange-500/5",
    expert: "border-red-500/30 text-red-400 bg-red-500/5",
  };
  return (
    <span
      className={cn(
        "rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        styles[complexity],
      )}
    >
      {complexity}
    </span>
  );
}

function RiskDot({ risk }: { risk: TemplateSummary["risk_level"] }) {
  const color = {
    low: "bg-profit",
    medium: "bg-amber-400",
    high: "bg-loss",
  }[risk];
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
      <span className={cn("h-1.5 w-1.5 rounded-full", color)} />
      {risk} risk
    </span>
  );
}

export function TemplateCard({
  template,
  onView,
  onClone,
}: TemplateCardProps) {
  const state = resolveCardState(template);
  const v = variantFor(state);

  return (
    <div
      data-testid={`template-card-${template.slug}`}
      data-state={state}
      className="h-full"
    >
    <GlassmorphismCard
      glow={v.cardGlow}
      className={cn(
        "flex flex-col gap-3 h-full",
        state !== "active-equity" && "opacity-90",
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <h3
          className="text-base font-semibold leading-tight"
          data-testid="template-card-name"
        >
          {template.name}
        </h3>
        <span
          className={cn(
            "shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide whitespace-nowrap",
            v.badgeClass,
          )}
        >
          {v.badgeLabel}
        </span>
      </div>

      {/* Category + complexity */}
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <Tag className="h-3 w-3" aria-hidden="true" />
          {template.category}
        </span>
        <span className="text-muted-foreground/40">·</span>
        <ComplexityBadge complexity={template.complexity} />
        <span className="text-muted-foreground/40">·</span>
        <span>{template.timeframe}</span>
      </div>

      {/* Description */}
      <p className="text-sm text-muted-foreground line-clamp-3 flex-1">
        {template.description_en}
      </p>

      {/* Indicators + risk + capital */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
        {template.indicators_used.length > 0 && (
          <span className="inline-flex items-center gap-1 text-muted-foreground">
            <Sparkles className="h-3 w-3" aria-hidden="true" />
            {template.indicators_used.slice(0, 3).join(", ")}
            {template.indicators_used.length > 3 && " …"}
          </span>
        )}
        <RiskDot risk={template.risk_level} />
        {template.recommended_capital_inr > 0 && (
          <span className="inline-flex items-center gap-0.5 text-muted-foreground">
            <IndianRupee className="h-3 w-3" aria-hidden="true" />
            {(template.recommended_capital_inr / 1000).toFixed(0)}K
          </span>
        )}
        {template.legs_count !== null && template.legs_count > 1 && (
          <span className="inline-flex items-center gap-1 text-muted-foreground">
            <Layers className="h-3 w-3" aria-hidden="true" />
            {template.legs_count}-leg
          </span>
        )}
      </div>

      {/* CTAs */}
      <div className="mt-1 flex gap-2">
        <Button
          variant="ghost"
          size="sm"
          className="flex-1"
          onClick={() => onView(template)}
          data-testid="template-card-view"
        >
          View Details
        </Button>
        <Button
          variant={state === "active-equity" ? "default" : "outline"}
          size="sm"
          className="flex-1"
          disabled={v.cloneDisabled}
          title={v.cloneTooltip || undefined}
          onClick={() => !v.cloneDisabled && onClone(template)}
          data-testid="template-card-clone"
        >
          {v.cloneDisabled && <Lock className="h-3 w-3 mr-1" />}
          {state === "active-equity" && (
            <Clock className="h-3 w-3 mr-1 opacity-0" aria-hidden="true" />
          )}
          {v.cloneLabel}
        </Button>
      </div>
    </GlassmorphismCard>
    </div>
  );
}
