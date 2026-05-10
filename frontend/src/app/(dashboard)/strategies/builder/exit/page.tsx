"use client";

/**
 * Standalone Exit Builder — author one ``ExitRules`` block in
 * isolation and save it as a reusable template.
 *
 * Reuses the Expert Builder's :class:`IndicatorSection` and
 * :class:`ExitSection` primitives unchanged — this page just owns
 * a slimmer reducer (only the exit-relevant slice) plus a
 * template-management sidebar that talks to ``/api/templates/exit``.
 *
 * The Expert / Beginner / Intermediate builders are NOT touched.
 * Phase 2 ships an "Apply template to current strategy" affordance
 * that copies the saved template into a strategy's exit block.
 */

import { useReducer, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  BookmarkPlus,
  FilePlus2,
  Save,
  Sparkles,
  Workflow,
} from "lucide-react";
import { toast } from "sonner";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import type { IndicatorMetadata } from "@/components/strategies/indicator-library";

import { ExitSection } from "@/components/strategies/expert-builder/exit-section";
import { IndicatorSection } from "@/components/strategies/expert-builder/indicator-section";
import {
  type CandlePattern,
  type ConditionRow,
  type ConditionType,
  type ExitState,
  type IndicatorOp,
  type PartialExitRow,
  type PriceOp,
  type SelectedIndicator,
  type TimeOp,
  INITIAL_EXIT,
  makeId,
} from "@/components/strategies/expert-builder/builder-types";
import {
  ExitTemplateCard,
  type ExitTemplateCardData,
} from "@/components/strategies/exit-template-card";

// ─── State machine ─────────────────────────────────────────────────────

interface BuilderState {
  exit: ExitState;
  selectedIndicators: SelectedIndicator[];
  loadedTemplateId: string | null;
}

const INITIAL_STATE: BuilderState = {
  exit: INITIAL_EXIT,
  selectedIndicators: [],
  loadedTemplateId: null,
};

type Action =
  | { type: "patch_exit"; patch: Partial<ExitState> }
  | { type: "add_indicator"; indicator: SelectedIndicator }
  | { type: "remove_indicator"; id: string }
  | { type: "add_partial" }
  | { type: "remove_partial"; rowId: string }
  | { type: "patch_partial"; rowId: string; patch: Partial<PartialExitRow> }
  | { type: "add_indicator_exit"; conditionType: ConditionType }
  | { type: "remove_indicator_exit"; rowId: string }
  | {
      type: "patch_indicator_exit";
      rowId: string;
      patch: Partial<ConditionRow>;
    }
  | { type: "load_template"; payload: BuilderState }
  | { type: "reset" };

function reducer(state: BuilderState, action: Action): BuilderState {
  switch (action.type) {
    case "patch_exit":
      return { ...state, exit: { ...state.exit, ...action.patch } };
    case "add_indicator":
      return {
        ...state,
        selectedIndicators: [...state.selectedIndicators, action.indicator],
      };
    case "remove_indicator": {
      return {
        ...state,
        selectedIndicators: state.selectedIndicators.filter(
          (i) => i.id !== action.id,
        ),
        exit: {
          ...state.exit,
          indicatorExits: state.exit.indicatorExits.map((c) =>
            clearIndicatorRefs(c, action.id),
          ),
        },
      };
    }
    case "add_partial":
      return {
        ...state,
        exit: {
          ...state.exit,
          partialExits: [
            ...state.exit.partialExits,
            { rowId: makeId(), qtyPercent: "", targetPercent: "" },
          ],
        },
      };
    case "remove_partial":
      return {
        ...state,
        exit: {
          ...state.exit,
          partialExits: state.exit.partialExits.filter(
            (p) => p.rowId !== action.rowId,
          ),
        },
      };
    case "patch_partial":
      return {
        ...state,
        exit: {
          ...state.exit,
          partialExits: state.exit.partialExits.map((p) =>
            p.rowId === action.rowId ? { ...p, ...action.patch } : p,
          ),
        },
      };
    case "add_indicator_exit":
      return {
        ...state,
        exit: {
          ...state.exit,
          indicatorExits: [
            ...state.exit.indicatorExits,
            newConditionOfType(action.conditionType, state.selectedIndicators),
          ],
        },
      };
    case "remove_indicator_exit":
      return {
        ...state,
        exit: {
          ...state.exit,
          indicatorExits: state.exit.indicatorExits.filter(
            (c) => c.rowId !== action.rowId,
          ),
        },
      };
    case "patch_indicator_exit":
      return {
        ...state,
        exit: {
          ...state.exit,
          indicatorExits: state.exit.indicatorExits.map((c) =>
            c.rowId === action.rowId
              ? mergeConditionPatch(c, action.patch)
              : c,
          ),
        },
      };
    case "load_template":
      return action.payload;
    case "reset":
      return INITIAL_STATE;
  }
}

