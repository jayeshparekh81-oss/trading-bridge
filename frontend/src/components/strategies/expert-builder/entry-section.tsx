"use client";

import { Plus, Hash, Crosshair, CalendarClock, Coins, Workflow } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { ConditionRowEditor } from "./condition-row";
import {
  type ConditionRow,
  type ConditionType,
  type EntryOperator,
  type SelectedIndicator,
  type Side,
} from "./builder-types";

interface EntrySectionProps {
  side: Side;
  onSideChange: (next: Side) => void;
  operator: EntryOperator;
  onOperatorChange: (next: EntryOperator) => void;
  indicators: ReadonlyArray<SelectedIndicator>;
  conditions: ReadonlyArray<ConditionRow>;
  onAddCondition: (type: ConditionType) => void;
  onRemoveCondition: (rowId: string) => void;
  onPatchCondition: (rowId: string, patch: Partial<ConditionRow>) => void;
}

const TYPE_BUTTONS: Array<{ id: ConditionType; label: string; icon: React.ComponentType<{ className?: string }>; hint: string }> = [
  { id: "indicator", label: "Indicator", icon: Hash, hint: "Compare two indicators or against a value." },
  { id: "candle", label: "Candle", icon: Crosshair, hint: "Match a candle pattern (engulfing, doji…)." },
  { id: "time", label: "Time", icon: CalendarClock, hint: "Match wall-clock IST time." },
  { id: "price", label: "Price", icon: Coins, hint: "Test price level or breakout primitive." },
];

export function EntrySection({
  side,
  onSideChange,
  operator,
  onOperatorChange,
  indicators,
  conditions,
  onAddCondition,
  onRemoveCondition,
  onPatchCondition,
}: EntrySectionProps) {
  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Workflow className="h-4 w-4 text-accent-blue" />
          <h2 className="font-semibold">Entry Logic</h2>
          <Badge className="ml-auto bg-accent-blue/15 text-accent-blue border-accent-blue/30 text-[10px]">
            single-group
          </Badge>
        </div>

        <p className="text-[11px] text-muted-foreground leading-relaxed">
          Sab conditions ek hi group mein hain — top-level operator AND ya
          OR. Nested groups Phase 1 schema support nahi karta; richer logic
          ke liye JSON tab mein raw payload edit kar sakte ho.
        </p>

        {/* Side + operator */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className="text-[11px] uppercase text-muted-foreground tracking-wide">
              Direction
            </label>
            <div className="grid grid-cols-2 gap-2">
              <ToggleButton
                label="BUY"
                active={side === "BUY"}
                tone="profit"
                onClick={() => onSideChange("BUY")}
              />
              <ToggleButton
                label="SELL"
                active={side === "SELL"}
                tone="loss"
                onClick={() => onSideChange("SELL")}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-[11px] uppercase text-muted-foreground tracking-wide">
              Group Operator
            </label>
            <div className="grid grid-cols-2 gap-2">
              <ToggleButton
                label="AND"
                active={operator === "AND"}
                tone="blue"
                onClick={() => onOperatorChange("AND")}
              />
              <ToggleButton
                label="OR"
                active={operator === "OR"}
                tone="blue"
                onClick={() => onOperatorChange("OR")}
              />
            </div>
          </div>
        </div>

        {/* Add condition buttons */}
        <div className="space-y-1.5">
          <label className="text-[11px] uppercase text-muted-foreground tracking-wide">
            Add condition
          </label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {TYPE_BUTTONS.map((btn) => (
              <button
                key={btn.id}
                type="button"
                onClick={() => onAddCondition(btn.id)}
                disabled={btn.id === "indicator" && indicators.length === 0}
                className={cn(
                  "rounded-md px-2.5 py-2 text-left transition-colors border",
                  "bg-white/[0.02] border-white/[0.06] hover:bg-white/[0.04]",
                  "disabled:opacity-40 disabled:cursor-not-allowed",
                )}
              >
                <div className="flex items-center gap-1.5 text-sm font-medium">
                  <btn.icon className="h-3.5 w-3.5 text-accent-blue" />
                  {btn.label}
                  <Plus className="h-3 w-3 text-muted-foreground ml-auto" />
                </div>
                <p className="text-[10px] text-muted-foreground mt-0.5 leading-snug">
                  {btn.hint}
                </p>
              </button>
            ))}
          </div>
          {indicators.length === 0 ? (
            <p className="text-[10px] text-muted-foreground">
              Indicator condition ke liye pehle indicator add karo.
            </p>
          ) : null}
        </div>

        {/* Conditions list */}
        {conditions.length === 0 ? (
          <div className="rounded-md bg-white/[0.02] border border-dashed border-white/[0.08] p-4 text-center">
            <p className="text-xs text-muted-foreground">
              Abhi koi entry condition nahi. Upar se ek type chuno.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {conditions.map((row, idx) => (
              <ConditionRowEditor
                key={row.rowId}
                index={idx}
                row={row}
                indicators={indicators}
                onChange={(patch) => onPatchCondition(row.rowId, patch)}
                onRemove={() => onRemoveCondition(row.rowId)}
              />
            ))}
          </div>
        )}
      </div>
    </GlassmorphismCard>
  );
}


function ToggleButton({
  label,
  active,
  tone,
  onClick,
}: {
  label: string;
  active: boolean;
  tone: "profit" | "loss" | "blue";
  onClick: () => void;
}) {
  const styles = {
    profit: "bg-profit/15 border-profit/40 text-profit",
    loss: "bg-loss/15 border-loss/40 text-loss",
    blue: "bg-accent-blue/15 border-accent-blue/40 text-accent-blue",
  } as const;
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded-md px-3 py-2 text-sm font-semibold transition-colors border",
        active
          ? styles[tone]
          : "bg-white/[0.02] border-white/[0.06] text-muted-foreground hover:bg-white/[0.04]",
      )}
    >
      {label}
    </button>
  );
}
