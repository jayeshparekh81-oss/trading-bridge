"use client";

import { FileCode2, Wand2, Loader2 } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { cn } from "@/lib/utils";

const SUPPORTED_FEATURES = [
  "ta.ema",
  "ta.sma",
  "ta.rsi",
  "ta.macd",
  "ta.bb",
  "ta.atr",
  "ta.vwap",
  "crossover",
  "crossunder",
  "highest",
  "lowest",
];

const PLACEHOLDER_PINE = `//@version=5
// SPDX-License-Identifier: MIT
strategy("EMA crossover", overlay=true)

ema_fast = ta.ema(close, 9)
ema_slow = ta.ema(close, 21)

buy_signal = ta.crossover(ema_fast, ema_slow)
if buy_signal
    strategy.entry("Long", strategy.long)
`;

interface SourceInputProps {
  source: string;
  onSourceChange: (next: string) => void;
  onConvert: () => void;
  isLoading: boolean;
}

export function SourceInput({
  source,
  onSourceChange,
  onConvert,
  isLoading,
}: SourceInputProps) {
  const tooEmpty = source.trim().length === 0;
  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <FileCode2 className="h-4 w-4 text-accent-blue" />
          <h2 className="font-semibold">Pine Source</h2>
          <span className="ml-auto text-[11px] text-muted-foreground">
            v5 / v6 syntax
          </span>
        </div>

        <textarea
          value={source}
          onChange={(e) => onSourceChange(e.target.value)}
          placeholder={PLACEHOLDER_PINE}
          spellCheck={false}
          className={cn(
            "w-full rounded-md p-3 text-[12px]",
            "bg-black/40 border border-white/[0.04] text-foreground/90",
            "font-mono leading-snug",
            "focus:outline-none focus:border-accent-blue/50 focus:ring-2 focus:ring-accent-blue/15",
            "min-h-[400px] resize-y",
          )}
          aria-label="Pine script source"
        />

        <div className="flex items-center justify-between gap-3 flex-wrap">
          <p className="text-[11px] text-muted-foreground">
            <span className="text-accent-blue font-medium">Supported:</span>{" "}
            {SUPPORTED_FEATURES.join(", ")}
          </p>
          <GlowButton
            onClick={onConvert}
            disabled={tooEmpty || isLoading}
            size="md"
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Converting…
              </>
            ) : (
              <>
                <Wand2 className="h-4 w-4 mr-2" />
                Convert
              </>
            )}
          </GlowButton>
        </div>
      </div>
    </GlassmorphismCard>
  );
}