function newConditionOfType(
  type: ConditionType,
  indicators: ReadonlyArray<SelectedIndicator>,
): ConditionRow {
  switch (type) {
    case "indicator":
      return {
        rowId: makeId(),
        type: "indicator",
        left: indicators[0]?.id ?? "",
        op: ">",
        rhsKind: "value",
        right: "",
        value: "",
      };
    case "candle":
      return { rowId: makeId(), type: "candle", pattern: "bullish" };
    case "time":
      return {
        rowId: makeId(),
        type: "time",
        op: "after",
        value: "",
        end: "",
      };
    case "price":
      return { rowId: makeId(), type: "price", op: ">", value: "" };
  }
}

function mergeConditionPatch(
  row: ConditionRow,
  patch: Partial<ConditionRow>,
): ConditionRow {
  const cleaned: Partial<ConditionRow> = { ...patch };
  if ("type" in cleaned) delete (cleaned as { type?: unknown }).type;
  return { ...row, ...cleaned } as ConditionRow;
}

function clearIndicatorRefs(
  row: ConditionRow,
  removedId: string,
): ConditionRow {
  if (row.type !== "indicator") return row;
  let next = row;
  if (row.left === removedId) next = { ...next, left: "" };
  if (row.right === removedId) next = { ...next, right: "" };
  return next;
}

// ─── Wire types ────────────────────────────────────────────────────────

interface ExitTemplateListResponse {
  templates: ExitTemplateCardData[];
  count: number;
}

// ─── Page ──────────────────────────────────────────────────────────────

