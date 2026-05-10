"use client";

/**
 * Standalone Entry Builder — author one ``EntryRules`` block in
 * isolation and save it as a reusable template.
 *
 * Reuses the Expert Builder's :class:`IndicatorSection` and
 * :class:`EntrySection` primitives unchanged — this page just owns
 * a slimmer reducer (only the entry-relevant slice) plus a
 * template-management sidebar that talks to ``/api/templates/entry``.
 *
 * The Expert / Beginner / Intermediate builders are NOT touched.
 * Phase 2 ships an "Apply template to current strategy" affordance
 * that copies the saved template into a strategy's entry block.
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

import { EntrySection } from "@/components/strategies/expert-builder/entry-section";
import { IndicatorSection } from "@/components/strategies/expert-builder/indicator-section";
import {
  type CandlePattern,
  type ConditionRow,
  type ConditionType,
  type EntryOperator,
  type IndicatorOp,
  type PriceOp,
  type SelectedIndicator,
  type Side,
  type TimeOp,
  makeId,
} from "@/components/strategies/expert-builder/builder-types";
import {
  EntryTemplateCard,
  type EntryTemplateCardData,
} from "@/components/strategies/entry-template-card";

// ─── State machine ─────────────────────────────────────────────────────

interface BuilderState {
  side: Side;
  operator: EntryOperator;
  selectedIndicators: SelectedIndicator[];
  conditions: ConditionRow[];
  loadedTemplateId: string | null;
}

const INITIAL_STATE: BuilderState = {
  side: "BUY",
  operator: "AND",
  selectedIndicators: [],
  conditions: [],
  loadedTemplateId: null,
};

type Action =
  | { type: "set_side"; side: Side }
  | { type: "set_operator"; operator: EntryOperator }
  | { type: "add_indicator"; indicator: SelectedIndicator }
  | { type: "remove_indicator"; id: string }
  | { type: "add_condition"; conditionType: ConditionType }
  | { type: "remove_condition"; rowId: string }
  | { type: "patch_condition"; rowId: string; patch: Partial<ConditionRow> }
  | { type: "load_template"; payload: BuilderState }
  | { type: "reset" };

function reducer(state: BuilderState, action: Action): BuilderState {
  switch (action.type) {
    case "set_side":
      return { ...state, side: action.side };
    case "set_operator":
      return { ...state, operator: action.operator };
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
        conditions: state.conditions.map((c) =>
          clearIndicatorRefs(c, action.id),
        ),
      };
    }
    case "add_condition":
      return {
        ...state,
        conditions: [
          ...state.conditions,
          newConditionOfType(action.conditionType, state.selectedIndicators),
        ],
      };
    case "remove_condition":
      return {
        ...state,
        conditions: state.conditions.filter((c) => c.rowId !== action.rowId),
      };
    case "patch_condition":
      return {
        ...state,
        conditions: state.conditions.map((c) =>
          c.rowId === action.rowId ? mergeConditionPatch(c, action.patch) : c,
        ),
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

interface EntryTemplateListResponse {
  templates: EntryTemplateCardData[];
  count: number;
}

// ─── Page ──────────────────────────────────────────────────────────────

export default function StandaloneEntryBuilderPage() {
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
  } = useApi<EntryTemplateListResponse>("/templates/entry", {
    templates: [],
    count: 0,
  });

  const canSave =
    name.trim().length > 0 &&
    state.conditions.length > 0 &&
    !submitting;

  async function handleSave() {
    if (!canSave) return;
    setSubmitting(true);
    try {
      const body = {
        name: name.trim(),
        description: description.trim() || null,
        side: state.side,
        operator: state.operator,
        conditions: state.conditions.map(toWireCondition),
        indicators_used: state.selectedIndicators.map((ind) => ({
          id: ind.id,
          type: ind.type,
          params: ind.params,
        })),
      };
      if (state.loadedTemplateId) {
        await api.put(`/templates/entry/${state.loadedTemplateId}`, body);
        toast.success("Template update ho gaya 🎉");
      } else {
        await api.post("/templates/entry", body);
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

  function handleLoad(template: EntryTemplateCardData) {
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
      await api.delete(`/templates/entry/${templateId}`);
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
            Entry Conditions Builder
          </h1>
          <p className="text-xs text-muted-foreground max-w-2xl leading-relaxed">
            Sirf entry conditions banao — reusable template ke liye.
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

          <EntrySection
            side={state.side}
            onSideChange={(s) => dispatch({ type: "set_side", side: s })}
            operator={state.operator}
            onOperatorChange={(op) =>
              dispatch({ type: "set_operator", operator: op })
            }
            indicators={state.selectedIndicators}
            conditions={state.conditions}
            onAddCondition={(t) =>
              dispatch({ type: "add_condition", conditionType: t })
            }
            onRemoveCondition={(rowId) =>
              dispatch({ type: "remove_condition", rowId })
            }
            onPatchCondition={(rowId, patch) =>
              dispatch({ type: "patch_condition", rowId, patch })
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
                    htmlFor="entry-template-name"
                    className="text-[10px] uppercase tracking-wide text-muted-foreground"
                  >
                    Template Name *
                  </label>
                  <Input
                    id="entry-template-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="RSI overbought entry"
                    maxLength={128}
                  />
                </div>
                <div className="space-y-1">
                  <label
                    htmlFor="entry-template-desc"
                    className="text-[10px] uppercase tracking-wide text-muted-foreground"
                  >
                    Description (optional)
                  </label>
                  <Input
                    id="entry-template-desc"
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
                    : state.conditions.length === 0
                      ? "At least 1 condition add karo"
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
                    <EntryTemplateCard
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
                  Abhi koi saved template nahi. Conditions banao + naam
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
  template: EntryTemplateCardData,
  catalogue: ReadonlyArray<IndicatorMetadata>,
): BuilderState {
  // Server-side conditions → builder-state condition rows. Each
  // gets a fresh client-side ``rowId`` so React keys stay stable.
  type WireCondition = {
    type: ConditionType;
    [key: string]: unknown;
  };
  const wire = (template.conditions as unknown as WireCondition[]) ?? [];
  const conditions: ConditionRow[] = wire.map((c) => {
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

  // Indicator hydration needs the catalogue — ``SelectedIndicator``
  // carries ``label`` + ``meta`` which only the registry knows.
  // Indicators whose registry entry has gone away (renamed, dropped)
  // are silently skipped; conditions that referenced them will show
  // the empty selection state and the user can re-bind manually.
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

  return {
    side: (template.side === "SELL" ? "SELL" : "BUY") as Side,
    operator: (template.operator === "OR" ? "OR" : "AND") as EntryOperator,
    selectedIndicators,
    conditions,
    loadedTemplateId: template.id,
  };
}
