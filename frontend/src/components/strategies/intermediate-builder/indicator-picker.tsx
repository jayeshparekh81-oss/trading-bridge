"use client";

import { useMemo, useState } from "react";
import { Search, Plus, X, Layers, Sparkles } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { IndicatorMetadata } from "@/components/strategies/indicator-library";
import {
  buildIndicatorLabel,
  makeInstanceId,
  readInputSpecs,
  SOURCE_OPTIONS,
  type SelectedIndicator,
} from "./builder-types";

interface IndicatorPickerProps {
  catalogue: ReadonlyArray<IndicatorMetadata>;
  selected: SelectedIndicator[];
  onAdd: (indicator: SelectedIndicator) => void;
  onRemove: (id: string) => void;
  loading: boolean;
  loadError: string | null;
}

export function IndicatorPicker({
  catalogue,
  selected,
  onAdd,
  onRemove,
  loading,
  loadError,
}: IndicatorPickerProps) {
  const [search, setSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [pendingTypeId, setPendingTypeId] = useState<string | null>(null);

  // Intermediate mode only exposes ACTIVE indicators (drops coming_soon
  // and experimental — matches modeAllowsClickable("intermediate", ...)
  // semantics inside the existing IndicatorLibrary component).
  const usable = useMemo(
    () => catalogue.filter((ind) => ind.status === "active"),
    [catalogue],
  );

  const categories = useMemo(() => {
    const set = new Set<string>();
    for (const ind of usable) set.add(ind.category);
    return Array.from(set).sort();
  }, [usable]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return usable.filter((ind) => {
      if (activeCategory && ind.category !== activeCategory) return false;
      if (!q) return true;
      const hay = `${ind.id} ${ind.name} ${ind.description} ${ind.tags.join(" ")}`.toLowerCase();
      return hay.includes(q);
    });
  }, [usable, search, activeCategory]);

  const pending = pendingTypeId
    ? usable.find((ind) => ind.id === pendingTypeId) ?? null
    : null;

  const takenIds = useMemo(
    () => new Set(selected.map((s) => s.id)),
    [selected],
  );

  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Layers className="h-4 w-4 text-accent-blue" />
          <h2 className="font-semibold">Indicators</h2>
          <Badge className="ml-auto bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
            {selected.length} selected
          </Badge>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="search"
            placeholder="Search by name, id, or tag…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={cn(
              "w-full rounded-lg pl-9 pr-3 py-2 text-sm",
              "bg-white/[0.02] border border-white/[0.06] text-foreground",
              "placeholder:text-muted-foreground",
              "focus:outline-none focus:border-accent-blue/50 focus:ring-2 focus:ring-accent-blue/15",
            )}
            aria-label="Search indicators"
          />
        </div>

        {/* Category chips */}
        <div className="flex flex-wrap gap-1.5">
          <CategoryChip
            label="All"
            active={activeCategory === null}
            onClick={() => setActiveCategory(null)}
          />
          {categories.map((cat) => (
            <CategoryChip
              key={cat}
              label={cat}
              active={activeCategory === cat}
              onClick={() =>
                setActiveCategory(cat === activeCategory ? null : cat)
              }
            />
          ))}
        </div>

        {/* Catalogue list (compact) */}
        {loadError ? (
          <p className="text-xs text-loss">
            Catalogue load failed: {loadError}
          </p>
        ) : loading && usable.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Loading indicator library…
          </p>
        ) : filtered.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Filter ke hisaab se koi indicator nahi mila.
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-72 overflow-y-auto pr-1">
            {filtered.map((ind) => (
              <IndicatorRow
                key={ind.id}
                indicator={ind}
                onClick={() => setPendingTypeId(ind.id)}
                active={pendingTypeId === ind.id}
              />
            ))}
          </div>
        )}

        {/* Add form */}
        {pending ? (
          <AddIndicatorForm
            key={pending.id}
            indicator={pending}
            takenIds={takenIds}
            onCancel={() => setPendingTypeId(null)}
            onAdd={(picked) => {
              onAdd(picked);
              setPendingTypeId(null);
            }}
          />
        ) : (
          <p className="text-[11px] text-muted-foreground">
            Indicator pe click karke uska config form kholo.
          </p>
        )}

        {/* Selected list */}
        {selected.length > 0 ? (
          <div className="space-y-2 pt-2 border-t border-white/[0.04]">
            <h3 className="text-xs uppercase tracking-wide text-muted-foreground font-medium">
              Selected ({selected.length})
            </h3>
            <div className="space-y-2">
              {selected.map((ind) => (
                <SelectedRow
                  key={ind.id}
                  indicator={ind}
                  onRemove={() => onRemove(ind.id)}
                />
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </GlassmorphismCard>
  );
}


// ─── Pieces ────────────────────────────────────────────────────────────


function CategoryChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "text-xs px-3 py-1 rounded-full border transition-colors",
        active
          ? "bg-accent-blue/15 border-accent-blue/30 text-accent-blue"
          : "bg-white/[0.02] border-white/[0.06] text-muted-foreground hover:text-foreground hover:bg-white/[0.04]",
      )}
    >
      {label}
    </button>
  );
}


