"use client";

import { ShieldCheck, TestTube } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { RISK_RANGES, type RiskState } from "./builder-types";

interface RiskSectionProps {
  risk: RiskState;
  onChange: (next: RiskState) => void;
  enableRobustnessTest: boolean;
  onRobustnessToggle: (enabled: boolean) => void;
}

export function RiskSection({
  risk,
  onChange,
  enableRobustnessTest,
  onRobustnessToggle,
}: RiskSectionProps) {
  function set<K extends keyof RiskState>(key: K, value: string) {
    onChange({ ...risk, [key]: value });
  }

  return (
    <div className="space-y-4">
      <GlassmorphismCard hover={false}>
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-accent-blue" />
            <h2 className="font-semibold">Risk Caps</h2>
            <Badge className="ml-auto bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
              All optional
            </Badge>
          </div>
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            Khaali chhodoge to cap apply nahi hota. Expert mode ke ranges
            wide hain — apni discipline ka socho phir set karo.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Field
              label="Max Daily Loss %"
              help={`${RISK_RANGES.maxDailyLossPercent.min}–${RISK_RANGES.maxDailyLossPercent.max}%`}
              value={risk.maxDailyLossPercent}
              min={RISK_RANGES.maxDailyLossPercent.min}
              max={RISK_RANGES.maxDailyLossPercent.max}
              onChange={(v) => set("maxDailyLossPercent", v)}
            />
            <Field
              label="Max Trades / Day"
              help={`${RISK_RANGES.maxTradesPerDay.min}–${RISK_RANGES.maxTradesPerDay.max}`}
              value={risk.maxTradesPerDay}
              min={RISK_RANGES.maxTradesPerDay.min}
              max={RISK_RANGES.maxTradesPerDay.max}
              integer
              onChange={(v) => set("maxTradesPerDay", v)}
            />
            <Field
              label="Max Loss Streak"
              help={`${RISK_RANGES.maxLossStreak.min}–${RISK_RANGES.maxLossStreak.max} consecutive losses`}
              value={risk.maxLossStreak}
              min={RISK_RANGES.maxLossStreak.min}
              max={RISK_RANGES.maxLossStreak.max}
              integer
              onChange={(v) => set("maxLossStreak", v)}
            />
            <Field
              label="Max Capital / Trade %"
              help={`${RISK_RANGES.maxCapitalPerTradePercent.min}–${RISK_RANGES.maxCapitalPerTradePercent.max}%`}
              value={risk.maxCapitalPerTradePercent}
              min={RISK_RANGES.maxCapitalPerTradePercent.min}
              max={RISK_RANGES.maxCapitalPerTradePercent.max}
              onChange={(v) => set("maxCapitalPerTradePercent", v)}
            />
          </div>
        </div>
      </GlassmorphismCard>

      {/* Robustness toggle — surfaces in the backtest run as
          ``include_sensitivity``. The backtest page currently sends
          ``{}`` to ``/strategies/{id}/backtest``; the toggle is
          persisted to sessionStorage on submit so a future wiring
          pass can pick it up without changing the wire format. */}
      <GlassmorphismCard hover={false}>
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <TestTube className="h-4 w-4 text-accent-blue" />
            <h3 className="font-semibold text-sm">Robustness Test</h3>
            <Badge className="ml-auto bg-accent-blue/15 text-accent-blue border-accent-blue/30 text-[10px]">
              Optional
            </Badge>
          </div>
          <label className="flex items-start gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={enableRobustnessTest}
              onChange={(e) => onRobustnessToggle(e.target.checked)}
              className="h-3.5 w-3.5 mt-1 rounded border-white/[0.1] bg-white/[0.04] text-accent-blue focus:ring-accent-blue/40"
            />
            <div>
              <span className="text-sm font-medium">
                Run sensitivity sweep with backtest
              </span>
              <p className="text-[11px] text-muted-foreground leading-relaxed mt-0.5">
                Backend ka ``include_sensitivity`` flag flip karta hai —
                ~21 extra backtests run honge alag-alag parameter
                perturbations pe. Slow-down realistic hai. Preference
                sessionStorage mein store hota hai aur backtest run pe
                pickup hota hai.
              </p>
            </div>
          </label>
        </div>
      </GlassmorphismCard>
    </div>
  );
}


function Field({
  label,
  help,
  value,
  min,
  max,
  integer = false,
  onChange,
}: {
  label: string;
  help: string;
  value: string;
  min: number;
  max: number;
  integer?: boolean;
  onChange: (v: string) => void;
}) {
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
        step={integer ? 1 : "any"}
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
