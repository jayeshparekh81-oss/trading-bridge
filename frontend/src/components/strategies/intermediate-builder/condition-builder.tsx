"use client";

import { Plus, X, ArrowRight, Calculator } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  ALL_CONDITION_OPS,
  SERIES_ONLY_OPS,
  type ConditionOp,
  type ConditionRow,
  type ConditionRhsKind,
  type SelectedIndicator,
  type Side,
} from "./builder-types";

interface ConditionBuilderProps {
  side: Side;
  onSideChange: (next: Side) => void;
  indicators: ReadonlyArray<SelectedIndicator>;
  conditions: ReadonlyArray<ConditionRow>;
  onAdd: () => void;
  onRemove: (rowId: string) => void;
  onChange: (rowId: string, patch: Partial<ConditionRow>) => void;
}

export function ConditionBuilder({
  side,
  onSideChange,
  indicators,
  conditions,
  onAdd,
  onRemove,
  onChange,
}: ConditionBuilderProps) {
  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Calculator className="h-4 w-4 text-accent-blue" />
          <h2 className="font-semibold">Entry Conditions</h2>
          <Badge className="ml-auto bg-accent-blue/15 text-accent-blue border-accent-blue/30 text-[10px]">
            AND
          </Badge>
        </div>

        <p className="text-[11px] text-muted-foreground leading-relaxed">
          Sab conditions saath match honi chahiye (AND). OR grouping
          expert mode mein milega.
        </p>

        {/* Side toggle */}
        <div className="space-y-1.5">
          <label className="text-[11px] uppercase tracking-wide text-muted-foreground">
            Direction
          </label>
          <div className="grid grid-cols-2 gap-2 max-w-sm">
            <SideButton
              label="BUY"
              active={side === "BUY"}
              tone="profit"
              onClick={() => onSideChange("BUY")}
            />
            <SideButton
              label="SELL"
              active={side === "SELL"}
              tone="loss"
              onClick={() => onSideChange("SELL")}
            />
          </div>
        </div>

        {indicators.length === 0 ? (
          <div className="rounded-md bg-white/[0.02] border border-dashed border-white/[0.08] p-4 text-center">
            <p className="text-xs text-muted-foreground">
              Pehle upar se indicators add karo, phir conditions banao.
            </p>
          </div>
        ) : conditions.length === 0 ? (
          <EmptyConditions onAdd={onAdd} />
        ) : (
          <div className="space-y-2">
            {conditions.map((row, idx) => (
              <ConditionRowEditor
                key={row.rowId}
                row={row}
                index={idx}
                indicators={indicators}
                onRemove={() => onRemove(row.rowId)}
                onChange={(patch) => onChange(row.rowId, patch)}
              />
            ))}
            <Button
              variant="outline"
              size="sm"
              onClick={onAdd}
              type="button"
              disabled={indicators.length === 0}
            >
              <Plus className="h-3.5 w-3.5 mr-1" />
              Add another condition
            </Button>
          </div>
        )}
      </div>
    </GlassmorphismCard>
  );
}


function SideButton({
  label,
  active,
  tone,
  onClick,
}: {
  label: string;
  active: boolean;
  tone: "profit" | "loss";
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded-md px-3 py-2 text-sm font-semibold transition-colors border",
        active
          ? tone === "profit"
            ? "bg-profit/15 border-profit/40 text-profit"
            : "bg-loss/15 border-loss/40 text-loss"
          : "bg-white/[0.02] border-white/[0.06] text-muted-foreground hover:bg-white/[0.04]",
      )}
    >
      {label}
    </button>
  );
}


function EmptyConditions({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="rounded-md bg-white/[0.02] border border-dashed border-white/[0.08] p-4 text-center space-y-2">
      <ArrowRight className="h-6 w-6 text-muted-foreground mx-auto opacity-50" />
      <p className="text-xs text-muted-foreground">
        Abhi koi condition nahi. Ek add karke shuru karo.
      </p>
      <Button variant="outline" size="sm" onClick={onAdd} type="button">
        <Plus className="h-3.5 w-3.5 mr-1" />
        Add condition
      </Button>
    </div>
  );
}


// ─── Single condition row editor ───────────────────────────────────────


interface ConditionRowEditorProps {
  row: ConditionRow;
  index: number;
  indicators: ReadonlyArray<SelectedIndicator>;
  onRemove: () => void;
  onChange: (patch: Partial<ConditionRow>) => void;
}

