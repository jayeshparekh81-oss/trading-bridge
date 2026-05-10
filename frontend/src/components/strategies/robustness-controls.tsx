"use client";

/**
 * Robustness Test Controls — Expert Builder section.
 *
 * Two independent gates the Phase 4 reliability engine respects:
 *
 *   * Walk-forward analysis — partitions the candle stream into N
 *     equal segments, trains on a rolling head, tests on the next.
 *     Default ON (5 windows) because the cost is moderate and the
 *     out-of-sample signal is high-value.
 *   * Sensitivity analysis — perturbs every tunable param ±V around
 *     its base value and re-runs. Default OFF — adds ~21 extra
 *     backtests (~30 s) and only opted in for "deep analyse" runs.
 *
 * The component is presentational: it owns no state. The parent
 * (Expert Builder page) keeps the four values in its reducer and
 * passes them in via props; ``onChange`` emits a partial patch the
 * parent merges into its state.
 */

import { motion } from "framer-motion";
import { Beaker, ShieldCheck, Sparkles, Zap } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// ── Public types ──────────────────────────────────────────────────────

export interface RobustnessConfig {
  walkForwardEnabled: boolean;
  walkForwardWindows: number;
  sensitivityEnabled: boolean;
  /** Variation factor 0.05–0.25 → ±5 % to ±25 %. Stored as a fraction
   *  (e.g. 0.10) to match the backend's wire vocabulary. */
  sensitivityVariation: number;
}

export const DEFAULT_ROBUSTNESS: RobustnessConfig = {
  walkForwardEnabled: true,
  walkForwardWindows: 5,
  sensitivityEnabled: false,
  sensitivityVariation: 0.10,
};

const WINDOW_OPTIONS = [3, 5, 7, 10] as const;

// ── Component ─────────────────────────────────────────────────────────

interface RobustnessControlsProps {
  value: RobustnessConfig;
  onChange: (patch: Partial<RobustnessConfig>) => void;
}

export function RobustnessControls({
  value,
  onChange,
}: RobustnessControlsProps) {
  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-5">
        <header className="space-y-1">
          <h2 className="text-base font-semibold flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-accent-blue" />
            🛡️ Robustness Test Controls
          </h2>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Strategy ko different conditions mein test karo — overfitting
            aur fake-backtest patterns expose ho jaate hain.
          </p>
        </header>

        <WalkForwardSection
          enabled={value.walkForwardEnabled}
          windows={value.walkForwardWindows}
          onToggle={(walkForwardEnabled) =>
            onChange({ walkForwardEnabled })
          }
          onWindowsChange={(walkForwardWindows) =>
            onChange({ walkForwardWindows })
          }
        />

        <SensitivitySection
          enabled={value.sensitivityEnabled}
          variation={value.sensitivityVariation}
          onToggle={(sensitivityEnabled) =>
            onChange({ sensitivityEnabled })
          }
          onVariationChange={(sensitivityVariation) =>
            onChange({ sensitivityVariation })
          }
        />
      </div>
    </GlassmorphismCard>
  );
}

// ── Walk-forward section ──────────────────────────────────────────────

interface WalkForwardSectionProps {
  enabled: boolean;
  windows: number;
  onToggle: (enabled: boolean) => void;
  onWindowsChange: (n: number) => void;
}

function WalkForwardSection({
  enabled,
  windows,
  onToggle,
  onWindowsChange,
}: WalkForwardSectionProps) {
  return (
    <section
      className={cn(
        "rounded-lg border p-3 space-y-3 transition-colors",
        enabled
          ? "border-accent-blue/30 bg-accent-blue/5"
          : "border-white/[0.06] bg-white/[0.02]",
      )}
    >
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div className="space-y-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Sparkles
              className={cn(
                "h-4 w-4 shrink-0",
                enabled ? "text-accent-blue" : "text-muted-foreground",
              )}
            />
            <span className="text-sm font-medium">Walk-Forward Analysis</span>
            {enabled ? (
              <Badge className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 text-[10px] uppercase">
                On
              </Badge>
            ) : null}
          </div>
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            Strategy ko {windows} alag time windows mein test karta hai —
            out-of-sample reliability check.
          </p>
        </div>
        <ToggleSwitch
          ariaLabel="Toggle walk-forward analysis"
          enabled={enabled}
          onToggle={onToggle}
        />
      </header>

      {enabled ? (
        <div className="space-y-2">
          <label className="text-[10px] uppercase tracking-wide text-muted-foreground">
            Number of windows
          </label>
          <div className="flex items-center gap-2">
            {WINDOW_OPTIONS.map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => onWindowsChange(opt)}
                className={cn(
                  "rounded-md px-3 py-1.5 text-xs font-semibold transition-colors",
                  windows === opt
                    ? "bg-accent-blue/25 text-accent-blue border border-accent-blue/40"
                    : "bg-white/[0.04] text-muted-foreground border border-white/[0.06] hover:text-foreground",
                )}
              >
                {opt}
              </button>
            ))}
          </div>
          <p className="text-[10px] text-muted-foreground italic">
            Zyada windows = strict test, slower
          </p>
        </div>
      ) : null}
    </section>
  );
}

