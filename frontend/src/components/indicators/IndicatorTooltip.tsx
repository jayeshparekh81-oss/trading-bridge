/**
 * IndicatorTooltip — wraps a child element with a hover/focus popover
 * that shows the indicator's name + one_liner. The popover is rendered
 * inline (not portal'd) so it sits in the same stacking context as
 * its trigger — keeps it simple in dense layouts.
 *
 * Reads language from localStorage's `tradetri_lang` key (same key the
 * onboarding tour + /help + /compliance/legal use). Defaults to 'hi'.
 *
 * If the slug is unknown (not in the registry), the component falls
 * back to rendering the children with no popover — avoids crashes
 * when the strategy editor references an indicator without content.
 */

"use client";

import { useEffect, useRef, useState } from "react";

import { IndicatorBadge } from "./IndicatorBadge";
import { getIndicator } from "@/lib/indicators/registry";

const LS_KEY_LANG = "tradetri_lang";

function readLang(): "en" | "hi" {
  if (typeof window === "undefined") return "hi";
  try {
    return window.localStorage.getItem(LS_KEY_LANG) === "en" ? "en" : "hi";
  } catch {
    return "hi";
  }
}

export interface IndicatorTooltipProps {
  slug: string;
  children: React.ReactNode;
}

export function IndicatorTooltip({ slug, children }: IndicatorTooltipProps) {
  const [open, setOpen] = useState(false);
  const [lang, setLang] = useState<"en" | "hi">("hi");
  const wrapRef = useRef<HTMLSpanElement | null>(null);

  useEffect(() => {
    setLang(readLang());
  }, []);

  const ind = getIndicator(slug);
  if (!ind) {
    // No content for this slug — render children passthrough.
    return <>{children}</>;
  }

  const oneLiner = lang === "hi" ? ind.one_liner_hi : ind.one_liner_en;

  return (
    <span
      ref={wrapRef}
      data-testid="indicator-tooltip"
      data-slug={slug}
      data-open={open ? "true" : "false"}
      className="relative inline-block"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children}
      {open && (
        <span
          role="tooltip"
          data-testid="indicator-tooltip-popover"
          className="pointer-events-none absolute left-1/2 top-full z-50 mt-2 w-72 -translate-x-1/2 rounded-lg border border-white/10 bg-neutral-900/95 supports-backdrop-filter:backdrop-blur-md p-3 text-xs leading-relaxed text-neutral-200 shadow-xl shadow-black/60"
        >
          <span className="mb-1 flex items-center gap-2">
            <span
              data-testid="indicator-tooltip-name"
              className="font-semibold text-neutral-100"
            >
              {ind.name}
            </span>
            <IndicatorBadge category={ind.category} />
          </span>
          <span
            data-testid="indicator-tooltip-oneliner"
            className="block text-neutral-300"
          >
            {oneLiner}
          </span>
        </span>
      )}
    </span>
  );
}