function ConditionRowEditor({
  row,
  index,
  indicators,
  onRemove,
  onChange,
}: ConditionRowEditorProps) {
  const seriesOnly = SERIES_ONLY_OPS.has(row.op);

  function handleOpChange(nextOp: ConditionOp) {
    if (SERIES_ONLY_OPS.has(nextOp)) {
      onChange({ op: nextOp, rhsKind: "indicator" });
    } else {
      onChange({ op: nextOp });
    }
  }

  function handleRhsKindChange(next: ConditionRhsKind) {
    if (seriesOnly && next === "value") return;
    onChange({ rhsKind: next });
  }

  return (
    <div className="rounded-md bg-white/[0.02] border border-white/[0.04] p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
          Condition #{index + 1}
        </span>
        <Button
          variant="ghost"
          size="icon-sm"
          type="button"
          onClick={onRemove}
          aria-label={`Remove condition ${index + 1}`}
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[1.4fr_0.9fr_1.4fr] gap-2 items-center">
        <IndicatorSelect
          value={row.left}
          indicators={indicators}
          onChange={(v) => onChange({ left: v })}
          ariaLabel="Left indicator"
        />
        <select
          value={row.op}
          onChange={(e) => handleOpChange(e.target.value as ConditionOp)}
          className={selectClasses}
          aria-label="Operator"
        >
          {ALL_CONDITION_OPS.map((op) => (
            <option key={op} value={op}>
              {op}
            </option>
          ))}
        </select>
        <RhsField
          row={row}
          indicators={indicators}
          seriesOnly={seriesOnly}
          onKindChange={handleRhsKindChange}
          onIndicatorChange={(v) => onChange({ right: v })}
          onValueChange={(v) => onChange({ value: v })}
        />
      </div>
    </div>
  );
}


function IndicatorSelect({
  value,
  indicators,
  onChange,
  ariaLabel,
}: {
  value: string;
  indicators: ReadonlyArray<SelectedIndicator>;
  onChange: (next: string) => void;
  ariaLabel: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label={ariaLabel}
      className={selectClasses}
    >
      <option value="">— select indicator —</option>
      {indicators.map((ind) => (
        <option key={ind.id} value={ind.id}>
          {ind.label}
        </option>
      ))}
    </select>
  );
}


function RhsField({
  row,
  indicators,
  seriesOnly,
  onKindChange,
  onIndicatorChange,
  onValueChange,
}: {
  row: ConditionRow;
  indicators: ReadonlyArray<SelectedIndicator>;
  seriesOnly: boolean;
  onKindChange: (kind: ConditionRhsKind) => void;
  onIndicatorChange: (next: string) => void;
  onValueChange: (next: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-1">
        <KindToggle
          label="Indicator"
          active={row.rhsKind === "indicator"}
          onClick={() => onKindChange("indicator")}
        />
        <KindToggle
          label="Value"
          active={row.rhsKind === "value"}
          onClick={() => onKindChange("value")}
          disabled={seriesOnly}
        />
      </div>
      {row.rhsKind === "indicator" ? (
        <IndicatorSelect
          value={row.right}
          indicators={indicators}
          onChange={onIndicatorChange}
          ariaLabel="Right indicator"
        />
      ) : (
        <input
          type="number"
          step="any"
          value={row.value}
          onChange={(e) => onValueChange(e.target.value)}
          placeholder="e.g. 30"
          className={selectClasses}
          aria-label="Right value"
        />
      )}
    </div>
  );
}


function KindToggle({
  label,
  active,
  onClick,
  disabled = false,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "text-[10px] uppercase tracking-wide px-2 py-0.5 rounded border",
        active
          ? "bg-accent-blue/15 border-accent-blue/40 text-accent-blue"
          : "bg-white/[0.02] border-white/[0.06] text-muted-foreground hover:bg-white/[0.04]",
        disabled && "opacity-40 cursor-not-allowed hover:bg-white/[0.02]",
      )}
    >
      {label}
    </button>
  );
}


const selectClasses = cn(
  "w-full rounded-md px-2.5 py-1.5 text-sm",
  "bg-white/[0.02] border border-white/[0.06] text-foreground",
  "focus:outline-none focus:border-accent-blue/50 focus:ring-2 focus:ring-accent-blue/15",
);
