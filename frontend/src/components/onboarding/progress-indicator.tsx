"use client";

import { cn } from "@/lib/utils";

interface ProgressIndicatorProps {
  current: number;
  total?: number;
}

export function ProgressIndicator({ current, total = 5 }: ProgressIndicatorProps) {
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="flex items-center gap-1.5">
        {Array.from({ length: total }, (_, i) => i + 1).map((step) => (
          <span
            key={step}
            className={cn(
              "h-1.5 rounded-full transition-all",
              step === current
                ? "w-8 bg-accent-blue"
                : step < current
                  ? "w-3 bg-accent-blue/60"
                  : "w-3 bg-white/[0.08]",
            )}
            aria-hidden
          />
        ))}
      </div>
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
        Step {current} of {total}
      </p>
    </div>
  );
}
