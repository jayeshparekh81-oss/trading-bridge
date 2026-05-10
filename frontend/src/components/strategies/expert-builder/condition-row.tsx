"use client";

import { X, Hash, Crosshair, CalendarClock, Coins } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  CANDLE_PATTERNS,
  INDICATOR_OPS,
  PRICE_COMPARATORS,
  PRICE_OPS,
  SERIES_ONLY_OPS,
  TIME_OPS,
  type ConditionRow,
  type ConditionType,
  type IndicatorOp,
  type SelectedIndicator,
  type TimeOp,
  type PriceOp,
  type CandlePattern,
  type ConditionRhsKind,
} from "./builder-types";

interface ConditionRowEditorProps {
  index: number;
  row: ConditionRow;
  indicators: ReadonlyArray<SelectedIndicator>;
  onChange: (patch: Partial<ConditionRow>) => void;
  onRemove: () => void;
}

export function ConditionRowEditor({
  index,
  row,
  indicators,
  onChange,
  onRemove,
}: ConditionRowEditorProps) {
  return (
    <div className="rounded-md bg-white/[0.02] border border-white/[0.04] p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
          <span>Condition #{index + 1}</span>
          <ConditionTypePill type={row.type} />
        </div>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onRemove}
          type="button"
          aria-label={`Remove condition ${index + 1}`}
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>

      {row.type === "indicator" ? (
        <IndicatorEditor row={row} indicators={indicators} onChange={onChange} />
      ) : row.type === "candle" ? (
        <CandleEditor row={row} onChange={onChange} />
      ) : row.type === "time" ? (
        <TimeEditor row={row} onChange={onChange} />
      ) : (
        <PriceEditor row={row} onChange={onChange} />
      )}
    </div>
  );
}


function ConditionTypePill({ type }: { type: ConditionType }) {
  const styles: Record<ConditionType, string> = {
    indicator: "bg-accent-blue/15 text-accent-blue border-accent-blue/30",
    candle: "bg-profit/15 text-profit border-profit/30",
    time: "bg-yellow-500/15 text-yellow-200 border-yellow-500/30",
    price: "bg-loss/15 text-loss border-loss/30",
  };
  const Icon =
    type === "indicator"
      ? Hash
      : type === "candle"
        ? Crosshair
        : type === "time"
          ? CalendarClock
          : Coins;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] uppercase",
        styles[type],
      )}
    >
      <Icon className="h-3 w-3" />
      {type}
    </span>
  );
}


// ─── Indicator condition ───────────────────────────────────────────────


function IndicatorEditor({
  row,
  indicators,
  onChange,
}: {
  row: Extract<ConditionRow, { type: "indicator" }>;
  indicators: ReadonlyArray<SelectedIndicator>;
  onChange: (patch: Partial<ConditionRow>) => void;
}) {
  const seriesOnly = SERIES_ONLY_OPS.has(row.op);

  function handleOpChange(nextOp: IndicatorOp) {
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
    <div className="grid grid-cols-1 md:grid-cols-[1.2fr_0.8fr_1.4fr] gap-2 items-start">
      <select
        value={row.left}
        onChange={(e) => onChange({ left: e.target.value })}
        className={selectClasses}
        aria-label="Left indicator"
      >
        <option value="">— select indicator —</option>
        {indicators.map((ind) => (
          <option key={ind.id} value={ind.id}>
            {ind.label}
          </option>
        ))}
      </select>
      <select
        value={row.op}
        onChange={(e) => handleOpChange(e.target.value as IndicatorOp)}
        className={selectClasses}
        aria-label="Operator"
      >
        {INDICATOR_OPS.map((op) => (
          <option key={op} value={op}>
            {op}
          </option>
        ))}
      </select>
      <div className="space-y-1.5">
        <div className="flex items-center gap-1">
          <KindToggle
            label="Indicator"
            active={row.rhsKind === "indicator"}
            onClick={() => handleRhsKindChange("indicator")}
          />
          <KindToggle
            label="Value"
            active={row.rhsKind === "value"}
            disabled={seriesOnly}
            onClick={() => handleRhsKindChange("value")}
          />
        </div>
        {row.rhsKind === "indicator" ? (
          <select
            value={row.right}
            onChange={(e) => onChange({ right: e.target.value })}
            className={selectClasses}
            aria-label="Right indicator"
          >
            <option value="">— select indicator —</option>
            {indicators.map((ind) => (
              <option key={ind.id} value={ind.id}>
                {ind.label}
              </option>
            ))}
          </select>
        ) : (
          <input
            type="number"
            step="any"
            value={row.value}
            onChange={(e) => onChange({ value: e.target.value })}
            placeholder="e.g. 30"
            className={selectClasses}
            aria-label="Right value"
          />
        )}
      </div>
    </div>
  );
}


