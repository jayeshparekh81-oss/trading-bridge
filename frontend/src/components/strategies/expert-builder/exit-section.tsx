"use client";

import { useMemo } from "react";
import {
  Target,
  Shield,
  TrendingDown,
  Plus,
  X,
  CalendarClock,
  ArrowLeft,
  Hash,
  Crosshair,
  Coins,
} from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { ConditionRowEditor } from "./condition-row";
import {
  type ConditionRow,
  type ConditionType,
  type ExitState,
  type PartialExitRow,
  type SelectedIndicator,
} from "./builder-types";

interface ExitSectionProps {
  exit: ExitState;
  indicators: ReadonlyArray<SelectedIndicator>;
  onChange: (patch: Partial<ExitState>) => void;
  onAddPartial: () => void;
  onRemovePartial: (rowId: string) => void;
  onPatchPartial: (rowId: string, patch: Partial<PartialExitRow>) => void;
  onAddIndicatorExit: (type: ConditionType) => void;
  onRemoveIndicatorExit: (rowId: string) => void;
  onPatchIndicatorExit: (rowId: string, patch: Partial<ConditionRow>) => void;
}

export function ExitSection({
  exit,
  indicators,
  onChange,
  onAddPartial,
  onRemovePartial,
  onPatchPartial,
  onAddIndicatorExit,
  onRemoveIndicatorExit,
  onPatchIndicatorExit,
}: ExitSectionProps) {
  const partialSum = useMemo(() => {
    let sum = 0;
    for (const p of exit.partialExits) {
      const num = Number(p.qtyPercent);
      if (!Number.isNaN(num)) sum += num;
    }
    return sum;
  }, [exit.partialExits]);

  return (
    <div className="space-y-4">
      <GlassmorphismCard hover={false}>
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Target className="h-4 w-4 text-accent-blue" />
            <h2 className="font-semibold">Exit Primitives</h2>
          </div>
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            Kam se kam ek exit rule chahiye (target, stop, trailing, partial,
            square-off, indicator exit, ya reverse signal).
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <NumberField
              icon={<Target className="h-4 w-4 text-profit" />}
              label="Target %"
              value={exit.targetPercent}
              placeholder="No target"
              step="0.1"
              onChange={(v) => onChange({ targetPercent: v })}
            />
            <NumberField
              icon={<Shield className="h-4 w-4 text-loss" />}
              label="Stop Loss %"
              value={exit.stopLossPercent}
              placeholder="No stop"
              step="0.1"
              onChange={(v) => onChange({ stopLossPercent: v })}
            />
            <NumberField
              icon={<TrendingDown className="h-4 w-4 text-accent-blue" />}
              label="Trailing Stop %"
              value={exit.trailingStopPercent}
              placeholder="Off"
              step="0.1"
              onChange={(v) => onChange({ trailingStopPercent: v })}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-[11px] uppercase text-muted-foreground tracking-wide">
                Square-off Time (HH:MM)
              </label>
              <div className="relative">
                <CalendarClock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type="text"
                  inputMode="numeric"
                  value={exit.squareOffTime}
                  onChange={(e) => onChange({ squareOffTime: e.target.value })}
                  placeholder="15:15"
                  className={cn(inputClasses, "pl-9")}
                />
              </div>
            </div>
            <label className="flex items-center gap-2 cursor-pointer mt-6">
              <input
                type="checkbox"
                checked={exit.reverseSignalExit}
                onChange={(e) => onChange({ reverseSignalExit: e.target.checked })}
                className="h-3.5 w-3.5 rounded border-white/[0.1] bg-white/[0.04] text-accent-blue focus:ring-accent-blue/40"
              />
              <span className="text-sm font-medium flex items-center gap-1.5">
                <ArrowLeft className="h-3.5 w-3.5 text-accent-blue" />
                Exit on reverse signal
              </span>
            </label>
          </div>
        </div>
      </GlassmorphismCard>

      {/* ── Partial exits ────────────────────────────────────────── */}
      <GlassmorphismCard hover={false}>
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Target className="h-4 w-4 text-accent-blue" />
            <h3 className="font-semibold text-sm">Partial Exits</h3>
            <Badge
              className={cn(
                "ml-auto text-[10px] gap-1",
                exit.partialExits.length === 0
                  ? "bg-white/[0.04] text-muted-foreground border-white/[0.06]"
                  : Math.abs(partialSum - 100) < 0.01
                    ? "bg-profit/15 text-profit border-profit/30"
                    : "bg-loss/15 text-loss border-loss/30",
              )}
            >
              qty% total {partialSum.toFixed(2)}%
            </Badge>
          </div>
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            Multiple exit levels banate hain — qty% ka total 100% hona
            chahiye. Empty list bhi valid hai (sirf top-level target use
            hoga).
          </p>
          {exit.partialExits.length > 0 ? (
            <div className="space-y-2">
              {exit.partialExits.map((p, idx) => (
                <PartialExitRowEditor
                  key={p.rowId}
                  index={idx}
                  row={p}
                  onRemove={() => onRemovePartial(p.rowId)}
                  onChange={(patch) => onPatchPartial(p.rowId, patch)}
                />
              ))}
            </div>
          ) : null}
          <Button variant="outline" size="sm" onClick={onAddPartial} type="button">
            <Plus className="h-3.5 w-3.5 mr-1" />
            Add partial exit
          </Button>
        </div>
      </GlassmorphismCard>

      {/* ── Indicator-driven exits ──────────────────────────────── */}
      <GlassmorphismCard hover={false}>
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-accent-blue" />
            <h3 className="font-semibold text-sm">Indicator-driven Exits</h3>
            <Badge className="ml-auto bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
              {exit.indicatorExits.length}
            </Badge>
          </div>
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            Yahan jo conditions add karoge, position khulne ke baad jab
            match karein, position close ho jayegi.
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <ExitTypeButton
              label="Indicator"
              icon={Hash}
              onClick={() => onAddIndicatorExit("indicator")}
              disabled={indicators.length === 0}
            />
            <ExitTypeButton
              label="Candle"
              icon={Crosshair}
              onClick={() => onAddIndicatorExit("candle")}
            />
            <ExitTypeButton
              label="Time"
              icon={CalendarClock}
              onClick={() => onAddIndicatorExit("time")}
            />
            <ExitTypeButton
              label="Price"
              icon={Coins}
              onClick={() => onAddIndicatorExit("price")}
            />
          </div>
          {exit.indicatorExits.length > 0 ? (
            <div className="space-y-2">
              {exit.indicatorExits.map((row, idx) => (
                <ConditionRowEditor
                  key={row.rowId}
                  index={idx}
                  row={row}
                  indicators={indicators}
                  onChange={(patch) => onPatchIndicatorExit(row.rowId, patch)}
                  onRemove={() => onRemoveIndicatorExit(row.rowId)}
                />
              ))}
            </div>
          ) : null}
        </div>
      </GlassmorphismCard>
    </div>
  );
}


