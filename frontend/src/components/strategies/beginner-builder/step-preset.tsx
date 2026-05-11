"use client";

import { Layers, Shield, Target, Sparkles, AlertTriangle, HelpCircle } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  GOAL_PRESETS,
  PERIOD_MAX,
  PERIOD_MIN,
  indicatorDisplayLabel,
  validatePeriodOverride,
  type BeginnerGoal,
  type IndicatorPreset,
  type PeriodOverrides,
} from "./presets";

interface StepPresetProps {
  goal: BeginnerGoal;
  stopLossPercent: number;
  targetPercent: number;
  periodOverrides: PeriodOverrides;
  onChange: (next: { stopLossPercent: number; targetPercent: number }) => void;
  onPeriodChange: (indicatorId: string, raw: string) => void;
}

const SL_OPTIONS = [0.5, 1, 2, 3];
const TARGET_OPTIONS = [1, 2, 3, 5];

export function StepPreset({
  goal,
  stopLossPercent,
  targetPercent,
  periodOverrides,
  onChange,
  onPeriodChange,
}: StepPresetProps) {
  const preset = GOAL_PRESETS[goal];

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <h2 className="text-xl font-semibold">Auto-setup tayyar hai</h2>
        <p className="text-sm text-muted-foreground">
          Aapke goal ke hisaab se humne yeh indicators choose kiye. Period
          customize karna ho to edit karo. SL aur Target bhi adjust kar
          sakte ho.
        </p>
      </div>

      <GlassmorphismCard hover={false}>
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-accent-blue" />
            <h3 className="font-semibold text-sm">Indicators</h3>
            <span className="ml-auto text-xs text-muted-foreground">
              {preset.indicators.length} configured
            </span>
          </div>
          <TooltipProvider delay={150}>
            <div className="space-y-2">
              {preset.indicators.map((ind) => (
                <IndicatorRow
                  key={ind.id}
                  ind={ind}
                  rawOverride={periodOverrides[ind.id]}
                  onPeriodChange={onPeriodChange}
                  overrides={periodOverrides}
                />
              ))}
            </div>
          </TooltipProvider>
          <div className="rounded-md bg-accent-blue/5 border border-accent-blue/20 px-3 py-2">
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              <Sparkles className="inline h-3 w-3 text-accent-blue mr-1" />
              <span className="text-accent-blue font-medium">Why these?</span>{" "}
              {preset.entryHinglish}
            </p>
          </div>
        </div>
      </GlassmorphismCard>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <PercentPicker
          icon={<Shield className="h-4 w-4 text-loss" />}
          title="Stop Loss %"
          subtitle="Loss kitna afford kar sakte ho?"
          value={stopLossPercent}
          options={SL_OPTIONS}
          onChange={(v) => onChange({ stopLossPercent: v, targetPercent })}
        />
        <PercentPicker
          icon={<Target className="h-4 w-4 text-profit" />}
          title="Target %"
          subtitle="Profit ka goal kya hai?"
          value={targetPercent}
          options={TARGET_OPTIONS}
          onChange={(v) => onChange({ stopLossPercent, targetPercent: v })}
        />
      </div>
    </div>
  );
}


interface IndicatorRowProps {
  ind: IndicatorPreset;
  rawOverride: string | undefined;
  overrides: PeriodOverrides;
  onPeriodChange: (indicatorId: string, raw: string) => void;
}

/** One row in the preset's indicator list. The period field is the
 *  only editable control — type, source, and the id are baked into
 *  the preset and can't be tweaked in the Beginner flow. */
function IndicatorRow({
  ind,
  rawOverride,
  overrides,
  onPeriodChange,
}: IndicatorRowProps) {
  const error = validatePeriodOverride(rawOverride);
  const display = indicatorDisplayLabel(ind, overrides);
  // The shown value is the raw user string when present (so partial
  // edits like "12" don't snap mid-typing), otherwise the preset
  // default rendered as a string for ``<input type="number">``.
  const value =
    rawOverride !== undefined ? rawOverride : String(ind.params.period);
  const inputId = `beginner-period-${ind.id}`;
  return (
    <div
      className={
        "rounded-md bg-white/[0.02] border px-3 py-2 space-y-1.5 transition-colors " +
        (error ? "border-loss/40" : "border-white/[0.04]")
      }
    >
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <div className="text-sm font-medium">{display}</div>
          <div className="text-[11px] text-muted-foreground font-mono">
            {ind.id} · {ind.type}
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <label
            htmlFor={inputId}
            className="text-[11px] uppercase tracking-wide text-muted-foreground"
          >
            Period
          </label>
          <Input
            id={inputId}
            type="number"
            inputMode="numeric"
            min={PERIOD_MIN}
            max={PERIOD_MAX}
            step={1}
            value={value}
            placeholder={String(ind.params.period)}
            onChange={(e) => onPeriodChange(ind.id, e.target.value)}
            aria-invalid={error !== null}
            aria-describedby={error ? `${inputId}-error` : undefined}
            className="w-20 text-sm tabular-nums"
          />
          <Tooltip>
            <TooltipTrigger
              type="button"
              aria-label={`Allowed range for ${ind.label}`}
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              <HelpCircle className="h-3.5 w-3.5" />
            </TooltipTrigger>
            <TooltipContent side="top">
              Period ({PERIOD_MIN}-{PERIOD_MAX})
            </TooltipContent>
          </Tooltip>
        </div>
      </div>
      {error ? (
        <p
          id={`${inputId}-error`}
          className="text-[11px] text-loss inline-flex items-center gap-1"
          role="alert"
        >
          <AlertTriangle className="h-3 w-3" />
          {error}
        </p>
      ) : null}
    </div>
  );
}


interface PercentPickerProps {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  value: number;
  options: number[];
  onChange: (next: number) => void;
}

function PercentPicker({
  icon,
  title,
  subtitle,
  value,
  options,
  onChange,
}: PercentPickerProps) {
  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          {icon}
          <div>
            <h3 className="font-semibold text-sm">{title}</h3>
            <p className="text-[11px] text-muted-foreground">{subtitle}</p>
          </div>
        </div>
        <div className="grid grid-cols-4 gap-1.5">
          {options.map((opt) => {
            const selected = opt === value;
            return (
              <button
                key={opt}
                type="button"
                onClick={() => onChange(opt)}
                aria-pressed={selected}
                className={
                  "rounded-md px-2 py-2 text-sm font-medium transition-colors " +
                  (selected
                    ? "bg-accent-blue/20 text-accent-blue border border-accent-blue/40"
                    : "bg-white/[0.02] text-muted-foreground border border-white/[0.04] hover:bg-white/[0.04]")
                }
              >
                {opt}%
              </button>
            );
          })}
        </div>
      </div>
    </GlassmorphismCard>
  );
}
