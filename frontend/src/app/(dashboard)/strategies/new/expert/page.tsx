"use client";

/**
 * Expert Builder — tabbed strategy authoring (Phase 5B).
 *
 * Tabs (5): Indicators | Entry | Exit | Risk | JSON.
 *
 * Differences vs intermediate:
 *   * Indicator catalogue includes EXPERIMENTAL (drops only coming_soon).
 *   * Entry conditions support all four schema types
 *     (indicator/candle/time/price) with AND/OR top-level operator.
 *     Nested grouping is not exposed because the Phase 1 schema's
 *     ``EntryRules.conditions`` is a flat list with one operator —
 *     richer logic must wait for a schema upgrade or be authored via
 *     the JSON tab (which still validates at the backend).
 *   * Exit primitives include partial exits, trailing stop, square-off
 *     time, indicator-driven exits, and reverse-signal exit.
 *   * Risk caps + a robustness toggle persisted to sessionStorage so a
 *     future, additive update to ``/strategies/{id}/backtest`` can
 *     opt-in via ``include_sensitivity`` without changing this builder.
 *   * Raw JSON tab: read+write, validate-on-blur, ``Apply`` overwrites
 *     builder state, ``Sync`` refreshes the text from builder state.
 *
 * On submit: ``validateExpertState`` → POST /api/strategies → push to
 * ``/strategies/{id}/backtest`` (existing destination auto-runs the
 * backtest in its own ``useEffect``).
 */

import { useMemo, useReducer, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  X,
  Save,
  Settings,
  Layers,
  Workflow,
  Target,
  ShieldCheck,
  FileJson,
  PlayCircle,
  AlertTriangle,
  Sparkles,
  ShieldQuestion,
  Activity,
  Zap,
} from "lucide-react";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import type { IndicatorMetadata } from "@/components/strategies/indicator-library";

import { IndicatorSection } from "@/components/strategies/expert-builder/indicator-section";
import { EntrySection } from "@/components/strategies/expert-builder/entry-section";
import { ExitSection } from "@/components/strategies/expert-builder/exit-section";
import { RiskSection } from "@/components/strategies/expert-builder/risk-section";
import { JsonSection } from "@/components/strategies/expert-builder/json-section";
import {
  buildStrategyJson,
  INITIAL_EXPERT_STATE,
  makeId,
  persistRobustnessPreference,
  validateExpertState,
  type ConditionRow,
  type ConditionType,
  type EntryOperator,
  type ExitState,
  type ExpertState,
  type PartialExitRow,
  type RiskState,
  type SelectedIndicator,
  type Side,
} from "@/components/strategies/expert-builder/builder-types";


// ─── State machine ─────────────────────────────────────────────────────


type Action =
  | { type: "set_name"; name: string }
  | { type: "set_side"; side: Side }
  | { type: "set_entry_operator"; operator: EntryOperator }
  | { type: "add_indicator"; indicator: SelectedIndicator }
  | { type: "remove_indicator"; id: string }
  | { type: "add_condition"; conditionType: ConditionType }
  | { type: "remove_condition"; rowId: string }
  | { type: "patch_condition"; rowId: string; patch: Partial<ConditionRow> }
  | { type: "patch_exit"; patch: Partial<ExitState> }
  | { type: "add_partial" }
  | { type: "remove_partial"; rowId: string }
  | {
      type: "patch_partial";
      rowId: string;
      patch: Partial<PartialExitRow>;
    }
  | { type: "add_indicator_exit"; conditionType: ConditionType }
  | { type: "remove_indicator_exit"; rowId: string }
  | {
      type: "patch_indicator_exit";
      rowId: string;
      patch: Partial<ConditionRow>;
    }
  | { type: "set_risk"; risk: RiskState }
  | { type: "set_robustness"; enabled: boolean }
  | { type: "replace_state"; state: ExpertState };

function reducer(state: ExpertState, action: Action): ExpertState {
  switch (action.type) {
    case "set_name":
      return { ...state, name: action.name };
    case "set_side":
      return { ...state, side: action.side };
    case "set_entry_operator":
      return { ...state, entryOperator: action.operator };
    case "add_indicator":
      return {
        ...state,
        selectedIndicators: [...state.selectedIndicators, action.indicator],
      };
    case "remove_indicator": {
      const nextIndicators = state.selectedIndicators.filter(
        (i) => i.id !== action.id,
      );
      return {
        ...state,
        selectedIndicators: nextIndicators,
        conditions: state.conditions.map((c) => clearIndicatorRefs(c, action.id)),
        exit: {
          ...state.exit,
          indicatorExits: state.exit.indicatorExits.map((c) =>
            clearIndicatorRefs(c, action.id),
          ),
        },
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
    case "patch_exit":
      return { ...state, exit: { ...state.exit, ...action.patch } };
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
            c.rowId === action.rowId ? mergeConditionPatch(c, action.patch) : c,
          ),
        },
      };
    case "set_risk":
      return { ...state, risk: action.risk };
    case "set_robustness":
      return { ...state, enableRobustnessTest: action.enabled };
    case "replace_state":
      return action.state;
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
      return { rowId: makeId(), type: "time", op: "after", value: "", end: "" };
    case "price":
      return { rowId: makeId(), type: "price", op: ">", value: "" };
  }
}


