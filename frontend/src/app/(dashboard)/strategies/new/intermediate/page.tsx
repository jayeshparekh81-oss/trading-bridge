"use client";

/**
 * Intermediate Builder — single-page strategy authoring (Phase 5B).
 *
 * Sections (all visible at once, not a wizard):
 *   1. Name + side
 *   2. Indicator picker (search, category chips, configure form, list)
 *   3. Entry conditions (AND-joined rows; OR grouping is expert-only)
 *   4. Exit rules (target + stop loss + optional trailing)
 *   5. Risk caps (4 optional caps)
 *   6. Strategy JSON preview (collapsed by default)
 *   7. Trust + Truth panels (placeholders — Phase 6 wires real data)
 *
 * On submit: client-side validate → POST /api/strategies → redirect
 * to /strategies/{id}/backtest, which auto-runs the backtest in its
 * own ``useEffect``.
 */

import { useEffect, useMemo, useReducer, useState } from "react";
import {
  CandleSourcePicker,
  makeDefaultPickerValue,
  stashCandlesRequest,
  type CandleSourcePickerValue,
} from "@/components/strategies/candle-source-picker";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  X,
  Save,
  Sparkles,
  Settings,
  ShieldCheck,
  ShieldQuestion,
  AlertTriangle,
  PlayCircle,
  Check,
} from "lucide-react";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { IndicatorMetadata } from "@/components/strategies/indicator-library";

import { BuilderOnboardingModal } from "@/components/strategies/builder-onboarding-modal";
import { STRATEGY_MODE_STORAGE_KEY } from "@/components/strategies/mode-selector";
import { IndicatorPicker } from "@/components/strategies/intermediate-builder/indicator-picker";
import { ConditionBuilder } from "@/components/strategies/intermediate-builder/condition-builder";
import { ExitBuilder } from "@/components/strategies/intermediate-builder/exit-builder";
import { RiskBuilder } from "@/components/strategies/intermediate-builder/risk-builder";
import { StrategyJsonPreview } from "@/components/strategies/intermediate-builder/strategy-json-preview";
import { AlgoMitraSectionProvider } from "@/components/algomitra/section-context";
import type { BuilderSection } from "@/components/algomitra/coaching-tips-data";
import {
  buildStrategyJson,
  validateBuilderState,
  INITIAL_BUILDER_STATE,
  type BuilderState,
  type ConditionRow,
  type RiskState,
  type SelectedIndicator,
  type Side,
} from "@/components/strategies/intermediate-builder/builder-types";


// ─── State machine ─────────────────────────────────────────────────────


type Action =
  | { type: "set_name"; name: string }
  | { type: "set_side"; side: Side }
  | { type: "add_indicator"; indicator: SelectedIndicator }
  | { type: "remove_indicator"; id: string }
  | { type: "add_condition" }
  | { type: "remove_condition"; rowId: string }
  | { type: "patch_condition"; rowId: string; patch: Partial<ConditionRow> }
  | {
      type: "patch_exit";
      patch: {
        targetPercent?: number;
        stopLossPercent?: number;
        trailingEnabled?: boolean;
        trailingPercent?: number;
      };
    }
  | { type: "set_risk"; risk: RiskState };

function reducer(state: BuilderState, action: Action): BuilderState {
  switch (action.type) {
    case "set_name":
      return { ...state, name: action.name };
    case "set_side":
      return { ...state, side: action.side };
    case "add_indicator":
      return {
        ...state,
        selectedIndicators: [...state.selectedIndicators, action.indicator],
      };
    case "remove_indicator": {
      const nextIndicators = state.selectedIndicators.filter(
        (i) => i.id !== action.id,
      );
      // Wipe references to the removed indicator from any condition row
      // so we never serialise a dangling id.
      const nextConditions = state.conditions.map<ConditionRow>((c) => ({
        ...c,
        left: c.left === action.id ? "" : c.left,
        right: c.right === action.id ? "" : c.right,
      }));
      return {
        ...state,
        selectedIndicators: nextIndicators,
        conditions: nextConditions,
      };
    }
    case "add_condition": {
      const firstId = state.selectedIndicators[0]?.id ?? "";
      const newRow: ConditionRow = {
        rowId: makeRowId(),
        left: firstId,
        op: "<",
        rhsKind: "value",
        right: "",
        value: "",
      };
      return { ...state, conditions: [...state.conditions, newRow] };
    }
    case "remove_condition":
      return {
        ...state,
        conditions: state.conditions.filter((c) => c.rowId !== action.rowId),
      };
    case "patch_condition":
      return {
        ...state,
        conditions: state.conditions.map((c) =>
          c.rowId === action.rowId ? { ...c, ...action.patch } : c,
        ),
      };
    case "patch_exit":
      return { ...state, ...action.patch };
    case "set_risk":
      return { ...state, risk: action.risk };
  }
}


// ─── Page ──────────────────────────────────────────────────────────────


interface CreatedStrategy {
  id: string;
  name: string;
}

