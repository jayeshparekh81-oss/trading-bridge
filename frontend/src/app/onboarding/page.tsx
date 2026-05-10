"use client";

/**
 * /onboarding — single-page state machine for the 5-step flow.
 *
 * State lives in the parent (this component); each step
 * sub-component is a presentational cluster that calls
 * ``onAdvance`` / ``onSavePreferences`` / ``onComplete`` to drive
 * forward. Keeping the 5 steps in one route simplifies routing +
 * lets back-button + browser refresh restore the user to the
 * step the backend reports — no client-side step persistence
 * needed.
 *
 * Backend API shape: see ``backend/app/strategy_engine/api/onboarding.py``.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowRight,
  CheckCircle2,
  Loader2,
  Sparkles,
  Store,
  Workflow,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { GlowButton } from "@/components/ui/glow-button";
import { Logo } from "@/components/logo";
import { ProgressIndicator } from "@/components/onboarding/progress-indicator";
import { SkipButton } from "@/components/onboarding/skip-button";
import { api, ApiError } from "@/lib/api";
import { trackEventSync } from "@/lib/analytics";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

// ─── Types mirroring the backend's OnboardingState ────────────────────

interface OnboardingState {
  onboarding_step: number;
  is_new_user: boolean;
  onboarding_completed_at: string | null;
  goal: string | null;
  experience: string | null;
}

type Goal =
  | "build_and_backtest"
  | "marketplace_buy"
  | "pine_import"
  | "explore";

type Experience = "new" | "intermediate" | "expert";

// ─── Page ─────────────────────────────────────────────────────────────

export default function OnboardingPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [state, setState] = useState<OnboardingState | null>(null);
  const [busy, setBusy] = useState(false);

  // Pull the current state from the backend on mount. If the user
  // is already complete (step=6), bounce to /strategies — the
  // dashboard's auto-redirect would catch this too, but doing it
  // here avoids a wasted render.
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const fresh = await api.get<OnboardingState>("/onboarding/state");
        if (cancelled) return;
        if (!fresh.is_new_user) {
          router.replace("/strategies");
          return;
        }
        setState(fresh);
        if (user?.id && fresh.onboarding_step === 0) {
          trackEventSync(user.id, "onboarding_started", {});
        }
      } catch {
        if (!cancelled) {
          // If state fetch fails, fall back to step 1 client-side
          // so the user can still proceed — the backend reconciles
          // on the next ``/onboarding/step`` POST.
          setState({
            onboarding_step: 0,
            is_new_user: true,
            onboarding_completed_at: null,
            goal: null,
            experience: null,
          });
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [router, user?.id]);

  // Display step is 1-based. Backend step 0 = "not started",
  // which the UI shows as step 1 (welcome).
  const displayStep = Math.max(1, state?.onboarding_step ?? 1);

  async function advanceTo(nextStep: 2 | 3 | 4 | 5) {
    if (state == null) return;
    setBusy(true);
    try {
      const updated = await api.post<OnboardingState>("/onboarding/step", {
        next_step: nextStep,
      });
      setState(updated);
      if (user?.id) {
        trackEventSync(user.id, "onboarding_step_completed", {
          step: nextStep - 1,
        });
      }
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : "Aage badhne mein dikkat aayi — refresh karo";
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  async function savePreferences(patch: {
    goal?: Goal;
    experience?: Experience;
  }) {
    if (state == null) return;
    try {
      const updated = await api.post<OnboardingState>(
        "/onboarding/preferences",
        patch,
      );
      setState(updated);
    } catch {
      // Preferences are best-effort — failure shouldn't block
      // the flow. The user can always edit them later via
      // /settings.
    }
  }

  async function completeAndGoTo(href: string) {
    if (state == null) return;
    setBusy(true);
    try {
      await api.post("/onboarding/complete", {});
      if (user?.id) {
        trackEventSync(user.id, "onboarding_completed", {
          goal: state.goal ?? null,
          experience: state.experience ?? null,
        });
      }
      router.push(href);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : "Save nahi ho paya — try again";
      toast.error(msg);
      setBusy(false);
    }
  }

  if (state == null) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-accent-blue" />
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6 md:p-10 flex flex-col">
      <div className="flex items-center justify-between gap-3 mb-6">
        <Logo width={40} height={40} variant="icon" />
        <SkipButton atStep={displayStep} />
      </div>

      <div className="flex-1 flex flex-col items-center justify-center gap-6 max-w-2xl mx-auto w-full">
        <ProgressIndicator current={displayStep} />

        <AnimatePresence mode="wait">
          <motion.div
            key={displayStep}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.25 }}
            className="w-full"
          >
            {displayStep === 1 ? (
              <WelcomeStep
                userName={user?.full_name || user?.email?.split("@")[0] || "Trader"}
                busy={busy}
                onAdvance={() => advanceTo(2)}
              />
            ) : null}
            {displayStep === 2 ? (
              <GoalsStep
                value={state.goal as Goal | null}
                busy={busy}
                onSelect={(g) => savePreferences({ goal: g })}
                onAdvance={() => advanceTo(3)}
              />
            ) : null}
            {displayStep === 3 ? (
              <ExperienceStep
                value={state.experience as Experience | null}
                busy={busy}
                onSelect={(e) => savePreferences({ experience: e })}
                onAdvance={() => advanceTo(4)}
              />
            ) : null}
            {displayStep === 4 ? (
              <AlgoMitraStep busy={busy} onAdvance={() => advanceTo(5)} />
            ) : null}
            {displayStep === 5 ? (
              <CtaStep
                goal={state.goal as Goal | null}
                experience={state.experience as Experience | null}
                busy={busy}
                onComplete={completeAndGoTo}
              />
            ) : null}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}

// ─── Step 1: Welcome ──────────────────────────────────────────────────

function WelcomeStep({
  userName,
  busy,
  onAdvance,
}: {
  userName: string;
  busy: boolean;
  onAdvance: () => void;
}) {
  return (
    <GlassmorphismCard hover={false} className="text-center">
      <div className="space-y-5 py-4">
        <div className="space-y-2">
          <Badge className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 text-[10px] uppercase">
            Step 1 — Welcome
          </Badge>
          <h1 className="text-3xl font-bold leading-tight">
            Namaste {userName}! 🇮🇳
          </h1>
          <p className="text-sm text-muted-foreground leading-relaxed max-w-md mx-auto">
            TRADETRI mein swagat hai — India ka first AI-powered trading
            platform. Retail traders ke liye banaya hua, L&T engineer ne.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
          <ValueProp icon={Workflow} title="Strategy banao" body="Beginner se Expert tak — visual builder + Pine import." />
          <ValueProp icon={Sparkles} title="AlgoMitra coaching" body="5 languages, har step pe context-aware tips." />
          <ValueProp icon={Store} title="Marketplace" body="Verified strategies + 90-day forward-test proof." />
        </div>
        <GlowButton
          size="sm"
          onClick={onAdvance}
          disabled={busy}
          type="button"
          className="mt-2"
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ArrowRight className="h-3.5 w-3.5" />}
          Aage badho
        </GlowButton>
      </div>
    </GlassmorphismCard>
  );
}

function ValueProp({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof Workflow;
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3 text-left space-y-1.5">
      <Icon className="h-4 w-4 text-accent-blue" />
      <p className="text-xs font-semibold">{title}</p>
      <p className="text-[11px] text-muted-foreground leading-relaxed">{body}</p>
    </div>
  );
}

// ─── Step 2: Goals ────────────────────────────────────────────────────

const GOAL_OPTIONS: ReadonlyArray<{ value: Goal; label: string; hint: string }> = [
  {
    value: "build_and_backtest",
    label: "Strategy banake backtest karna",
    hint: "Apna trading idea visual builder mein bana ke historical data pe test karna chahta hu.",
  },
  {
    value: "marketplace_buy",
    label: "Marketplace se strategies subscribe karna",
    hint: "Already-tested strategies use karna — Trust + Truth verified.",
  },
  {
    value: "pine_import",
    label: "Pine script import karna",
    hint: "TradingView ka existing Pine code TRADETRI mein convert karna.",
  },
  {
    value: "explore",
    label: "Sirf platform explore karna",
    hint: "Pehle dekhna hai kya milega, baad mein decide karunga.",
  },
];

function GoalsStep({
  value,
  busy,
  onSelect,
  onAdvance,
}: {
  value: Goal | null;
  busy: boolean;
  onSelect: (g: Goal) => void;
  onAdvance: () => void;
}) {
  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-4 py-2">
        <div className="space-y-1 text-center">
          <Badge className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 text-[10px] uppercase">
            Step 2 — Tumhara goal
          </Badge>
          <h2 className="text-xl font-bold">Tum kya karna chahte ho?</h2>
          <p className="text-[11px] text-muted-foreground">
            Ek choose karo — baad mein change kar sakte ho.
          </p>
        </div>
        <div className="space-y-2">
          {GOAL_OPTIONS.map((opt) => (
            <OptionCard
              key={opt.value}
              label={opt.label}
              hint={opt.hint}
              active={value === opt.value}
              onSelect={() => onSelect(opt.value)}
            />
          ))}
        </div>
        <div className="flex justify-center pt-2">
          <GlowButton
            size="sm"
            onClick={onAdvance}
            disabled={busy || value == null}
            type="button"
          >
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ArrowRight className="h-3.5 w-3.5" />}
            Aage badho
          </GlowButton>
        </div>
      </div>
    </GlassmorphismCard>
  );
}

// ─── Step 3: Experience ───────────────────────────────────────────────

const EXPERIENCE_OPTIONS: ReadonlyArray<{
  value: Experience;
  label: string;
  hint: string;
}> = [
  {
    value: "new",
    label: "Naya hu — sikhna hai",
    hint: "Beginner Builder se shuru karenge — guided wizard, sab step-by-step.",
  },
  {
    value: "intermediate",
    label: "1-2 saal ka experience hai",
    hint: "Intermediate Builder — saari sections ek saath, par AlgoMitra ka support hai.",
  },
  {
    value: "expert",
    label: "Pro trader hu",
    hint: "Expert Builder — full control, JSON edit, walk-forward testing, sab kuch.",
  },
];

function ExperienceStep({
  value,
  busy,
  onSelect,
  onAdvance,
}: {
  value: Experience | null;
  busy: boolean;
  onSelect: (e: Experience) => void;
  onAdvance: () => void;
}) {
  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-4 py-2">
        <div className="space-y-1 text-center">
          <Badge className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 text-[10px] uppercase">
            Step 3 — Experience
          </Badge>
          <h2 className="text-xl font-bold">Trading mein kitna experience hai?</h2>
          <p className="text-[11px] text-muted-foreground">
            Iss se hum default builder mode set kar denge — kabhi bhi
            switch kar sakte ho.
          </p>
        </div>
        <div className="space-y-2">
          {EXPERIENCE_OPTIONS.map((opt) => (
            <OptionCard
              key={opt.value}
              label={opt.label}
              hint={opt.hint}
              active={value === opt.value}
              onSelect={() => onSelect(opt.value)}
            />
          ))}
        </div>
        <div className="flex justify-center pt-2">
          <GlowButton
            size="sm"
            onClick={onAdvance}
            disabled={busy || value == null}
            type="button"
          >
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ArrowRight className="h-3.5 w-3.5" />}
            Aage badho
          </GlowButton>
        </div>
      </div>
    </GlassmorphismCard>
  );
}

// ─── Step 4: AlgoMitra intro ──────────────────────────────────────────

function AlgoMitraStep({
  busy,
  onAdvance,
}: {
  busy: boolean;
  onAdvance: () => void;
}) {
  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-4 py-2 text-center">
        <Badge className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 text-[10px] uppercase">
          Step 4 — Meet AlgoMitra
        </Badge>
        <div className="size-12 rounded-full bg-gradient-to-br from-accent-blue to-accent-purple grid place-items-center mx-auto">
          <Sparkles className="h-5 w-5 text-white" />
        </div>
        <h2 className="text-xl font-bold">AlgoMitra hai tumhara AI coach</h2>
        <p className="text-sm text-muted-foreground leading-relaxed max-w-lg mx-auto">
          Builder pages pe right-side panel mein AlgoMitra dikhega — har section pe
          context-aware tips dega. 5 languages mein available: Hinglish,
          हिंदी, ગુજરાતી, தமிழ், বাংলা. Top header pe language switcher hai.
        </p>
        <div className="rounded-lg bg-white/[0.02] border border-white/[0.06] p-3 max-w-md mx-auto text-left">
          <p className="text-[11px] font-semibold mb-1">
            🤖 Sample tip (Hinglish):
          </p>
          <p className="text-[12px] leading-relaxed text-foreground/90">
            &ldquo;Indicators charts ke patterns dikhate hain — jaise EMA trend
            dikhata hai. Beginner ke liye 1-2 indicators kaafi hain — zyada
            confusion karte hain.&rdquo;
          </p>
        </div>
        <GlowButton
          size="sm"
          onClick={onAdvance}
          disabled={busy}
          type="button"
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ArrowRight className="h-3.5 w-3.5" />}
          Aage badho
        </GlowButton>
      </div>
    </GlassmorphismCard>
  );
}

// ─── Step 5: First-strategy CTA ───────────────────────────────────────

function CtaStep({
  goal,
  experience,
  busy,
  onComplete,
}: {
  goal: Goal | null;
  experience: Experience | null;
  busy: boolean;
  onComplete: (href: string) => void;
}) {
  // Default builder mode based on the experience answer.
  const builderHref =
    experience === "new"
      ? "/strategies/new/beginner"
      : experience === "expert"
        ? "/strategies/new/expert"
        : "/strategies/new/intermediate";
  const builderLabel =
    experience === "new"
      ? "Beginner Builder se shuru karo (5 min)"
      : experience === "expert"
        ? "Expert Builder mein jao"
        : "Intermediate Builder try karo";

  // If the user picked marketplace_buy as their goal, surface the
  // marketplace path as the primary CTA instead.
  const primaryHref = goal === "marketplace_buy" ? "/marketplace" : builderHref;
  const primaryLabel =
    goal === "marketplace_buy"
      ? "Marketplace browse karo"
      : builderLabel;

  return (
    <GlassmorphismCard hover={false} className="text-center">
      <div className="space-y-4 py-4">
        <Badge className="bg-profit/15 text-profit border-profit/30 text-[10px] uppercase">
          Step 5 — Final
        </Badge>
        <div className="size-12 rounded-full bg-profit/15 grid place-items-center mx-auto">
          <CheckCircle2 className="h-5 w-5 text-profit" />
        </div>
        <h2 className="text-2xl font-bold">Ready ho? 🎉</h2>
        <p className="text-sm text-muted-foreground leading-relaxed max-w-md mx-auto">
          Onboarding complete. Ab pehli strategy banao ya marketplace
          explore karo — choice tumhari.
        </p>
        <div className="flex flex-col items-center gap-2 pt-2">
          <GlowButton
            size="sm"
            onClick={() => onComplete(primaryHref)}
            disabled={busy}
            type="button"
          >
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ArrowRight className="h-3.5 w-3.5" />}
            {primaryLabel}
          </GlowButton>
          {goal !== "marketplace_buy" ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onComplete("/marketplace")}
              disabled={busy}
              type="button"
            >
              Ya phir, marketplace browse karo →
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onComplete(builderHref)}
              disabled={busy}
              type="button"
            >
              Ya phir, apni strategy banao →
            </Button>
          )}
        </div>
      </div>
    </GlassmorphismCard>
  );
}

// ─── Shared option card for steps 2 + 3 ───────────────────────────────

function OptionCard({
  label,
  hint,
  active,
  onSelect,
}: {
  label: string;
  hint: string;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full rounded-lg border p-3 text-left transition-colors",
        active
          ? "bg-accent-blue/[0.08] border-accent-blue/40"
          : "bg-white/[0.02] border-white/[0.06] hover:bg-white/[0.04]",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold">{label}</span>
        {active ? (
          <Badge className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 text-[10px] uppercase">
            Selected
          </Badge>
        ) : null}
      </div>
      <p className="text-[11px] text-muted-foreground mt-1 leading-relaxed">
        {hint}
      </p>
    </button>
  );
}
