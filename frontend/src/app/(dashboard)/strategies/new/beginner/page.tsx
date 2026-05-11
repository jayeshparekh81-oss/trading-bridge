"use client";

/**
 * Beginner Builder — 5-step guided strategy wizard (Phase 5B).
 *
 * Routing:
 *   /strategies/new/beginner   →   POST /api/strategies   →
 *   /strategies/{id}/backtest  (which auto-runs the backtest in its
 *   own ``useEffect``).
 *
 * The wizard never exposes raw StrategyJSON, the indicator library,
 * or advanced controls (AND/OR groups, partial exits, trailing stops).
 * That stays inside the future expert builder. The step-by-step
 * flow + Hinglish copy is the locked beginner-mode UI from the
 * master prompt PHASE 5 spec.
 */

import { useEffect, useReducer, useMemo } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  X,
  Sparkles,
} from "lucide-react";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { celebrationCopy } from "@/lib/celebration";

import { BuilderOnboardingModal } from "@/components/strategies/builder-onboarding-modal";
import { STRATEGY_MODE_STORAGE_KEY } from "@/components/strategies/mode-selector";
import { ProgressStepper } from "@/components/strategies/beginner-builder/progress-stepper";
import { StepGoal } from "@/components/strategies/beginner-builder/step-goal";
import { StepPreset } from "@/components/strategies/beginner-builder/step-preset";
import { StepPreview } from "@/components/strategies/beginner-builder/step-preview";
import { StepRun } from "@/components/strategies/beginner-builder/step-run";
import { BeginnerSyntheticHint } from "@/components/strategies/candle-source-picker";
import { AlgoMitraSectionProvider } from "@/components/algomitra/section-context";
import type { BuilderSection } from "@/components/algomitra/coaching-tips-data";
import {
  GOAL_PRESETS,
  buildStrategyJson,
  defaultStrategyName,
  validateBuildArgs,
  validatePeriodOverrides,
  type BeginnerGoal,
  type PeriodOverrides,
  type StrategyJsonPayload,
} from "@/components/strategies/beginner-builder/presets";

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.25 } },
};

/** Directional slide — used by AnimatePresence in the step body. The
 *  ``custom`` prop is the navigation direction (+1 next, -1 back); the
 *  variant functions pick the entry/exit X axis from it. */
const stepSlide = {
  enter: (dir: number) => ({ x: dir > 0 ? 60 : -60, opacity: 0 }),
  show: {
    x: 0,
    opacity: 1,
    transition: { duration: 0.28, ease: "easeOut" as const },
  },
  leave: (dir: number) => ({
    x: dir > 0 ? -60 : 60,
    opacity: 0,
    transition: { duration: 0.22, ease: "easeIn" as const },
  }),
};


// ─── State machine ─────────────────────────────────────────────────────

type WizardStep = 1 | 2 | 3 | 4;

interface WizardState {
  step: WizardStep;
  /**
   * Direction of the most recent step transition. Drives the slide
   * animation in :class:`AnimatePresence`: ``+1`` slides the new step
   * in from the right, ``-1`` from the left. Initial value is ``+1``
   * so the first paint plays the same enter-from-right transition the
   * user will see when clicking Next.
   */
  direction: 1 | -1;
  goal: BeginnerGoal | null;
  name: string;
  stopLossPercent: number;
  targetPercent: number;
  /** Raw user-entered period strings keyed by indicator id. An entry's
   *  *absence* means "use the preset default"; an empty string means
   *  the user explicitly cleared the field (surfaces a Required
   *  error). Switching goals clears this map so step 2 opens with a
   *  clean preset every time. */
  periodOverrides: PeriodOverrides;
  submitState: "idle" | "submitting" | "error";
  error: string | null;
}

const INITIAL_STATE: WizardState = {
  step: 1,
  direction: 1,
  goal: null,
  name: "",
  stopLossPercent: 1,
  targetPercent: 2,
  periodOverrides: {},
  submitState: "idle",
  error: null,
};

type Action =
  | { type: "select_goal"; goal: BeginnerGoal }
  | { type: "set_risk"; stopLossPercent: number; targetPercent: number }
  | { type: "set_period"; indicatorId: string; raw: string }
  | { type: "set_name"; name: string }
  | { type: "next" }
  | { type: "back" }
  | { type: "submit_start" }
  | { type: "submit_error"; message: string }
  | { type: "submit_retry" };