export default function IntermediateBuilderPage() {
  const router = useRouter();
  const [state, dispatch] = useReducer(reducer, INITIAL_BUILDER_STATE);
  const [submitState, setSubmitState] = useState<SubmitState>({ type: "idle" });
  const [candlePicker, setCandlePicker] = useState<CandleSourcePickerValue>(
    () => makeDefaultPickerValue("synthetic"),
  );

  // Remember the level so ``/strategies/new`` (the smart-default
  // redirector) lands the user back here on their next Create.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(STRATEGY_MODE_STORAGE_KEY, "intermediate");
    } catch {
      // Strict-storage / private-browsing — non-fatal.
    }
  }, []);

  const {
    data: catalogue,
    isLoading: catalogueLoading,
    error: catalogueError,
  } = useApi<IndicatorMetadata[]>("/strategies/indicators", []);

  const validationError = useMemo(
    () => validateBuilderState(state),
    [state],
  );

  // Build a payload preview for the JSON card. If the state isn't
  // submittable we still want a representative blob so the user can
  // see what's missing — generate with a placeholder id and fall back
  // to a partial preview when the serializer would otherwise refuse.
  const payloadPreview = useMemo(() => {
    if (validationError) {
      return buildPartialPreview(state);
    }
    return buildStrategyJson(state, "<generated-on-submit>");
  }, [state, validationError]);

  async function handleSubmit() {
    if (validationError) {
      setSubmitState({ type: "error", message: validationError });
      return;
    }
    if (candlePicker.validation_error) {
      setSubmitState({ type: "error", message: candlePicker.validation_error });
      return;
    }
    setSubmitState({ type: "submitting" });
    try {
      const id = makeStrategyId();
      const payload = buildStrategyJson(state, id);
      const created = await api.post<CreatedStrategy>("/strategies", {
        strategy_json: payload,
      });
      // Stash the candle source so the backtest page picks it up on
      // mount. Synthetic / no-request paths clear the slot.
      stashCandlesRequest(candlePicker);
      router.push(`/strategies/${created.id}/backtest`);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : "Strategy save nahi ho payi. Network ya backend issue.";
      setSubmitState({ type: "error", message: msg });
    }
  }

  // Last-focused section drives the AlgoMitra coaching panel. We
  // detect it via ``onFocusCapture`` on the page wrapper — any focus
  // event that bubbles up checks ``event.target.closest`` against
  // the per-section ``data-algomitra-section`` attribute and updates
  // the active section without touching the inner section
  // components. Default ``"indicators"`` mirrors the page's natural
  // top-down reading order.
  const [activeSection, setActiveSection] = useState<BuilderSection>(
    "indicators",
  );
  const handleFocusCapture: React.FocusEventHandler<HTMLDivElement> = (e) => {
    const target = e.target as HTMLElement | null;
    if (!target) return;
    const block = target.closest<HTMLElement>("[data-algomitra-section]");
    const next = block?.dataset.algomitraSection as BuilderSection | undefined;
    if (next && next !== activeSection) {
      setActiveSection(next);
    }
  };

  return (
    <AlgoMitraSectionProvider section={activeSection}>
      <BuilderOnboardingModal />
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.25 }}
        className="p-4 md:p-6 lg:p-8 max-w-5xl mx-auto space-y-6"
        onFocusCapture={handleFocusCapture}
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
            Intermediate Builder
          </h1>
          <p className="text-sm text-muted-foreground max-w-2xl">
            Pure indicator library, custom conditions (AND only), exit +
            risk caps. OR grouping aur partial exits expert mode mein
            milenge.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/marketplace"
            className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-white/[0.04] text-muted-foreground hover:bg-white/[0.06] hover:text-foreground transition-colors"
            data-testid="builder-marketplace-crosslink"
          >
            Or pick a proven one
            <ArrowRight className="h-3 w-3" />
          </Link>
          <Link
            href="/strategies"
            className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-white/[0.04] text-muted-foreground hover:bg-white/[0.06] hover:text-foreground transition-colors"
          >
            <X className="h-3 w-3" />
            Cancel
          </Link>
        </div>
      </header>

      {/* 1. Identity */}
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
                placeholder="My intermediate strategy"
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
                  Intermediate
                </Badge>
                <span className="text-[11px] text-muted-foreground">
                  set by route
                </span>
              </div>
            </div>
          </div>
        </div>
      </GlassmorphismCard>

      {/* 2. Indicator picker */}
      <div data-algomitra-section="indicators">
        <IndicatorPicker
          catalogue={catalogue ?? []}
          selected={state.selectedIndicators}
          onAdd={(ind) => dispatch({ type: "add_indicator", indicator: ind })}
          onRemove={(id) => dispatch({ type: "remove_indicator", id })}
          loading={catalogueLoading}
          loadError={catalogueError}
        />
      </div>

      {/* 3. Conditions */}
      <div data-algomitra-section="entry">
        <ConditionBuilder
          side={state.side}
          onSideChange={(s) => dispatch({ type: "set_side", side: s })}
          indicators={state.selectedIndicators}
          conditions={state.conditions}
          onAdd={() => dispatch({ type: "add_condition" })}
          onRemove={(rowId) => dispatch({ type: "remove_condition", rowId })}
          onChange={(rowId, patch) =>
            dispatch({ type: "patch_condition", rowId, patch })
          }
        />
      </div>

      {/* 4. Exit */}
      <div data-algomitra-section="exit">
        <ExitBuilder
          targetPercent={state.targetPercent}
          stopLossPercent={state.stopLossPercent}
          trailingEnabled={state.trailingEnabled}
          trailingPercent={state.trailingPercent}
          onChange={(patch) => dispatch({ type: "patch_exit", patch })}
        />
      </div>

      {/* 5. Risk */}
      <div data-algomitra-section="risk">
        <RiskBuilder
          risk={state.risk}
          onChange={(risk) => dispatch({ type: "set_risk", risk })}
        />
      </div>

      {/* 6. JSON preview */}
      <StrategyJsonPreview
        payload={payloadPreview}
        invalidReason={validationError}
      />

      {/* 7. Trust + Truth placeholders */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <TrustPanelPlaceholder />
        <TruthPanelPlaceholder />
      </div>

      {/* 8. Candle source picker — defaults to synthetic in Intermediate. */}
      <CandleSourcePicker value={candlePicker} onChange={setCandlePicker} />

      {/* Submit bar */}
      <GlassmorphismCard hover={false}>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="space-y-1 min-w-0">
            <h3 className="font-semibold text-sm flex items-center gap-2">
              <Save className="h-4 w-4 text-accent-blue" />
              Save & Backtest
            </h3>
            <p className="text-[11px] text-muted-foreground">
              Backend Pydantic Phase 1 schema ke against revalidate karega;
              fail hua to inline error dikhega.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {submitState.type === "error" ? (
              <span className="text-[11px] text-loss inline-flex items-center gap-1">
                <AlertTriangle className="h-3 w-3" />
                {submitState.message}
              </span>
            ) : validationError === null ? (
              <span
                key="valid-check"
                className="text-[11px] text-profit inline-flex items-center gap-1"
              >
                <Check className="h-3 w-3 check-pulse" />
                Looks good
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
    </AlgoMitraSectionProvider>
  );
}


// ─── Submit reducer ────────────────────────────────────────────────────


type SubmitState =
  | { type: "idle" }
  | { type: "submitting" }
  | { type: "error"; message: string };


// ─── Trust + Truth placeholders ────────────────────────────────────────


function TrustPanelPlaceholder() {
  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-muted-foreground" />
          <h3 className="font-semibold text-sm">Trust Score</h3>
          <Badge className="ml-auto bg-white/[0.04] text-muted-foreground border-white/[0.06]">
            Available after backtest
          </Badge>
        </div>
        <p className="text-[11px] text-muted-foreground leading-relaxed">
          Phase 4 reliability engine (OOS, walk-forward, sensitivity)
          backtest ke saath chalti hai. Score yahin nahi, agle page pe
          dikhega.
        </p>
      </div>
    </GlassmorphismCard>
  );
}


