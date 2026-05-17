/**
 * IndicatorHelpButton — small "?" icon button that opens the
 * IndicatorDetailModal for a given slug. Owns the modal's open state
 * locally, so callers just drop in the button next to an indicator
 * name in the strategy editor.
 *
 * Renders nothing when the slug is unknown — safe to use even when
 * the registry doesn't have content for a particular indicator yet.
 */

"use client";

import { HelpCircle } from "lucide-react";
import { useState } from "react";

import { IndicatorDetailModal } from "./IndicatorDetailModal";
import { getIndicator } from "@/lib/indicators/registry";

export interface IndicatorHelpButtonProps {
  slug: string;
  /** Optional visual size override — defaults to 14px icon. */
  size?: number;
  /** Optional ARIA label override. Defaults to "Help for <indicator name>". */
  ariaLabel?: string;
}

export function IndicatorHelpButton({
  slug,
  size = 14,
  ariaLabel,
}: IndicatorHelpButtonProps) {
  const [open, setOpen] = useState(false);
  const ind = getIndicator(slug);

  if (!ind) return null;

  const label = ariaLabel ?? `Help for ${ind.name}`;
  return (
    <>
      <button
        type="button"
        aria-label={label}
        title={label}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen(true);
        }}
        data-testid="indicator-help-button"
        data-slug={slug}
        className="inline-flex items-center justify-center rounded-full p-0.5 text-neutral-500 hover:bg-white/5 hover:text-emerald-300"
      >
        <HelpCircle style={{ width: size, height: size }} aria-hidden="true" />
      </button>
      <IndicatorDetailModal
        open={open}
        slug={slug}
        onClose={() => setOpen(false)}
      />
    </>
  );
}
