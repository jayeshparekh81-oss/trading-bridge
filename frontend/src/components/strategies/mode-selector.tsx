"use client";

import { useEffect, useState } from "react";
import { GraduationCap, Sparkles, Cpu } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Strategy authoring mode — controls how much detail the dashboard
 * surfaces and which builder flow lands when the user opens "Create".
 *
 *   beginner     — guided flow, minimal jargon, defaults baked in
 *   intermediate — the same flow with more knobs and explanations
 *   expert       — full StrategyJSON DSL access
 *
 * Persists to ``localStorage`` so the choice survives a refresh.
 */

export type StrategyMode = "beginner" | "intermediate" | "expert";

export const STRATEGY_MODE_STORAGE_KEY = "tb_strategy_mode";

const OPTIONS: ReadonlyArray<{
  value: StrategyMode;
  label: string;
  icon: typeof GraduationCap;
  blurb: string;
}> = [
  {
    value: "beginner",
    label: "Beginner",
    icon: GraduationCap,
    blurb: "Step-by-step. Defaults baked in.",
  },
  {
    value: "intermediate",
    label: "Intermediate",
    icon: Sparkles,
    blurb: "Same flow, more knobs.",
  },
  {
    value: "expert",
    label: "Expert",
    icon: Cpu,
    blurb: "Full DSL — bring your own conditions.",
  },
];

interface ModeSelectorProps {
  value?: StrategyMode;
  onChange?: (mode: StrategyMode) => void;
  className?: string;
}

/**
 * Hydration-safe mode selector. Reads the persisted mode after mount
 * (so SSR and the first client render agree) and writes back on
 * every change.
 */
export function ModeSelector({ value, onChange, className }: ModeSelectorProps) {
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

  return (
    <div className={cn("space-y-2", className)}>
      <div
        role="radiogroup"
        aria-label="Strategy mode"
        className="inline-flex rounded-lg border border-white/[0.06] bg-white/[0.02] p-1"
      >
        {OPTIONS.map(({ value: v, label, icon: Icon }) => {
          const isActive = hydrated && v === current;
          return (
            <button
              key={v}
              type="button"
              role="radio"
              aria-checked={isActive}
              onClick={() => pick(v)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                isActive
                  ? "bg-accent-blue/15 text-accent-blue"
                  : "text-muted-foreground hover:text-foreground hover:bg-white/[0.04]",
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          );
        })}
      </div>
      <p className="text-xs text-muted-foreground">{active.blurb}</p>
    </div>
  );
}