function TruthPanelPlaceholder() {
  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <ShieldQuestion className="h-4 w-4 text-muted-foreground" />
          <h3 className="font-semibold text-sm">Strategy Truth</h3>
          <Badge className="ml-auto bg-white/[0.04] text-muted-foreground border-white/[0.06]">
            Coming soon
          </Badge>
        </div>
        <p className="text-[11px] text-muted-foreground leading-relaxed">
          Truth Engine (fake-backtest detection, overfitting + cost
          warnings) Phase 6 frontend integration ke saath jude ga.
        </p>
      </div>
    </GlassmorphismCard>
  );
}


// ─── Helpers ───────────────────────────────────────────────────────────


function makeStrategyId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `strategy_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}


function makeRowId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `row_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}


/**
 * When ``state`` is incomplete the strict ``buildStrategyJson`` would
 * still serialise (it doesn't enforce business rules), but we want the
 * preview to surface as much of the state as possible — including
 * incomplete condition rows — so the user can see *exactly* which keys
 * are wrong before fixing them. We just stringify the live state and
 * let the JSON card render it; the validation banner explains why
 * submit is blocked.
 */
function buildPartialPreview(state: BuilderState): unknown {
  return {
    note: "Preview — abhi submit-ready nahi hai. Banner mein wajah dekho.",
    name: state.name,
    side: state.side,
    indicators: state.selectedIndicators.map((ind) => ({
      id: ind.id,
      type: ind.type,
      params: ind.params,
    })),
    conditions: state.conditions,
    exit: {
      targetPercent: state.targetPercent,
      stopLossPercent: state.stopLossPercent,
      ...(state.trailingEnabled
        ? { trailingStopPercent: state.trailingPercent }
        : {}),
    },
    risk: state.risk,
  };
}
