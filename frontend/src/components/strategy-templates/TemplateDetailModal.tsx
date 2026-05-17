/**
 * TemplateDetailModal — full template detail surfaced from a card.
 *
 * Displays description (en + hi if available), config preview,
 * indicators, capital + risk + complexity. CTA at the bottom mirrors
 * TemplateCard's state-gated clone button.
 *
 * For ``requires_options_builder=true`` rows: includes a payoff-
 * diagram placeholder section (the Phase 1 frontend doesn't render
 * actual payoff diagrams — that's Phase 7-8 — but the slot is here
 * so the future builder drops in without modal-shell rework).
 */

"use client";

import { Fragment } from "react";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { cn } from "@/lib/utils";
import {
  resolveCardState,
  type TemplateDetail,
} from "@/lib/strategy-templates/types";

export interface TemplateDetailModalProps {
  template: TemplateDetail | null;
  isLoading?: boolean;
  error?: string | null;
  onClose: () => void;
  onClone: (slug: string) => void;
  cloning?: boolean;
}

export function TemplateDetailModal({
  template,
  isLoading = false,
  error = null,
  onClose,
  onClone,
  cloning = false,
}: TemplateDetailModalProps) {
  // Render the modal shell only when there's something to show.
  // Backdrop click + Escape both close.
  if (!template && !isLoading && !error) return null;

  return (
    <div
      data-testid="template-detail-modal"
      className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 supports-backdrop-filter:backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto"
      >
        <GlassmorphismCard hover={false} className="relative">
          <button
            type="button"
            onClick={onClose}
            data-testid="template-detail-close"
            className="absolute top-4 right-4 p-2 rounded-full hover:bg-white/5 transition-colors"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>

          {isLoading && (
            <div className="py-12 text-center text-muted-foreground text-sm">
              Loading template…
            </div>
          )}

          {error && !isLoading && (
            <div className="py-12 text-center text-loss text-sm">
              {error}
            </div>
          )}

          {template && !isLoading && (
            <TemplateDetailBody
              template={template}
              onClone={onClone}
              cloning={cloning}
            />
          )}
        </GlassmorphismCard>
      </div>
    </div>
  );
}

function TemplateDetailBody({
  template,
  onClone,
  cloning,
}: {
  template: TemplateDetail;
  onClone: (slug: string) => void;
  cloning: boolean;
}) {
  const state = resolveCardState(template);
  const canClone = state === "active-equity";
  const cloneDisabledReason =
    state === "options-builder-required"
      ? "Options templates require the options builder (Phase 7-8). We'll notify you when it ships."
      : state === "inactive-equity-coming-soon"
      ? "Trading config is being finalised — available in a future release."
      : "";

  return (
    <div className="pr-8">
      <h2 className="text-xl font-bold mb-1" data-testid="template-detail-name">
        {template.name}
      </h2>
      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground mb-4">
        <span>{template.category}</span>
        <span>·</span>
        <span className="uppercase">{template.complexity}</span>
        <span>·</span>
        <span>{template.segment}</span>
        <span>·</span>
        <span>{template.timeframe}</span>
        <span>·</span>
        <span>₹{template.recommended_capital_inr.toLocaleString("en-IN")} suggested</span>
      </div>

      <section className="mb-4">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
          What it does
        </h3>
        <p className="text-sm leading-relaxed">{template.description_en}</p>
        {template.description_hi && (
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            {template.description_hi}
          </p>
        )}
      </section>

      {template.indicators_used.length > 0 && (
        <section className="mb-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
            Indicators
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {template.indicators_used.map((ind) => (
              <span
                key={ind}
                className="rounded-md border border-border bg-muted/40 px-2 py-0.5 text-xs"
              >
                {ind}
              </span>
            ))}
          </div>
        </section>
      )}

      {template.tags.length > 0 && (
        <section className="mb-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
            Tags
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {template.tags.map((t) => (
              <span
                key={t}
                className="rounded-full border border-accent-blue/30 bg-accent-blue/10 px-2 py-0.5 text-[10px] text-accent-blue"
              >
                {t}
              </span>
            ))}
          </div>
        </section>
      )}

      {state === "options-builder-required" && (
        <section
          className="mb-4 border border-dashed border-accent-purple/40 rounded-lg p-4 text-center text-muted-foreground"
          data-testid="template-detail-payoff-placeholder"
        >
          <div className="text-xs uppercase tracking-wide font-semibold text-accent-purple mb-1">
            Payoff Diagram
          </div>
          <p className="text-xs">
            Visualisation lands with the options builder in Phase 7-8.
          </p>
        </section>
      )}

      {canClone && Object.keys(template.config_json).length > 0 && (
        <section className="mb-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
            Config Preview
          </h3>
          <pre
            data-testid="template-detail-config-preview"
            className="bg-muted/40 border border-border rounded-md p-3 text-[11px] leading-tight overflow-x-auto max-h-48"
          >
            <code>{JSON.stringify(template.config_json, null, 2)}</code>
          </pre>
        </section>
      )}

      <div
        className={cn(
          "flex items-center justify-end gap-2 pt-4 border-t border-border",
        )}
      >
        {!canClone && (
          <p className="flex-1 text-xs text-muted-foreground">
            {cloneDisabledReason}
          </p>
        )}
        <Button
          disabled={!canClone || cloning}
          onClick={() => canClone && onClone(template.slug)}
          data-testid="template-detail-clone"
        >
          {cloning
            ? "Cloning…"
            : canClone
            ? "Clone & Use"
            : "Not Available"}
        </Button>
      </div>
    </div>
  );
}
