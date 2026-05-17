/**
 * OnboardingTour — orchestrates the first-login flow:
 *   1. Welcome modal
 *   2. 5-step react-joyride tour (custom-styled via TourStep)
 *   3. Success screen with two CTAs
 *
 * State is owned by `useOnboarding` (localStorage-backed). This
 * component is purely the presenter — it dispatches markCompleted /
 * markSkipped at the right transitions and otherwise does nothing.
 *
 * Mounting: render once in the dashboard layout. It self-gates on
 * `shouldShow`, the current pathname blacklist, and SSR/CSR readiness,
 * so dropping it into the tree is safe regardless of route.
 */

"use client";

import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { CallBackProps, Step } from "react-joyride";

import { TourStep } from "./TourStep";
import { WelcomeModal } from "./WelcomeModal";
import { Button } from "@/components/ui/button";
import { useOnboarding } from "@/hooks/useOnboarding";
import type { Lang } from "@/lib/onboarding/tourSteps";
import {
  STEP_NAV_COPY,
  SUCCESS_COPY,
  TOUR_STEPS,
} from "@/lib/onboarding/tourSteps";

// Joyride is client-only and pulls in DOM-measurement utilities at
// import time. Dynamic import with `ssr: false` keeps it out of the
// server bundle and avoids "window is not defined" during the Next
// build step.
const Joyride = dynamic(
  () => import("react-joyride").then((m) => m.default),
  { ssr: false },
);

// Routes where the welcome modal/tour should never auto-display:
//   - `/onboarding` is the signup flow; the tour assumes the dashboard
//     chrome is mounted, which it isn't there.
//   - `/login` is a public unauthenticated screen.
// `/brokers` and `/strategies/new` are excluded only during the
// signup-incomplete state, which the layout already gates upstream.
const BLOCKED_PATHS = ["/onboarding", "/login"];

export interface OnboardingTourProps {
  userName: string;
}

type Phase = "welcome" | "tour" | "success" | "done";

export function OnboardingTour({ userName }: OnboardingTourProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { shouldShow, lang, markCompleted, markSkipped, setLang } =
    useOnboarding();

  const [phase, setPhase] = useState<Phase>("done");

  // Only PROMOTES the phase to "welcome" when the tour becomes
  // applicable (first mount or restart). Once the tour starts,
  // markCompleted() flips shouldShow → false and we deliberately
  // leave phase untouched so the "success" screen can render
  // through to its CTA dismiss. An explicit setPhase("done") in
  // each terminal handler handles teardown.
  useEffect(() => {
    if (!shouldShow) return;
    if (BLOCKED_PATHS.some((p) => pathname?.startsWith(p))) return;
    setPhase("welcome");
  }, [shouldShow, pathname]);

  const steps: Step[] = useMemo(
    () =>
      TOUR_STEPS.map((s) => ({
        target: s.target,
        title: s.title[lang],
        content: s.body[lang],
        placement: s.placement,
        disableBeacon: true,
        locale: {
          next: STEP_NAV_COPY.next[lang],
          skip: STEP_NAV_COPY.skip[lang],
          last: STEP_NAV_COPY.finish[lang],
          lang,
        } as unknown as Step["locale"],
      })),
    [lang],
  );

  const handleStart = useCallback(() => setPhase("tour"), []);

  const handleLater = useCallback(() => {
    markSkipped();
    setPhase("done");
  }, [markSkipped]);

  const handleJoyride = useCallback(
    (data: CallBackProps) => {
      if (data.status === "finished") {
        markCompleted();
        setPhase("success");
        return;
      }
      if (data.status === "skipped") {
        markCompleted();
        setPhase("done");
      }
    },
    [markCompleted],
  );

  const handleLang = useCallback(
    (next: Lang) => setLang(next),
    [setLang],
  );

  const goBuild = useCallback(() => {
    setPhase("done");
    router.push("/strategies/new");
  }, [router]);

  const goChart = useCallback(() => {
    setPhase("done");
    router.push("/chart");
  }, [router]);

  if (phase === "welcome") {
    return (
      <WelcomeModal
        userName={userName}
        lang={lang}
        onLangChange={handleLang}
        onStart={handleStart}
        onLater={handleLater}
      />
    );
  }

  if (phase === "tour") {
    return (
      <Joyride
        steps={steps}
        run
        continuous
        showSkipButton
        disableScrolling={false}
        scrollOffset={80}
        tooltipComponent={TourStep}
        callback={handleJoyride}
        styles={{
          options: {
            arrowColor: "rgba(23, 23, 23, 0.95)",
            overlayColor: "rgba(0, 0, 0, 0.55)",
            zIndex: 70,
          },
        }}
      />
    );
  }

  if (phase === "success") {
    return (
      <div
        role="dialog"
        aria-modal="true"
        data-testid="onboarding-success-modal"
        className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 supports-backdrop-filter:backdrop-blur-sm p-4"
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.96, y: 12 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ duration: 0.2 }}
          className="w-full max-w-md rounded-2xl border border-white/10 bg-neutral-900/85 supports-backdrop-filter:backdrop-blur-xl p-6 text-center shadow-2xl shadow-black/60"
        >
          <h2
            data-testid="onboarding-success-title"
            className="mb-3 text-xl font-bold text-neutral-100"
          >
            {SUCCESS_COPY.title[lang]}
          </h2>
          <p className="mb-6 text-sm text-neutral-300">
            {SUCCESS_COPY.body[lang]}
          </p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button
              type="button"
              onClick={goBuild}
              data-testid="onboarding-success-build"
              className="flex-1 bg-emerald-500 text-emerald-950 hover:bg-emerald-400"
            >
              {SUCCESS_COPY.buildCta[lang]}
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={goChart}
              data-testid="onboarding-success-chart"
              className="flex-1 text-neutral-300 hover:bg-white/5"
            >
              {SUCCESS_COPY.chartCta[lang]}
            </Button>
          </div>
        </motion.div>
      </div>
    );
  }

  return null;
}
