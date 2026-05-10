"use client";

import { Layers, Shield, Target, Sparkles } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GOAL_PRESETS, type BeginnerGoal } from "./presets";

interface StepPresetProps {
  goal: BeginnerGoal;
  stopLossPercent: number;
  targetPercent: number;
  onChange: (next: { stopLossPercent: number; targetPercent: number }) => void;
}

const SL_OPTIONS = [0.5, 1, 2, 3];
const TARGET_OPTIONS = [1, 2, 3, 5];

export function StepPreset({
  goal,
  stopLossPercent,
  targetPercent,
  onChange,
}: StepPresetProps) {
  const preset = GOAL_PRESETS[goal];

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <h2 className="text-xl font-semibold">Auto-setup tayyar hai</h2>
        <p className="text-sm text-muted-foreground">
          Aapke goal ke hisaab se humne yeh indicators choose kiye. SL aur
          Target adjust kar sakte ho.
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
          <div className="space-y-2">
            {preset.indicators.map((ind) => (
              <div
                key={ind.id}
                className="flex items-center justify-between gap-3 rounded-md bg-white/[0.02] border border-white/[0.04] px-3 py-2"
              >
                <div>
                  <div className="text-sm font-medium">{ind.label}</div>
                  <div className="text-[11px] text-muted-foreground font-mono">
                    {ind.id} · period={ind.params.period}
                  </div>
                </div>
                <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                  {ind.type}
                </span>
              </div>
            ))}
          </div>
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