// ── Sensitivity section ───────────────────────────────────────────────

interface SensitivitySectionProps {
  enabled: boolean;
  variation: number;
  onToggle: (enabled: boolean) => void;
  onVariationChange: (v: number) => void;
}

function SensitivitySection({
  enabled,
  variation,
  onToggle,
  onVariationChange,
}: SensitivitySectionProps) {
  const variationPct = Math.round(variation * 100);
  return (
    <section
      className={cn(
        "rounded-lg border p-3 space-y-3 transition-colors",
        enabled
          ? "border-accent-purple/30 bg-accent-purple/5"
          : "border-white/[0.06] bg-white/[0.02]",
      )}
    >
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div className="space-y-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Beaker
              className={cn(
                "h-4 w-4 shrink-0",
                enabled ? "text-accent-purple" : "text-muted-foreground",
              )}
            />
            <span className="text-sm font-medium">Sensitivity Analysis</span>
            {enabled ? (
              <Badge className="bg-accent-purple/15 text-accent-purple border-accent-purple/30 text-[10px] uppercase">
                On
              </Badge>
            ) : null}
          </div>
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            Parameters ko slightly change karke test karta hai — overfitting
            detect karne ke liye.
          </p>
          <div className="inline-flex items-center gap-1.5 rounded-md bg-amber-500/10 border border-amber-400/30 px-2 py-1 mt-1">
            <Zap className="h-3 w-3 text-amber-400" />
            <span className="text-[10px] text-amber-400 leading-tight">
              ⚠️ Sensitivity slow hota hai (~30 seconds extra)
            </span>
          </div>
        </div>
        <ToggleSwitch
          ariaLabel="Toggle sensitivity analysis"
          enabled={enabled}
          onToggle={onToggle}
        />
      </header>

      {enabled ? (
        <div className="space-y-2">
          <label className="text-[10px] uppercase tracking-wide text-muted-foreground flex items-center justify-between">
            <span>Variation %</span>
            <span className="font-mono text-foreground">±{variationPct} %</span>
          </label>
          <input
            type="range"
            min={5}
            max={25}
            step={1}
            value={variationPct}
            onChange={(e) =>
              onVariationChange(Number(e.target.value) / 100)
            }
            className={cn(
              "w-full h-1.5 rounded-full appearance-none cursor-pointer",
              "bg-white/[0.06]",
              "[&::-webkit-slider-thumb]:appearance-none",
              "[&::-webkit-slider-thumb]:h-4",
              "[&::-webkit-slider-thumb]:w-4",
              "[&::-webkit-slider-thumb]:rounded-full",
              "[&::-webkit-slider-thumb]:bg-accent-purple",
              "[&::-webkit-slider-thumb]:cursor-pointer",
              "[&::-moz-range-thumb]:h-4",
              "[&::-moz-range-thumb]:w-4",
              "[&::-moz-range-thumb]:rounded-full",
              "[&::-moz-range-thumb]:bg-accent-purple",
              "[&::-moz-range-thumb]:border-0",
              "[&::-moz-range-thumb]:cursor-pointer",
            )}
          />
          <p className="text-[10px] text-muted-foreground italic">
            Higher variation = harder test
          </p>
        </div>
      ) : null}
    </section>
  );
}

// ── Toggle primitive ──────────────────────────────────────────────────

interface ToggleSwitchProps {
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  ariaLabel: string;
}

function ToggleSwitch({
  enabled,
  onToggle,
  ariaLabel,
}: ToggleSwitchProps) {
  return (
    <motion.button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={ariaLabel}
      whileTap={{ scale: 0.95 }}
      onClick={() => onToggle(!enabled)}
      className={cn(
        "relative h-6 w-11 shrink-0 rounded-full transition-colors",
        enabled ? "bg-accent-blue" : "bg-white/[0.08]",
      )}
    >
      <motion.span
        animate={{ x: enabled ? 22 : 2 }}
        transition={{ type: "spring", stiffness: 400, damping: 30 }}
        className="absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm"
      />
    </motion.button>
  );
}
