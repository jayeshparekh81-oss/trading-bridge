"use client";

import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface ProgressStepperProps {
  /** 1-indexed; total is 5 even though step 5 is the redirect target. */
  current: 1 | 2 | 3 | 4 | 5;
}

const LABELS = ["Goal", "Setup", "Preview", "Run", "Result"];

export function ProgressStepper({ current }: ProgressStepperProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span className="font-medium text-foreground">
          Step {current} of 5
        </span>
        <span>{LABELS[current - 1]}</span>
      </div>
      <div className="flex items-center gap-1.5">
        {LABELS.map((label, idx) => {
          const stepNum = idx + 1;
          const isDone = stepNum < current;
          const isActive = stepNum === current;
          return (
            <div key={label} className="flex-1 flex items-center gap-1.5">
              <div
                className={cn(
                  "h-1.5 flex-1 rounded-full transition-colors",
                  isDone && "bg-accent-blue",
                  isActive && "bg-accent-blue/60",
                  !isDone && !isActive && "bg-white/[0.06]",
                )}
              />
              {stepNum < LABELS.length ? (
                <div
                  className={cn(
                    "size-4 rounded-full grid place-items-center text-[9px] font-semibold",
                    isDone && "bg-accent-blue text-white",
                    isActive && "bg-accent-blue/20 text-accent-blue border border-accent-blue/40",
                    !isDone && !isActive && "bg-white/[0.04] text-muted-foreground",
                  )}
                >
                  {isDone ? <Check className="h-2.5 w-2.5" /> : stepNum}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