/**
 * Patch helper that respects discriminated unions — a partial patch
 * cannot change a row's ``type`` (that requires removing + re-adding).
 */
function mergeConditionPatch(
  row: ConditionRow,
  patch: Partial<ConditionRow>,
): ConditionRow {
  // Drop any ``type`` key from the patch defensively.
  const cleaned: Partial<ConditionRow> = { ...patch };
  if ("type" in cleaned) delete (cleaned as { type?: unknown }).type;
  return { ...row, ...cleaned } as ConditionRow;
}


function clearIndicatorRefs(row: ConditionRow, removedId: string): ConditionRow {
  if (row.type !== "indicator") return row;
  let next = row;
  if (row.left === removedId) next = { ...next, left: "" };
  if (row.right === removedId) next = { ...next, right: "" };
  return next;
}


// ─── Page ──────────────────────────────────────────────────────────────


type TabId = "indicators" | "entry" | "exit" | "risk" | "json";

const TABS: Array<{ id: TabId; label: string; icon: React.ComponentType<{ className?: string }> }> = [
  { id: "indicators", label: "Indicators", icon: Layers },
  { id: "entry", label: "Entry", icon: Workflow },
  { id: "exit", label: "Exit", icon: Target },
  { id: "risk", label: "Risk", icon: ShieldCheck },
  { id: "json", label: "JSON", icon: FileJson },
];


interface CreatedStrategy {
  id: string;
  name: string;
}


type SubmitState =
  | { type: "idle" }
  | { type: "submitting" }
  | { type: "error"; message: string };


