"use client";

import { Target, Shield, TrendingDown } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { cn } from "@/lib/utils";
import {
  STOP_LOSS_RANGE,
  TARGET_RANGE,
  TRAILING_RANGE,
} from "./builder-types";

interface ExitBuilderProps {
  targetPercent: number;
  stopLossPercent: number;
  trailingEnabled: boolean;
  trailingPercent: number;
  onChange: (patch: {
    targetPercent?: number;
    stopLossPercent?: number;
    trailingEnabled?: boolean;
    trailingPercent?: number;
  }) => void;
}

export function ExitBuilder({
  targetPercent,
  stopLossPercent,
  trailingEnabled,
  trailingPercent,
  onChange,
}: ExitBuilderProps) {
  const targetIssue =
    targetPercent <= stopLossPercent
      ? "Target Stop Loss se bada hona chahiye."
      : null;

  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Target className="h-4 w-4 text-accent-blue" />
          <h2 className="font-semibold">Exit Rules</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <NumberField
            icon={<Target className="h-4 w-4 text-profit" />}
            label="Target %"
            value={targetPercent}
            min={TARGET_RANGE.min}
            max={TARGET_RANGE.max}
            step={TARGET_RANGE.step}
            onChange={(v) => onChange({ targetPercent: v })}
            error={targetIssue}
            help={`Profit book karne ka level. Range: ${TARGET_RANGE.min}–${TARGET_RANGE.max}%.`}
          />
          <NumberField
            icon={<Shield className="h-4 w-4 text-loss" />}
            label="Stop Loss %"
            value={stopLossPercent}
            min={STOP_LOSS_RANGE.min}
            max={STOP_LOSS_RANGE.max}
            step={STOP_LOSS_RANGE.step}
            onChange={(v) => onChange({ stopLossPercent: v })}
            help={`Maximum acceptable loss. Range: ${STOP_LOSS_RANGE.min}–${STOP_LOSS_RANGE.max}%.`}
          />
        </div>

        <div className="rounded-md bg-white/[0.02] border border-white/[0.04] p-3 space-y-2">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={trailingEnabled}
              onChange={(e) => onChange({ trailingEnabled: e.target.checked })}
              className="h-3.5 w-3.5 rounded border-white/[0.1] bg-white/[0.04] text-accent-blue focus:ring-accent-blue/40"
            />
            <span className="text-sm font-medium flex items-center gap-1.5">
              <TrendingDown className="h-3.5 w-3.5 text-accent-blue" />
              Enable Trailing Stop
            </span>
          </label>
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            Profit ke saath stop bhi upar aata hai. Bigger move pakadne ke
            liye useful.
          </p>
          {trailingEnabled ? (
            <NumberField
              icon={<TrendingDown className="h-4 w-4 text-accent-blue" />}
              label="Trailing Stop %"
              value={trailingPercent}
              min={TRAILING_RANGE.min}
              max={TRAILING_RANGE.max}
              step={TRAILING_RANGE.step}
              onChange={(v) => onChange({ trailingPercent: v })}
              help={`Range: ${TRAILING_RANGE.min}–${TRAILING_RANGE.max}%.`}
            />
          ) : null}
        </div>
      </div>
    </GlassmorphismCard>
  );
}


interface NumberFieldProps {
  icon: React.ReactNode;
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (next: number) => void;
  error?: string | null;
  help?: string;
}

function NumberField({
  icon,
  label,
  value,
  min,
  max,
  step,
  onChange,
  error,
  help,
}: NumberFieldProps) {
  function handleChange(raw: string) {
    if (raw.trim() === "") {
      onChange(min);
      return;
    }
    const num = Number(raw);
    if (Number.isNaN(num)) return;
    onChange(num);
  }

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-1.5">
        {icon}
        <label className="text-xs uppercase tracking-wide text-muted-foreground">
          {label}
        </label>
      </div>
      <input
        type="number"
        value={Number.isFinite(value) ? value : ""}
        min={min}
        max={max}
        step={step}
        onChange={(e) => handleChange(e.target.value)}
        className={cn(
          "w-full rounded-md px-2.5 py-1.5 text-sm",
          "bg-white/[0.02] border text-foreground",
          error
            ? "border-loss/50 focus:border-loss"
            : "border-white/[0.06] focus:border-accent-blue/50",
          "focus:outline-none focus:ring-2 focus:ring-accent-blue/15",
        )}
      />
      {error ? (
        <p className="text-[10px] text-loss">{error}</p>
      ) : help ? (
        <p className="text-[10px] text-muted-foreground">{help}</p>
      ) : null}
    </div>
  );
}