function reducer(state: WizardState, action: Action): WizardState {
  switch (action.type) {
    case "select_goal": {
      const preset = GOAL_PRESETS[action.goal];
      // Selecting a goal also seeds sensible defaults for SL / Target /
      // name and discards any period overrides — the prior preset's
      // ids may not even exist on the new one, so carrying them
      // forward would render orphaned errors.
      return {
        ...state,
        goal: action.goal,
        stopLossPercent: preset.defaultStopLossPercent,
        targetPercent: preset.defaultTargetPercent,
        periodOverrides: {},
        name: state.name || defaultStrategyName(action.goal),
      };
    }
    case "set_risk":
      return {
        ...state,
        stopLossPercent: action.stopLossPercent,
        targetPercent: action.targetPercent,
      };
    case "set_period": {
      // Keep the raw string in state so the input doesn't snap mid-
      // typing; validation runs on read in StepPreset and at the
      // ``canAdvance`` / submit boundary.
      return {
        ...state,
        periodOverrides: {
          ...state.periodOverrides,
          [action.indicatorId]: action.raw,
        },
      };
    }
    case "set_name":
      return { ...state, name: action.name };
    case "next":
      return {
        ...state,
        direction: 1,
        step: Math.min(4, state.step + 1) as WizardStep,
      };
    case "back":
      return {
        ...state,
        direction: -1,
        step: Math.max(1, state.step - 1) as WizardStep,
      };
    case "submit_start":
      return { ...state, submitState: "submitting", error: null };
    case "submit_error":
      return { ...state, submitState: "error", error: action.message };
    case "submit_retry":
      return { ...state, submitState: "idle", error: null };
  }
}


// ─── Page ──────────────────────────────────────────────────────────────


interface CreatedStrategy {
  id: string;
  name: string;
}

