"use client";

import { ShieldCheck } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { cn } from "@/lib/utils";
import { RISK_RANGES, type RiskState } from "./builder-types";

interface RiskBuilderProps {
  risk: RiskState;
  onChange: (next: RiskState) => void;
}

export function RiskBuilder({ risk, onChange }: RiskBuilderProps) {
  function set<K extends keyof RiskState>(key: K, value: string) {
    onChange({ ...risk, [key]: value });
  }

  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-accent-blue" />
          <h2 className="font-semibold">Risk Caps</h2>
          <span className="ml-auto text-[11px] text-muted-foreground">
            All optional
          </span>
        </div>
        <p className="text-[11px] text-muted-foreground leading-relaxed">
          Khaali chhodoge to woh cap apply nahi hoga. Beginner-friendly
          tip: kam se kam Max Daily Loss ek baar zaroor set karo.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <RiskField
            label="Max Daily Loss %"
            help={`Range: ${RISK_RANGES.maxDailyLossPercent.min}–${RISK_RANGES.maxDailyLossPercent.max}%`}
            value={risk.maxDailyLossPercent}
            min={RISK_RANGES.maxDailyLossPercent.min}
            max={RISK_RANGES.maxDailyLossPercent.max}
            step={RISK_RANGES.maxDailyLossPercent.step}
            onChange={(v) => set("maxDailyLossPercent", v)}
          />
          <RiskField
            label="Max Trades / Day"
            help={`Range: ${RISK_RANGES.maxTradesPerDay.min}–${RISK_RANGES.maxTradesPerDay.max}`}
            value={risk.maxTradesPerDay}
            min={RISK_RANGES.maxTradesPerDay.min}
            max={RISK_RANGES.maxTradesPerDay.max}
            step={RISK_RANGES.maxTradesPerDay.step}
            onChange={(v) => set("maxTradesPerDay", v)}
          />
          <RiskField
            label="Max Loss Streak"
            help={`Range: ${RISK_RANGES.maxLossStreak.min}–${RISK_RANGES.maxLossStreak.max} consecutive losses`}
            value={risk.maxLossStreak}
            min={RISK_RANGES.maxLossStreak.min}
            max={RISK_RANGES.maxLossStreak.max}
            step={RISK_RANGES.maxLossStreak.step}
            onChange={(v) => set("maxLossStreak", v)}
          />
          <RiskField
            label="Max Capital / Trade %"
            help={`Range: ${RISK_RANGES.maxCapitalPerTradePercent.min}–${RISK_RANGES.maxCapitalPerTradePercent.max}%`}
            value={risk.maxCapitalPerTradePercent}
            min={RISK_RANGES.maxCapitalPerTradePercent.min}
            max={RISK_RANGES.maxCapitalPerTradePercent.max}
            step={RISK_RANGES.maxCapitalPerTradePercent.step}
            onChange={(v) => set("maxCapitalPerTradePercent", v)}
          />
        </div>
      </div>
    </GlassmorphismCard>
  );
}


interface RiskFieldProps {
  label: string;
  help: string;
  value: string;
  min: number;
  max: number;
  step: number;
  onChange: (next: string) => void;
}

function RiskField({
  label,
  help,
  value,
  min,
  max,
  step,
  onChange,
}: RiskFieldProps) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </label>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        placeholder="No cap"
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          "w-full rounded-md px-2.5 py-1.5 text-sm",
          "bg-white/[0.02] border border-white/[0.06] text-foreground",
          "placeholder:text-muted-foreground",
          "focus:outline-none focus:border-accent-blue/50 focus:ring-2 focus:ring-accent-blue/15",
        )}
      />
      <p className="text-[10px] text-muted-foreground">{help}</p>
    </div>
  );
}