function PartialExitRowEditor({
  index,
  row,
  onRemove,
  onChange,
}: {
  index: number;
  row: PartialExitRow;
  onRemove: () => void;
  onChange: (patch: Partial<PartialExitRow>) => void;
}) {
  return (
    <div className="rounded-md bg-white/[0.02] border border-white/[0.04] p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
          Partial #{index + 1}
        </span>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onRemove}
          type="button"
          aria-label={`Remove partial ${index + 1}`}
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <label className="text-[10px] uppercase text-muted-foreground tracking-wide">
            qty %
          </label>
          <input
            type="number"
            step="0.1"
            min={0.1}
            max={100}
            value={row.qtyPercent}
            onChange={(e) => onChange({ qtyPercent: e.target.value })}
            className={inputClasses}
          />
        </div>
        <div className="space-y-1">
          <label className="text-[10px] uppercase text-muted-foreground tracking-wide">
            target %
          </label>
          <input
            type="number"
            step="0.1"
            min={0.1}
            value={row.targetPercent}
            onChange={(e) => onChange({ targetPercent: e.target.value })}
            className={inputClasses}
          />
        </div>
      </div>
    </div>
  );
}


function ExitTypeButton({
  label,
  icon: Icon,
  onClick,
  disabled = false,
}: {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "rounded-md px-2.5 py-2 text-sm font-medium transition-colors border",
        "bg-white/[0.02] border-white/[0.06] hover:bg-white/[0.04]",
        "disabled:opacity-40 disabled:cursor-not-allowed",
      )}
    >
      <span className="inline-flex items-center gap-1.5">
        <Icon className="h-3.5 w-3.5 text-accent-blue" />
        {label}
        <Plus className="h-3 w-3 text-muted-foreground ml-1" />
      </span>
    </button>
  );
}


function NumberField({
  icon,
  label,
  value,
  placeholder,
  step,
  onChange,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  placeholder?: string;
  step?: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-1.5">
        {icon}
        <label className="text-[11px] uppercase text-muted-foreground tracking-wide">
          {label}
        </label>
      </div>
      <input
        type="number"
        step={step ?? "any"}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={inputClasses}
      />
    </div>
  );
}


const inputClasses = cn(
  "w-full rounded-md px-2.5 py-1.5 text-sm",
  "bg-white/[0.02] border border-white/[0.06] text-foreground",
  "placeholder:text-muted-foreground",
  "focus:outline-none focus:border-accent-blue/50 focus:ring-2 focus:ring-accent-blue/15",
);