export default function ExpertBuilderPage() {
  const router = useRouter();
  const [state, dispatch] = useReducer(reducer, INITIAL_EXPERT_STATE);
  const [activeTab, setActiveTab] = useState<TabId>("indicators");
  const [submitState, setSubmitState] = useState<SubmitState>({ type: "idle" });

  const {
    data: catalogueRaw,
    isLoading: catalogueLoading,
    error: catalogueError,
  } = useApi<IndicatorMetadata[]>("/strategies/indicators", []);
  const catalogue = catalogueRaw ?? [];

  const validationError = useMemo(
    () => validateExpertState(state),
    [state],
  );

  const payloadPreview = useMemo(() => {
    try {
      return buildStrategyJson(state, "<generated-on-submit>");
    } catch {
      // The builder is permissive — the only real failure mode is
      // unreachable until validateExpertState passes. If somehow we end
      // up here, emit a partial preview so the JSON tab isn't blank.
      return state;
    }
  }, [state]);

  async function handleSubmit() {
    if (validationError) {
      setSubmitState({ type: "error", message: validationError });
      return;
    }
    setSubmitState({ type: "submitting" });
    try {
      const id = makeId();
      const payload = buildStrategyJson(state, id);
      const created = await api.post<CreatedStrategy>("/strategies", {
        strategy_json: payload,
      });
      // Hand off the robustness preference to the destination page via
      // sessionStorage. The destination currently sends ``{}`` to the
      // backtest endpoint; once it reads this key, it can opt-in to the
      // sensitivity sweep with no wire-format change required here.
      persistRobustnessPreference(created.id, state.enableRobustnessTest);
      router.push(`/strategies/${created.id}/backtest`);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : "Strategy save nahi ho payi. Network ya backend issue.";
      setSubmitState({ type: "error", message: msg });
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      className="p-4 md:p-6 lg:p-8 max-w-6xl mx-auto space-y-6"
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
            <Settings className="h-6 w-6 text-accent-blue" />
            Expert Builder
          </h1>
          <p className="text-sm text-muted-foreground max-w-3xl">
            Full active + experimental indicator catalogue. AND/OR group
            with all four condition types. Partial exits, trailing stop,
            square-off time. Raw JSON editor. Robustness sweep toggle.
          </p>
        </div>
        <Link
          href="/strategies"
          className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-white/[0.04] text-muted-foreground hover:bg-white/[0.06] hover:text-foreground transition-colors"
        >
          <X className="h-3 w-3" />
          Cancel
        </Link>
      </header>

      {/* Identity */}
      <GlassmorphismCard hover={false}>
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-accent-blue" />
            <h2 className="font-semibold">Strategy Identity</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-[2fr_1fr] gap-3">
            <div className="space-y-1">
              <label
                htmlFor="strategy-name"
                className="text-xs uppercase tracking-wide text-muted-foreground"
              >
                Strategy Name
              </label>
              <Input
                id="strategy-name"
                value={state.name}
                onChange={(e) =>
                  dispatch({ type: "set_name", name: e.target.value })
                }
                placeholder="My expert strategy"
                maxLength={256}
                autoComplete="off"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs uppercase tracking-wide text-muted-foreground">
                Mode
              </label>
              <div className="flex items-center gap-2">
                <Badge className="bg-accent-blue/15 text-accent-blue border-accent-blue/30">
                  Expert
                </Badge>
                <span className="text-[11px] text-muted-foreground">
                  set by route
                </span>
              </div>
            </div>
          </div>
        </div>
      </GlassmorphismCard>

      {/* Tabs */}
      <div
        className="flex flex-wrap gap-1.5 rounded-lg bg-white/[0.02] border border-white/[0.04] p-1.5"
        role="tablist"
      >
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const active = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors",
                active
                  ? "bg-accent-blue/15 text-accent-blue border border-accent-blue/40"
                  : "text-muted-foreground hover:bg-white/[0.04] hover:text-foreground border border-transparent",
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab body */}
      <div className="space-y-6">
        {activeTab === "indicators" ? (
          <IndicatorSection
            catalogue={catalogue}
            selected={state.selectedIndicators}
            onAdd={(ind) => dispatch({ type: "add_indicator", indicator: ind })}
            onRemove={(id) => dispatch({ type: "remove_indicator", id })}
            loading={catalogueLoading}
            loadError={catalogueError}
          />
        ) : null}

        {activeTab === "entry" ? (
          <EntrySection
            side={state.side}
            onSideChange={(s) => dispatch({ type: "set_side", side: s })}
            operator={state.entryOperator}
            onOperatorChange={(op) =>
              dispatch({ type: "set_entry_operator", operator: op })
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
        ) : null}

        {activeTab === "exit" ? (
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
        ) : null}

        {activeTab === "risk" ? (
          <RiskSection
            risk={state.risk}
            onChange={(risk) => dispatch({ type: "set_risk", risk })}
            enableRobustnessTest={state.enableRobustnessTest}
            onRobustnessToggle={(enabled) =>
              dispatch({ type: "set_robustness", enabled })
            }
          />
        ) : null}

        {activeTab === "json" ? (
          <JsonSection
            payload={payloadPreview}
            catalogue={catalogue}
            onApply={(next) => dispatch({ type: "replace_state", state: next })}
          />
        ) : null}
      </div>

      {/* Trust + Truth + Regime + Deviation placeholders */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <PlaceholderCard
          icon={<ShieldCheck className="h-4 w-4 text-muted-foreground" />}
          title="Trust Score"
          badge="Available after backtest"
          body="Phase 4 reliability engine (OOS, walk-forward, sensitivity) backtest ke saath chalti hai."
        />
        <PlaceholderCard
          icon={<ShieldQuestion className="h-4 w-4 text-muted-foreground" />}
          title="Strategy Truth Engine"
          badge="Coming soon"
          body="Fake-backtest detection, overfitting + cost warnings — Phase 6 frontend wiring ke saath."
        />
        <PlaceholderCard
          icon={<Activity className="h-4 w-4 text-muted-foreground" />}
          title="Market Regime Test"
          badge="Coming soon"
          body="Strategy ko bull, bear, sideways regimes pe alag-alag chala ke deviation check."
        />
        <PlaceholderCard
          icon={<Zap className="h-4 w-4 text-muted-foreground" />}
          title="Live vs Backtest Deviation"
          badge="Coming soon"
          body="Live execution metrics ko backtest expectations se compare karke slippage + cost gap surface karega."
        />
      </div>

      {/* Submit bar */}
      <GlassmorphismCard hover={false}>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="space-y-1 min-w-0">
            <h3 className="font-semibold text-sm flex items-center gap-2">
              <Save className="h-4 w-4 text-accent-blue" />
              Save & Backtest
            </h3>
            <p className="text-[11px] text-muted-foreground">
              Backend Pydantic full validation karega; failure inline
              dikhega.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {submitState.type === "error" ? (
              <span className="text-[11px] text-loss inline-flex items-center gap-1">
                <AlertTriangle className="h-3 w-3" />
                {submitState.message}
              </span>
            ) : null}
            <GlowButton
              size="sm"
              onClick={handleSubmit}
              disabled={
                validationError !== null || submitState.type === "submitting"
              }
            >
              <PlayCircle className="h-4 w-4 mr-1.5" />
              {submitState.type === "submitting"
                ? "Saving..."
                : "Save & Run Backtest"}
            </GlowButton>
          </div>
        </div>
        {validationError ? (
          <p className="text-[11px] text-muted-foreground mt-2">
            <span className="text-loss font-medium">Cannot submit:</span>{" "}
            {validationError}
          </p>
        ) : null}
      </GlassmorphismCard>
    </motion.div>
  );
}


function PlaceholderCard({
  icon,
  title,
  badge,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  badge: string;
  body: string;
}) {
  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          {icon}
          <h3 className="font-semibold text-sm">{title}</h3>
          <Badge className="ml-auto bg-white/[0.04] text-muted-foreground border-white/[0.06]">
            {badge}
          </Badge>
        </div>
        <p className="text-[11px] text-muted-foreground leading-relaxed">
          {body}
        </p>
      </div>
    </GlassmorphismCard>
  );
}
