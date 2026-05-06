"use client";

import { Loader2, AlertTriangle, PlayCircle } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";

interface StepRunProps {
  state: "idle" | "submitting" | "error";
  error: string | null;
  onSubmit: () => void;
  onRetry: () => void;
}

export function StepRun({ state, error, onSubmit, onRetry }: StepRunProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <h2 className="text-xl font-semibold">Backtest chalao</h2>
        <p className="text-sm text-muted-foreground">
          Strategy save hogi aur historical data pe test hogi. Result agle
          page pe milega.
        </p>
      </div>

      <GlassmorphismCard hover={false}>
        {state === "submitting" ? (
          <div className="text-center py-10 space-y-4">
            <Loader2 className="h-10 w-10 text-accent-blue mx-auto animate-spin" />
            <div className="space-y-1">
              <h3 className="font-semibold">Strategy save ho rahi hai...</h3>
              <p className="text-xs text-muted-foreground">
                Bas thoda ruko — backtest result agle page pe khulega.
              </p>
            </div>
          </div>
        ) : state === "error" ? (
          <div className="text-center py-10 space-y-4">
            <AlertTriangle className="h-10 w-10 text-loss mx-auto" />
            <div className="space-y-1">
              <h3 className="font-semibold">Save nahi ho payi</h3>
              <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                {error ?? "Kuch toh galat hua. Phir se try karo."}
              </p>
            </div>
            <GlowButton size="sm" onClick={onRetry}>
              Phir se try karo
            </GlowButton>
          </div>
        ) : (
          <div className="text-center py-10 space-y-4">
            <div className="size-14 rounded-full bg-accent-blue/15 text-accent-blue grid place-items-center mx-auto">
              <PlayCircle className="h-7 w-7" />
            </div>
            <div className="space-y-1">
              <h3 className="font-semibold">Sab tayyar hai</h3>
              <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                Niche button dabaao — strategy save hogi aur backtest
                automatically chalega.
              </p>
            </div>
            <GlowButton size="lg" onClick={onSubmit}>
              <PlayCircle className="h-5 w-5 mr-2" />
              Run Backtest
            </GlowButton>
          </div>
        )}
      </GlassmorphismCard>
    </div>
  );
}