function IndicatorRow({
  indicator,
  onClick,
  active,
}: {
  indicator: IndicatorMetadata;
  onClick: () => void;
  active: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded-md px-2.5 py-2 text-left transition-colors border",
        active
          ? "bg-accent-blue/15 border-accent-blue/40"
          : "bg-white/[0.02] border-white/[0.04] hover:bg-white/[0.04]",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="text-sm font-medium truncate">{indicator.name}</div>
          <div className="text-[10px] text-muted-foreground font-mono truncate">
            {indicator.id} · {indicator.category}
          </div>
        </div>
        <Plus
          className={cn(
            "h-4 w-4 shrink-0",
            active ? "text-accent-blue" : "text-muted-foreground",
          )}
        />
      </div>
    </button>
  );
}


function SelectedRow({
  indicator,
  onRemove,
}: {
  indicator: SelectedIndicator;
  onRemove: () => void;
}) {
  const paramText = Object.entries(indicator.params)
    .map(([k, v]) => `${k}=${v}`)
    .join(", ");
  return (
    <div className="flex items-center justify-between gap-3 rounded-md bg-white/[0.02] border border-white/[0.04] px-3 py-2">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <Sparkles className="h-3 w-3 text-accent-blue" />
          <span className="text-sm font-medium truncate">{indicator.label}</span>
        </div>
        <div className="text-[10px] text-muted-foreground font-mono truncate mt-0.5">
          {indicator.id}
          {paramText ? ` · ${paramText}` : ""}
        </div>
      </div>
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={onRemove}
        type="button"
        aria-label={`Remove ${indicator.label}`}
      >
        <X className="h-3.5 w-3.5" />
      </Button>
    </div>
  );
}


// ─── Add form ──────────────────────────────────────────────────────────


interface AddIndicatorFormProps {
  indicator: IndicatorMetadata;
  takenIds: ReadonlySet<string>;
  onCancel: () => void;
  onAdd: (picked: SelectedIndicator) => void;
}

interface FieldState {
  value: string;
  error: string | null;
}

