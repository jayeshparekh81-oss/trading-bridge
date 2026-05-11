"use client";

/**
 * First-visit onboarding modal for the Strategy Builder.
 *
 * Auto-shows the first time a user lands on any ``/strategies/new/*``
 * route, then dismisses (with the "Don't show again" checkbox on by
 * default) into a single localStorage flag.
 *
 * Storage keys touched:
 *   * ``tradetri_builder_onboarding_seen``  — "1" once dismissed.
 *   * ``tb_strategy_mode``                  — written when the user
 *     clicks one of the level cards (so the smart-default redirector
 *     and the ModeSelector stay in sync).
 *
 * The modal renders unconditionally on each builder page; the parent
 * passes ``strategyCount`` from ``/strategies`` so we can show a
 * "Recommended for you" pill on the Beginner or Intermediate card.
 * ``strategyCount = null`` (still loading) just hides the pill — the
 * modal itself never blocks on data.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  GraduationCap,
  Sparkles,
  Cpu,
  Check,
  AlertCircle,
} from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useApi } from "@/lib/use-api";
import { STRATEGY_MODE_STORAGE_KEY, type StrategyMode } from "./mode-selector";

export const ONBOARDING_STORAGE_KEY = "tradetri_builder_onboarding_seen";

interface StrategyListResponse {
  strategies: Array<{ id: string }>;
  count: number;
}

interface LevelCard {
  value: StrategyMode;
  emoji: string;
  label: string;
  icon: typeof GraduationCap;
  blurb: string;
  bestFor: string;
  accent: string;
}

const CARDS: ReadonlyArray<LevelCard> = [
  {
    value: "beginner",
    emoji: "🎓",
    label: "Beginner",
    icon: GraduationCap,
    blurb:
      "Step-by-step wizard. Defaults baked in. Up to 5 indicators, simple conditions.",
    bestFor: "First-time users.",
    accent: "text-emerald-300 border-emerald-400/30 bg-emerald-400/[0.06]",
  },
  {
    value: "intermediate",
    emoji: "⚙️",
    label: "Intermediate",
    icon: Sparkles,
    blurb:
      "Full indicator library. Custom conditions (AND only). OR grouping and partial exits in Expert.",
    bestFor: "Users familiar with technical analysis.",
    accent: "text-sky-300 border-sky-400/30 bg-sky-400/[0.06]",
  },
  {
    value: "expert",
    emoji: "🔬",
    label: "Expert",
    icon: Cpu,
    blurb:
      "Pure DSL editor. All features unlocked. Multi-leg, OR conditions, custom logic.",
    bestFor: "Power users who code their own strategies.",
    accent: "text-purple-300 border-purple-400/30 bg-purple-400/[0.06]",
  },
];

export function BuilderOnboardingModal() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [dontShow, setDontShow] = useState(true);
  // Self-fetches so each builder page is a one-liner — the API
  // payload is small and ``useApi``'s SWR-style cache dedupes
  // overlapping calls if the user toggles routes quickly.
  const { data: list, error: listError } = useApi<StrategyListResponse>(
    "/strategies",
    null,
  );
  const strategyCount: number | null =
    list?.count ?? (listError ? 0 : null);
  // Read the localStorage flag inside an effect so SSR and the first
  // client render agree on ``open=false`` — without this gate the
  // modal would briefly flash on hydration before localStorage is
  // checked.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const seen = window.localStorage.getItem(ONBOARDING_STORAGE_KEY);
    if (seen !== "1") {
      setOpen(true);
    }
  }, []);

  const recommended: StrategyMode | null =
    strategyCount === null
      ? null
      : strategyCount >= 6
      ? "intermediate"
      : "beginner";

  function persistDismissal() {
    if (!dontShow) return;
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(ONBOARDING_STORAGE_KEY, "1");
    } catch {
      // localStorage may throw in strict-storage / private-browsing —
      // the modal just shows again next visit, which is acceptable.
    }
  }

  function handleDismiss() {
    persistDismissal();
    setOpen(false);
  }

  function handlePickLevel(level: StrategyMode) {
    persistDismissal();
    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem(STRATEGY_MODE_STORAGE_KEY, level);
      } catch {
        // See above — best-effort.
      }
    }
    setOpen(false);
    router.push(`/strategies/new/${level}`);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <Sparkles className="h-4 w-4 text-accent-blue" />
            Welcome to Strategy Builder
          </DialogTitle>
          <DialogDescription className="pt-1 text-sm">
            Pick your level — each one is a different builder. You can
            switch at any time from the strategies page.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 py-2">
          {CARDS.map((card) => {
            const Icon = card.icon;
            const isRecommended = recommended === card.value;
            return (
              <button
                key={card.value}
                type="button"
                onClick={() => handlePickLevel(card.value)}
                className={cn(
                  "group text-left rounded-lg border p-3 transition-colors",
                  "hover:bg-white/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  card.accent,
                )}
              >
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-1.5">
                    <span className="text-base" aria-hidden="true">
                      {card.emoji}
                    </span>
                    <Icon className="h-3.5 w-3.5" />
                    <span className="text-sm font-semibold">{card.label}</span>
                  </div>
                  {isRecommended ? (
                    <Badge className="text-[9px] uppercase tracking-wide bg-accent-blue/15 text-accent-blue border-accent-blue/30">
                      For you
                    </Badge>
                  ) : null}
                </div>
                <p className="text-[11px] leading-relaxed text-muted-foreground">
                  {card.blurb}
                </p>
                <p className="text-[10px] mt-2 text-muted-foreground/80">
                  <span className="font-medium text-foreground/80">
                    Best for:
                  </span>{" "}
                  {card.bestFor}
                </p>
              </button>
            );
          })}
        </div>

        {recommended === null ? (
          <p className="text-[10px] text-muted-foreground/70 inline-flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />
            Recommendation loads after we read your strategy count.
          </p>
        ) : null}

        <DialogFooter className="gap-3 sm:items-center sm:justify-between flex-col-reverse sm:flex-row">
          <label className="inline-flex items-center gap-2 text-xs text-muted-foreground cursor-pointer select-none">
            <input
              type="checkbox"
              checked={dontShow}
              onChange={(e) => setDontShow(e.target.checked)}
              className="h-3.5 w-3.5 rounded border-white/20 bg-white/[0.04] accent-accent-blue"
            />
            Don&apos;t show again
          </label>
          <Button
            type="button"
            size="sm"
            onClick={handleDismiss}
            className="gap-1"
          >
            <Check className="h-3.5 w-3.5" />
            Got it, let me pick
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