export default function StandaloneExitBuilderPage() {
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const {
    data: catalogue,
    isLoading: catalogueLoading,
    error: catalogueError,
  } = useApi<IndicatorMetadata[]>("/strategies/indicators", []);

  const {
    data: templatesResp,
    refetch: refetchTemplates,
  } = useApi<ExitTemplateListResponse>("/templates/exit", {
    templates: [],
    count: 0,
  });

  const hasAnyExit = hasAnyExitPrimitive(state.exit);
  const canSave = name.trim().length > 0 && hasAnyExit && !submitting;

  async function handleSave() {
    if (!canSave) return;
    setSubmitting(true);
    try {
      const body = {
        name: name.trim(),
        description: description.trim() || null,
        exit_rules: toWireExitRules(state.exit),
        indicators_used: state.selectedIndicators.map((ind) => ({
          id: ind.id,
          type: ind.type,
          params: ind.params,
        })),
      };
      if (state.loadedTemplateId) {
        await api.put(`/templates/exit/${state.loadedTemplateId}`, body);
        toast.success("Template update ho gaya 🎉");
      } else {
        await api.post("/templates/exit", body);
        toast.success("Template save ho gaya 🎉");
      }
      refetchTemplates();
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : "Template save nahi ho paya — refresh karke try karo.";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  function handleLoad(template: ExitTemplateCardData) {
    setName(template.name);
    setDescription(template.description ?? "");
    dispatch({
      type: "load_template",
      payload: hydrateTemplate(template, catalogue ?? []),
    });
    toast.message(`"${template.name}" load ho gaya — edit karke save karo`);
  }

  async function handleDelete(templateId: string) {
    try {
      await api.delete(`/templates/exit/${templateId}`);
      if (state.loadedTemplateId === templateId) {
        dispatch({ type: "reset" });
        setName("");
        setDescription("");
      }
      refetchTemplates();
      toast.success("Template delete ho gaya");
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.detail : "Delete nahi ho paya";
      toast.error(msg);
    }
  }

  function handleNewBlank() {
    dispatch({ type: "reset" });
    setName("");
    setDescription("");
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto space-y-5"
    >
      {/* Header */}
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div className="space-y-1">
          <Link
            href="/strategies"
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-3 w-3" />
            Back to strategies
          </Link>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Workflow className="h-6 w-6 text-accent-blue" />
            Exit Conditions Builder
          </h1>
          <p className="text-xs text-muted-foreground max-w-2xl leading-relaxed">
            Sirf exit rules banao — reusable template ke liye. Target,
            stop-loss, trailing, partials, square-off — sab yahan hai.
            Beginner / Intermediate / Expert builders mein baad mein
            apply kar sakte ho. ✨
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleNewBlank}
          type="button"
        >
          <FilePlus2 className="h-3.5 w-3.5" />
          New blank
        </Button>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
        {/* Editor column */}
        <div className="space-y-4">
          <IndicatorSection
            catalogue={catalogue ?? []}
            selected={state.selectedIndicators}
            onAdd={(ind) => dispatch({ type: "add_indicator", indicator: ind })}
            onRemove={(id) => dispatch({ type: "remove_indicator", id })}
            loading={catalogueLoading}
            loadError={catalogueError}
          />

          <ExitSection
            exit={state.exit}
            indicators={state.selectedIndicators}
            onChange={(patch) => dispatch({ type: "patch_exit", patch })}
            onAddPartial={() => dispatch({ type: "add_partial" })}
            onRemovePartial={(rowId) =>
              dispatch({ type: "remove_partial", rowId })
            }
            onPatchPartial={(rowId, patch) =>
              dispatch({ type: "patch_partial", rowId, patch })
            }
            onAddIndicatorExit={(t) =>
              dispatch({ type: "add_indicator_exit", conditionType: t })
            }
            onRemoveIndicatorExit={(rowId) =>
              dispatch({ type: "remove_indicator_exit", rowId })
            }
            onPatchIndicatorExit={(rowId, patch) =>
              dispatch({ type: "patch_indicator_exit", rowId, patch })
            }
          />

          {/* Save form */}
          <GlassmorphismCard hover={false}>
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Save className="h-4 w-4 text-accent-blue" />
                <h3 className="font-semibold text-sm">
                  {state.loadedTemplateId
                    ? "Update template"
                    : "Save as template"}
                </h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-[1fr_2fr] gap-3">
                <div className="space-y-1">
                  <label
                    htmlFor="exit-template-name"
                    className="text-[10px] uppercase tracking-wide text-muted-foreground"
                  >
                    Template Name *
                  </label>
                  <Input
                    id="exit-template-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="2% target + 1% SL"
                    maxLength={128}
                  />
                </div>
                <div className="space-y-1">
                  <label
                    htmlFor="exit-template-desc"
                    className="text-[10px] uppercase tracking-wide text-muted-foreground"
                  >
                    Description (optional)
                  </label>
                  <Input
                    id="exit-template-desc"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Kya situation mein use karna hai..."
                    maxLength={2000}
                  />
                </div>
              </div>
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <p
                  className={cn(
                    "text-[11px]",
                    canSave ? "text-profit" : "text-muted-foreground",
                  )}
                >
                  {canSave
                    ? "Looks good — save karne ke liye ready hai"
                    : !hasAnyExit
                      ? "Kam se kam ek exit rule daalo (target / SL / trailing / partial / square-off / indicator / reverse-signal)"
                      : !name.trim()
                        ? "Template ka name daalo"
                        : "Saving..."}
                </p>
                <GlowButton
                  size="sm"
                  onClick={handleSave}
                  disabled={!canSave}
                  type="button"
                >
                  <BookmarkPlus className="h-3.5 w-3.5" />
                  {state.loadedTemplateId
                    ? "Update Template"
                    : "Save Template"}
                </GlowButton>
              </div>
            </div>
          </GlassmorphismCard>
        </div>

        {/* Templates sidebar */}
        <aside className="space-y-3 lg:sticky lg:top-4 self-start">
          <GlassmorphismCard hover={false}>
            <div className="space-y-3">
              <header className="space-y-1">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-accent-purple" />
                  Saved Templates
                </h3>
                <p className="text-[10px] text-muted-foreground">
                  Click to load. Edit karke update karo, ya delete karo.
                </p>
              </header>
              {templatesResp && templatesResp.count > 0 ? (
                <div className="space-y-2 max-h-[520px] overflow-y-auto pr-1">
                  {templatesResp.templates.map((tpl) => (
                    <ExitTemplateCard
                      key={tpl.id}
                      template={tpl}
                      active={tpl.id === state.loadedTemplateId}
                      onLoad={handleLoad}
                      onDelete={handleDelete}
                    />
                  ))}
                </div>
              ) : (
                <div className="rounded-lg bg-white/[0.02] border border-white/[0.04] p-3 text-[11px] text-muted-foreground leading-relaxed">
                  Abhi koi saved template nahi. Exit rules banao + naam
                  do, phir save karo. Yeh sidebar populate ho jayega.
                </div>
              )}
              {state.loadedTemplateId ? (
                <Badge className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 text-[10px] uppercase">
                  Editing template
                </Badge>
              ) : null}
            </div>
          </GlassmorphismCard>
        </aside>
      </div>
    </motion.div>
  );
}

// ─── Helpers — translate between wire shape and builder state ────────

function hasAnyExitPrimitive(exit: ExitState): boolean {
  // Mirror the Pydantic ``_at_least_one_exit`` rule on ``ExitRules``.
  // Only requires *some* primitive to be non-empty; the backend
  // catches deeper shape errors (target > stop, partial-qty sum,
  // HH:MM regex) on POST.
  return (
    exit.targetPercent.trim() !== "" ||
    exit.stopLossPercent.trim() !== "" ||
    exit.trailingStopPercent.trim() !== "" ||
    exit.squareOffTime.trim() !== "" ||
    exit.partialExits.length > 0 ||
    exit.indicatorExits.length > 0 ||
    exit.reverseSignalExit
  );
}

function parseOptionalNumber(raw: string): number | undefined {
  const t = raw.trim();
  if (t === "") return undefined;
  const n = Number(t);
  return Number.isFinite(n) ? n : undefined;
}

function toWireExitRules(exit: ExitState): Record<string, unknown> {
  // camelCase keys — match the ``ExitRules`` Pydantic aliases.
  const out: Record<string, unknown> = {};
  const t = parseOptionalNumber(exit.targetPercent);
  const s = parseOptionalNumber(exit.stopLossPercent);
  const tr = parseOptionalNumber(exit.trailingStopPercent);
  if (t !== undefined) out.targetPercent = t;
  if (s !== undefined) out.stopLossPercent = s;
  if (tr !== undefined) out.trailingStopPercent = tr;
  if (exit.squareOffTime.trim() !== "") {
    out.squareOffTime = exit.squareOffTime.trim();
  }
  if (exit.partialExits.length > 0) {
    out.partialExits = exit.partialExits.map((p) => ({
      qtyPercent: Number(p.qtyPercent),
      targetPercent: Number(p.targetPercent),
    }));
  }
  if (exit.indicatorExits.length > 0) {
    out.indicatorExits = exit.indicatorExits.map(toWireCondition);
  }
  if (exit.reverseSignalExit) out.reverseSignalExit = true;
  return out;
}

function toWireCondition(row: ConditionRow): Record<string, unknown> {
  switch (row.type) {
    case "indicator":
      return {
        type: "indicator",
        left: row.left,
        op: row.op,
        ...(row.rhsKind === "indicator"
          ? { right: row.right }
          : { value: numericValue(row.value) }),
      };
    case "candle":
      return { type: "candle", pattern: row.pattern };
    case "time":
      return {
        type: "time",
        op: row.op,
        value: row.value,
        ...(row.end ? { end: row.end } : {}),
      };
    case "price":
      return {
        type: "price",
        op: row.op,
        value: numericValue(row.value),
      };
  }
}

function numericValue(raw: string | number): number {
  if (typeof raw === "number") return raw;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : 0;
}

function hydrateTemplate(
  template: ExitTemplateCardData,
  catalogue: ReadonlyArray<IndicatorMetadata>,
): BuilderState {
  const wire = (template.exit_rules ?? {}) as Record<string, unknown>;

  // Indicator hydration first — the indicator-exit conditions reference
  // these by id. Indicators whose registry entry has gone away are
  // silently skipped; conditions referencing them surface the empty
  // selection state and the user re-binds manually.
  type WireIndicator = {
    id: string;
    type: string;
    params?: Record<string, unknown>;
  };
  const indicators = (
    template as unknown as { indicators_used?: WireIndicator[] }
  ).indicators_used ?? [];
  const metaByType = new Map<string, IndicatorMetadata>(
    catalogue.map((m) => [m.id, m]),
  );
  const selectedIndicators: SelectedIndicator[] = [];
  for (const ind of indicators) {
    const meta = metaByType.get(ind.type);
    if (!meta) continue;
    selectedIndicators.push({
      id: ind.id,
      type: ind.type,
      label: meta.name,
      params: (ind.params ?? {}) as Record<string, number | string>,
      meta,
    });
  }

  // Wire conditions → builder rows (fresh client rowIds for stable keys).
  type WireCondition = {
    type: ConditionType;
    [key: string]: unknown;
  };
  const wireExits = (wire.indicatorExits as WireCondition[]) ?? [];
  const indicatorExits: ConditionRow[] = wireExits.map((c) => {
    if (c.type === "indicator") {
      const hasRight = "right" in c && typeof c.right === "string";
      return {
        rowId: makeId(),
        type: "indicator",
        left: typeof c.left === "string" ? c.left : "",
        op: (typeof c.op === "string" ? c.op : ">") as IndicatorOp,
        rhsKind: hasRight ? "indicator" : "value",
        right: hasRight ? (c.right as string) : "",
        value: !hasRight && c.value != null ? String(c.value) : "",
      };
    }
    if (c.type === "candle") {
      return {
        rowId: makeId(),
        type: "candle",
        pattern: (typeof c.pattern === "string"
          ? c.pattern
          : "bullish") as CandlePattern,
      };
    }
    if (c.type === "time") {
      return {
        rowId: makeId(),
        type: "time",
        op: (typeof c.op === "string" ? c.op : "after") as TimeOp,
        value: typeof c.value === "string" ? c.value : "",
        end: typeof c.end === "string" ? c.end : "",
      };
    }
    return {
      rowId: makeId(),
      type: "price",
      op: (typeof c.op === "string" ? c.op : ">") as PriceOp,
      value: c.value != null ? String(c.value) : "",
    };
  });

  // Partial exits: numbers → strings (form inputs are string-bound).
  type WirePartial = { qtyPercent?: number; targetPercent?: number };
  const wirePartials = (wire.partialExits as WirePartial[]) ?? [];
  const partialExits: PartialExitRow[] = wirePartials.map((p) => ({
    rowId: makeId(),
    qtyPercent: p.qtyPercent != null ? String(p.qtyPercent) : "",
    targetPercent: p.targetPercent != null ? String(p.targetPercent) : "",
  }));

  const exit: ExitState = {
    targetPercent:
      typeof wire.targetPercent === "number"
        ? String(wire.targetPercent)
        : "",
    stopLossPercent:
      typeof wire.stopLossPercent === "number"
        ? String(wire.stopLossPercent)
        : "",
    trailingStopPercent:
      typeof wire.trailingStopPercent === "number"
        ? String(wire.trailingStopPercent)
        : "",
    squareOffTime:
      typeof wire.squareOffTime === "string" ? wire.squareOffTime : "",
    partialExits,
    indicatorExits,
    reverseSignalExit: wire.reverseSignalExit === true,
  };

  return {
    exit,
    selectedIndicators,
    loadedTemplateId: template.id,
  };
}