// ─── Candle condition ──────────────────────────────────────────────────


function CandleEditor({
  row,
  onChange,
}: {
  row: Extract<ConditionRow, { type: "candle" }>;
  onChange: (patch: Partial<ConditionRow>) => void;
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
      <div className="space-y-1">
        <label className="text-[10px] uppercase text-muted-foreground tracking-wide">
          Pattern
        </label>
        <select
          value={row.pattern}
          onChange={(e) =>
            onChange({ pattern: e.target.value as CandlePattern })
          }
          className={selectClasses}
        >
          {CANDLE_PATTERNS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </div>
      <p className="text-[11px] text-muted-foreground self-end leading-snug">
        Match karta hai jab current bar specified candle pattern fire kare.
      </p>
    </div>
  );
}


// ─── Time condition ────────────────────────────────────────────────────


function TimeEditor({
  row,
  onChange,
}: {
  row: Extract<ConditionRow, { type: "time" }>;
  onChange: (patch: Partial<ConditionRow>) => void;
}) {
  function handleOpChange(nextOp: TimeOp) {
    if (nextOp === "between") {
      onChange({ op: nextOp });
    } else {
      // Pydantic rejects ``end`` for non-between ops; clear it.
      onChange({ op: nextOp, end: "" });
    }
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
      <div className="space-y-1">
        <label className="text-[10px] uppercase text-muted-foreground tracking-wide">
          Op
        </label>
        <select
          value={row.op}
          onChange={(e) => handleOpChange(e.target.value as TimeOp)}
          className={selectClasses}
        >
          {TIME_OPS.map((op) => (
            <option key={op} value={op}>
              {op}
            </option>
          ))}
        </select>
      </div>
      <div className="space-y-1">
        <label className="text-[10px] uppercase text-muted-foreground tracking-wide">
          Time (HH:MM)
        </label>
        <input
          type="text"
          inputMode="numeric"
          placeholder="09:30"
          value={row.value}
          onChange={(e) => onChange({ value: e.target.value })}
          className={selectClasses}
        />
      </div>
      <div className="space-y-1">
        <label className="text-[10px] uppercase text-muted-foreground tracking-wide">
          End {row.op === "between" ? "(HH:MM)" : "— between only"}
        </label>
        <input
          type="text"
          inputMode="numeric"
          placeholder="15:15"
          value={row.end}
          disabled={row.op !== "between"}
          onChange={(e) => onChange({ end: e.target.value })}
          className={cn(
            selectClasses,
            row.op !== "between" && "opacity-50 cursor-not-allowed",
          )}
        />
      </div>
    </div>
  );
}


// ─── Price condition ───────────────────────────────────────────────────


function PriceEditor({
  row,
  onChange,
}: {
  row: Extract<ConditionRow, { type: "price" }>;
  onChange: (patch: Partial<ConditionRow>) => void;
}) {
  const usesValue = PRICE_COMPARATORS.has(row.op);

  function handleOpChange(nextOp: PriceOp) {
    if (PRICE_COMPARATORS.has(nextOp)) {
      onChange({ op: nextOp });
    } else {
      // Breakout primitives don't take a value — clear it.
      onChange({ op: nextOp, value: "" });
    }
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
      <div className="space-y-1">
        <label className="text-[10px] uppercase text-muted-foreground tracking-wide">
          Op
        </label>
        <select
          value={row.op}
          onChange={(e) => handleOpChange(e.target.value as PriceOp)}
          className={selectClasses}
        >
          {PRICE_OPS.map((op) => (
            <option key={op} value={op}>
              {op}
            </option>
          ))}
        </select>
      </div>
      <div className="space-y-1">
        <label className="text-[10px] uppercase text-muted-foreground tracking-wide">
          Value {usesValue ? "" : "— not used"}
        </label>
        <input
          type="number"
          step="any"
          placeholder={usesValue ? "e.g. 21500" : ""}
          value={row.value}
          disabled={!usesValue}
          onChange={(e) => onChange({ value: e.target.value })}
          className={cn(
            selectClasses,
            !usesValue && "opacity-50 cursor-not-allowed",
          )}
        />
      </div>
    </div>
  );
}


// ─── Shared toggles + classes ──────────────────────────────────────────


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
