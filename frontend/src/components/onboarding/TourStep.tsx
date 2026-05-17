/**
 * TourStep — single tooltip panel used by react-joyride via its
 * `tooltipComponent` prop. Owns the glassmorphism styling so the
 * tour matches the rest of the dashboard chrome instead of joyride's
 * default white box.
 *
 * Props arrive in joyride's `TooltipRenderProps` shape:
 *   - step.title / step.content come from the joyride steps array
 *   - tooltipProps spreads required ARIA + click-outside behaviour
 *   - primary/skip/close props are pre-bound by joyride
 *   - index / size give us "Step N of M"
 */

"use client";

import type { TooltipRenderProps } from "react-joyride";

import { Button } from "@/components/ui/button";

export function TourStep({
  index,
  size,
  step,
  primaryProps,
  skipProps,
  tooltipProps,
  isLastStep,
}: TooltipRenderProps) {
  const lang = (step.locale?.lang as "en" | "hi") ?? "hi";
  const nextLabel =
    typeof step.locale?.next === "string" ? step.locale.next : "Next";
  const skipLabel =
    typeof step.locale?.skip === "string" ? step.locale.skip : "Skip";
  const finishLabel =
    typeof step.locale?.last === "string" ? step.locale.last : "Finish";
  const stepOf = lang === "hi" ? `Step ${index + 1}/${size}` : `Step ${index + 1} of ${size}`;

  return (
    <div
      {...tooltipProps}
      data-testid="onboarding-tour-step"
      data-step-index={index}
      className="max-w-sm rounded-2xl border border-white/10 bg-neutral-900/85 supports-backdrop-filter:backdrop-blur-xl p-5 text-neutral-100 shadow-2xl shadow-black/60"
    >
      <div className="mb-2 text-[10px] font-medium uppercase tracking-wide text-emerald-400">
        {stepOf}
      </div>
      {step.title && (
        <h3
          data-testid="onboarding-tour-step-title"
          className="mb-2 text-base font-semibold text-neutral-100"
        >
          {step.title}
        </h3>
      )}
      <div
        data-testid="onboarding-tour-step-body"
        className="mb-5 text-sm leading-relaxed text-neutral-300"
      >
        {step.content}
      </div>
      <div className="flex items-center justify-between gap-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          {...skipProps}
          data-testid="onboarding-tour-skip"
          className="text-neutral-400 hover:bg-white/5"
        >
          {skipLabel}
        </Button>
        <Button
          type="button"
          size="sm"
          {...primaryProps}
          data-testid="onboarding-tour-next"
          className="bg-emerald-500 text-emerald-950 hover:bg-emerald-400"
        >
          {isLastStep ? finishLabel : nextLabel}
        </Button>
      </div>
    </div>
  );
}
