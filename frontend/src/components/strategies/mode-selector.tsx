"use client";

import { useEffect, useState } from "react";
import { GraduationCap, Sparkles, Cpu } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/**
 * Strategy authoring mode — controls how much detail the dashboard
 * surfaces and which builder flow lands when the user opens "Create".
 *
 *   beginner     — guided flow, minimal jargon, defaults baked in
 *   intermediate — the same flow with more knobs and explanations
 *   expert       — full StrategyJSON DSL access
 *
 * Persists to ``localStorage`` so the choice survives a refresh; the
 * smart-default redirector at ``/strategies/new`` reads the same key.
 */

export type StrategyMode = "beginner" | "intermediate" | "expert";

export const STRATEGY_MODE_STORAGE_KEY = "tb_strategy_mode";

/** Number of strategies above which the new-user badges retire. The
 *  user has clearly graduated past needing "Start Here" prompts. */
const BADGE_HIDE_THRESHOLD = 6;

interface ModeOption {
  value: StrategyMode;
  label: string;
  icon: typeof GraduationCap;
  blurb: string;
  tooltip: string;
}

const OPTIONS: ReadonlyArray<ModeOption> = [
  {
    value: "beginner",
    label: "Beginner",
    icon: GraduationCap,
    blurb: "Step-by-step. Defaults baked in.",
    tooltip: "Step-by-step. Up to 5 indicators. Defaults baked in.",
  },
  {
    value: "intermediate",
    label: "Intermediate",
    icon: Sparkles,
    blurb: "Same flow, more knobs.",
    tooltip: "Full library. Custom AND conditions. Most users start here.",
  },
  {
    value: "expert",
    label: "Expert",
    icon: Cpu,
    blurb: "Full DSL — bring your own conditions.",
    tooltip: "DSL editor. All features. For advanced users.",
  },
];

interface ModeSelectorProps {
  value?: StrategyMode;
  onChange?: (mode: StrategyMode) => void;
  className?: string;
  /** When set, drives the "Start Here / Most Popular / Advanced"
   *  badges. ``count >= BADGE_HIDE_THRESHOLD`` hides all badges
   *  (user has graduated). ``undefined`` hides badges too — they're
   *  opt-in via this prop. */
  strategyCount?: number | null;
}

/**
 * Hydration-safe mode selector. Reads the persisted mode after mount
 * (so SSR and the first client render agree) and writes back on
 * every change.
 */
export function ModeSelector({
  value,
  onChange,
  className,
  strategyCount,
}: ModeSelectorProps) {
  const [internal, setInternal] = useState<StrategyMode>("beginner");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.localStorage.getItem(STRATEGY_MODE_STORAGE_KEY);
    if (stored === "beginner" || stored === "intermediate" || stored === "expert") {
      setInternal(stored);
    }
    setHydrated(true);
  }, []);

  const current: StrategyMode = value ?? internal;
  const active = OPTIONS.find((o) => o.value === current) ?? OPTIONS[0];

  function pick(next: StrategyMode) {
    if (value === undefined) setInternal(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STRATEGY_MODE_STORAGE_KEY, next);
    }
    onChange?.(next);
  }

  const showBadges =
    typeof strategyCount === "number" &&
    strategyCount < BADGE_HIDE_THRESHOLD;

  return (
    <div className={cn("space-y-2", className)}>
      <TooltipProvider delay={150}>
        <div
          role="radiogroup"
          aria-label="Strategy mode"
          className="inline-flex rounded-lg border border-white/[0.06] bg-white/[0.02] p-1"
        >
          {OPTIONS.map(({ value: v, label, icon: Icon, tooltip }) => {
            const isActive = hydrated && v === current;
            const badge = showBadges
              ? getBadgeFor(v, strategyCount as number)
              : null;
            return (
              <Tooltip key={v}>
                <TooltipTrigger
                  type="button"
                  role="radio"
                  aria-checked={isActive}
                  onClick={() => pick(v)}
                  className={cn(
                    "relative inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                    isActive
                      ? "bg-accent-blue/15 text-accent-blue"
                      : "text-muted-foreground hover:text-foreground hover:bg-white/[0.04]",
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {label}
                  {badge ? (
                    <span
                      className={cn(
                        "absolute -top-2 -right-1 text-[9px] uppercase tracking-wide font-semibold",
                        "px-1.5 py-0.5 rounded-sm border whitespace-nowrap",
                        badge.className,
                      )}
                    >
                      {badge.label}
                    </span>
                  ) : null}
                </TooltipTrigger>
                <TooltipContent side="bottom" sideOffset={8}>
                  {tooltip}
                </TooltipContent>
              </Tooltip>
            );
          })}
        </div>
      </TooltipProvider>
      <p className="text-xs text-muted-foreground">{active.blurb}</p>
    </div>
  );
}

interface BadgeSpec {
  label: string;
  className: string;
}

/** Per-mode badge for the new-user phase. Beginner's "Start Here"
 *  only fires when the user has *zero* strategies — once they have
 *  any, the most-popular/advanced labels carry the load until the
 *  whole row retires at the threshold. */
function getBadgeFor(
  mode: StrategyMode,
  count: number,
): BadgeSpec | null {
  switch (mode) {
    case "beginner":
      if (count === 0) {
        return {
          label: "Start Here",
          className: "text-emerald-300 bg-emerald-400/15 border-emerald-400/40",
        };
      }
      return null;
    case "intermediate":
      return {
        label: "Most Popular",
        className: "text-sky-300 bg-sky-400/15 border-sky-400/40",
      };
    case "expert":
      return {
        label: "Advanced",
        className: "text-purple-300 bg-purple-400/15 border-purple-400/40",
      };
  }
}