export default function BeginnerBuilderPage() {
  const router = useRouter();
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);

  // Remember the level so ``/strategies/new`` (the smart-default
  // redirector) lands the user back here on their next Create.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(STRATEGY_MODE_STORAGE_KEY, "beginner");
    } catch {
      // Strict-storage / private-browsing — non-fatal.
    }
  }, []);

  /** Disabled state for the per-step "Next" / primary action. */
  const canAdvance = useMemo(() => {
    switch (state.step) {
      case 1:
        return state.goal !== null;
      case 2: {
        if (
          !(state.stopLossPercent > 0) ||
          !(state.targetPercent > state.stopLossPercent)
        ) {
          return false;
        }
        // Block "Next" if any period override is currently invalid —
        // ``StepPreset`` already surfaces the field-level error.
        if (state.goal) {
          const periodErr = validatePeriodOverrides(
            state.goal,
            state.periodOverrides,
          );
          if (periodErr) return false;
        }
        return true;
      }
      case 3:
        return state.goal !== null && state.name.trim().length > 0;
      case 4:
        return state.submitState !== "submitting";
    }
  }, [state]);

  async function handleSubmit() {
    if (state.goal === null) {
      dispatch({ type: "submit_error", message: "Goal nahi chuna gaya." });
      return;
    }
    const id = makeStrategyId();
    const args = {
      id,
      name: state.name.trim(),
      goal: state.goal,
      stopLossPercent: state.stopLossPercent,
      targetPercent: state.targetPercent,
      periodOverrides: state.periodOverrides,
    };
    const validationError = validateBuildArgs(args);
    if (validationError) {
      dispatch({ type: "submit_error", message: validationError });
      return;
    }
    const periodError = validatePeriodOverrides(state.goal, state.periodOverrides);
    if (periodError) {
      dispatch({ type: "submit_error", message: periodError });
      return;
    }

    let payload: StrategyJsonPayload;
    try {
      payload = buildStrategyJson(args);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "StrategyJSON banane mein error.";
      dispatch({ type: "submit_error", message: msg });
      return;
    }

    dispatch({ type: "submit_start" });
    try {
      const created = await api.post<CreatedStrategy>("/strategies", {
        strategy_json: payload,
      });
      toast.success(celebrationCopy("small", "Saved"));
      // Step 5 = the existing backtest result page. It auto-runs the
      // backtest via its own useEffect, so the wizard's job ends here.
      router.push(`/strategies/${created.id}/backtest`);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : "Strategy save nahi ho payi. Network ya backend issue ho sakta hai.";
      dispatch({ type: "submit_error", message: msg });
    }
  }

  // Beginner wizard step → AlgoMitra section. The Beginner flow is a
  // guided preset wizard (goal/preset/preview/run), not literal
  // indicator/entry/exit/risk editing. We pick the section whose
  // coaching content best matches what the user is doing on each
  // step so the panel still gives useful in-context tips:
  //   1 (goal)    → indicators (introduces the concept of trend tools)
  //   2 (preset)  → entry      (preset surfaces entry conditions)
  //   3 (preview) → exit       (preview shows stop-loss + target)
  //   4 (run)     → risk       (run step puts position-size in focus)
  const STEP_TO_SECTION: Record<WizardStep, BuilderSection> = {
    1: "indicators",
    2: "entry",
    3: "exit",
    4: "risk",
  };
  const activeSection = STEP_TO_SECTION[state.step];

  return (
    <AlgoMitraSectionProvider section={activeSection}>
      <BuilderOnboardingModal />
      <motion.div
        initial="hidden"
        animate="show"
        variants={fadeUp}
        className="p-4 md:p-6 lg:p-8 max-w-3xl mx-auto space-y-6"
      >
        {/* Header */}
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="space-y-1">
            <Link
              href="/strategies"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="h-3 w-3" />
              Back to strategies
            </Link>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Sparkles className="h-6 w-6 text-accent-blue" />
              Beginner Builder
            </h1>
            <p className="text-sm text-muted-foreground">
              5 simple steps. Goal chuno, baaki hum sambhal lenge.
            </p>
          </div>
          <Link
            href="/strategies"
            className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-white/[0.04] text-muted-foreground hover:bg-white/[0.06] hover:text-foreground transition-colors"
          >
            <X className="h-3 w-3" />
            Cancel
          </Link>
        </div>
        <ProgressStepper current={state.step} />
      </div>

      {/* Step body — slide horizontally on every navigation. ``mode="wait"``
          ensures the outgoing step finishes its exit before the next step
          starts entering, so the layout doesn't briefly show two cards.
          ``custom={direction}`` lets the variants flip the entry/exit
          axis based on whether the user clicked Next or Back. */}
      <div className="relative overflow-hidden">
        <AnimatePresence mode="wait" custom={state.direction}>
          <motion.div
            key={state.step}
            custom={state.direction}
            variants={stepSlide}
            initial="enter"
            animate="show"
            exit="leave"
          >
            {state.step === 1 ? (
              <StepGoal
                selected={state.goal}
                onSelect={(g) => dispatch({ type: "select_goal", goal: g })}
              />
            ) : state.step === 2 && state.goal ? (
              <StepPreset
                goal={state.goal}
                stopLossPercent={state.stopLossPercent}
                targetPercent={state.targetPercent}
                periodOverrides={state.periodOverrides}
                onChange={(next) => dispatch({ type: "set_risk", ...next })}
                onPeriodChange={(indicatorId, raw) =>
                  dispatch({ type: "set_period", indicatorId, raw })
                }
              />
            ) : state.step === 3 && state.goal ? (
              <StepPreview
                goal={state.goal}
                name={state.name}
                stopLossPercent={state.stopLossPercent}
                targetPercent={state.targetPercent}
                onNameChange={(n) => dispatch({ type: "set_name", name: n })}
              />
            ) : state.step === 4 ? (
              <div className="space-y-3">
                <BeginnerSyntheticHint />
                <StepRun
                  state={state.submitState}
                  error={state.error}
                  onSubmit={handleSubmit}
                  onRetry={() => dispatch({ type: "submit_retry" })}
                />
              </div>
            ) : null}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Footer nav — hidden on step 4 because StepRun owns its own CTA. */}
      {state.step < 4 ? (
        <div className="flex items-center justify-between gap-3 pt-2">
          <Button
            variant="ghost"
            size="sm"
            type="button"
            onClick={() => dispatch({ type: "back" })}
            disabled={state.step === 1}
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>
          <GlowButton
            size="sm"
            onClick={() => dispatch({ type: "next" })}
            disabled={!canAdvance}
          >
            {state.step === 3 ? "Continue to Backtest" : "Next"}
            <ArrowRight className="h-4 w-4 ml-1.5 inline" />
          </GlowButton>
        </div>
      ) : state.submitState === "idle" || state.submitState === "error" ? (
        <div className="flex items-center justify-start">
          <Button
            variant="ghost"
            size="sm"
            type="button"
            onClick={() => dispatch({ type: "back" })}
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>
        </div>
      ) : null}

      {/* Inline validation error on step 4 so users see why submit was blocked */}
      {state.step === 4 && state.submitState === "error" && state.error ? (
        <GlassmorphismCard hover={false} className="border-loss/30">
          <p className="text-xs text-loss leading-relaxed">{state.error}</p>
        </GlassmorphismCard>
      ) : null}
      </motion.div>
    </AlgoMitraSectionProvider>
  );
}


// ─── Helpers ───────────────────────────────────────────────────────────


function makeStrategyId(): string {
  // Mirror the existing pattern from src/hooks/useAlgoMitra.ts so we
  // degrade gracefully on browsers without crypto.randomUUID.
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `strategy_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}