function AddIndicatorForm({
  indicator,
  takenIds,
  onCancel,
  onAdd,
}: AddIndicatorFormProps) {
  const specs = useMemo(() => readInputSpecs(indicator), [indicator]);
  const [fields, setFields] = useState<Record<string, FieldState>>(() => {
    const init: Record<string, FieldState> = {};
    for (const s of specs) {
      init[s.name] = {
        value: s.default !== undefined && s.default !== null ? String(s.default) : "",
        error: null,
      };
    }
    return init;
  });

  function setField(name: string, value: string) {
    setFields((prev) => ({ ...prev, [name]: { value, error: null } }));
  }

  function handleSubmit() {
    const params: Record<string, number | string> = {};
    const next: Record<string, FieldState> = { ...fields };
    let firstError: string | null = null;

    for (const spec of specs) {
      const raw = (fields[spec.name]?.value ?? "").trim();
      if (spec.type === "number") {
        if (raw === "") {
          next[spec.name] = { value: raw, error: "Required" };
          firstError ??= `${spec.name} chahiye.`;
          continue;
        }
        const num = Number(raw);
        if (Number.isNaN(num)) {
          next[spec.name] = { value: raw, error: "Must be a number" };
          firstError ??= `${spec.name} number hona chahiye.`;
          continue;
        }
        if (spec.min !== undefined && num < spec.min) {
          next[spec.name] = { value: raw, error: `Min ${spec.min}` };
          firstError ??= `${spec.name} kam se kam ${spec.min} hona chahiye.`;
          continue;
        }
        if (spec.max !== undefined && num > spec.max) {
          next[spec.name] = { value: raw, error: `Max ${spec.max}` };
          firstError ??= `${spec.name} ${spec.max} se zyada nahi.`;
          continue;
        }
        params[spec.name] = num;
      } else if (spec.type === "source") {
        if (!raw) {
          next[spec.name] = { value: raw, error: "Required" };
          firstError ??= `${spec.name} chuno.`;
          continue;
        }
        params[spec.name] = raw;
      } else {
        params[spec.name] = raw;
      }
    }

    if (firstError) {
      setFields(next);
      return;
    }

    const id = makeInstanceId(indicator.id, params, takenIds);
    onAdd({
      id,
      type: indicator.id,
      label: buildIndicatorLabel(indicator, params),
      params,
      meta: indicator,
    });
  }

  return (
    <div className="rounded-lg bg-accent-blue/[0.04] border border-accent-blue/20 p-3 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold text-sm">{indicator.name}</h3>
          <p className="text-[11px] text-muted-foreground line-clamp-2 leading-snug">
            {indicator.description}
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onCancel}
          type="button"
          aria-label="Cancel"
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {specs.length === 0 ? (
          <p className="text-[11px] text-muted-foreground sm:col-span-2">
            Is indicator ko configure karne ke liye koi input nahi hai.
          </p>
        ) : (
          specs.map((spec) => (
            <FieldRow
              key={spec.name}
              spec={spec}
              field={fields[spec.name] ?? { value: "", error: null }}
              onChange={(v) => setField(spec.name, v)}
            />
          ))
        )}
      </div>

      <div className="flex items-center justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={onCancel} type="button">
          Cancel
        </Button>
        <Button variant="default" size="sm" onClick={handleSubmit} type="button">
          <Plus className="h-3.5 w-3.5 mr-1" />
          Add Indicator
        </Button>
      </div>
    </div>
  );
}


function FieldRow({
  spec,
  field,
  onChange,
}: {
  spec: { name: string; type: "number" | "source" | "boolean" | "string"; min?: number; max?: number };
  field: FieldState;
  onChange: (v: string) => void;
}) {
  const inputClasses = cn(
    "w-full rounded-md px-2.5 py-1.5 text-sm",
    "bg-white/[0.02] border text-foreground",
    field.error
      ? "border-loss/50 focus:border-loss"
      : "border-white/[0.06] focus:border-accent-blue/50",
    "focus:outline-none focus:ring-2 focus:ring-accent-blue/15",
  );

  return (
    <div className="space-y-1">
      <label className="text-[11px] uppercase tracking-wide text-muted-foreground">
        {spec.name}
        {spec.type === "number" && (spec.min !== undefined || spec.max !== undefined) ? (
          <span className="ml-1 text-muted-foreground/70 lowercase normal-case font-mono">
            ({spec.min ?? "—"}–{spec.max ?? "—"})
          </span>
        ) : null}
      </label>
      {spec.type === "source" ? (
        <select
          value={field.value}
          onChange={(e) => onChange(e.target.value)}
          className={inputClasses}
        >
          {SOURCE_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      ) : spec.type === "boolean" ? (
        <select
          value={field.value || "false"}
          onChange={(e) => onChange(e.target.value)}
          className={inputClasses}
        >
          <option value="true">true</option>
          <option value="false">false</option>
        </select>
      ) : (
        <input
          type={spec.type === "number" ? "number" : "text"}
          value={field.value}
          step={spec.type === "number" ? "any" : undefined}
          min={spec.min}
          max={spec.max}
          onChange={(e) => onChange(e.target.value)}
          className={inputClasses}
        />
      )}
      {field.error ? (
        <p className="text-[10px] text-loss">{field.error}</p>
      ) : null}
    </div>
  );
}
