"use client";

/**
 * useGuidedPathLive — THE switch-on interlock as a hook (founder, 26 Sep 2026).
 *
 *   "off"       the frontend flag NEXT_PUBLIC_CUSTOMER_GUIDED_PATH is off (no network call)
 *   "checking"  the flag is on and the backend's readiness has not answered yet
 *   "ready"     the flag is on AND the backend said, live, that its guided API is ready
 *   "not-ready" the flag is on but the backend is off / erroring / slow / old / not ready
 *
 * Only "ready" may show /start or redirect to it. Every other value keeps the current
 * onboarding — so the two flags can never be on "separately" in a way a customer can see.
 */

import { useEffect, useState } from "react";

import { guidedPathEnabled, guidedPathLive, type GuidedLive } from "@/lib/guided-path";

export function useGuidedPathLive(): GuidedLive {
  const enabled = guidedPathEnabled();
  const [answer, setAnswer] = useState<"checking" | "ready" | "not-ready">("checking");

  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    guidedPathLive().then(
      (ok) => { if (alive) setAnswer(ok ? "ready" : "not-ready"); },
      () => { if (alive) setAnswer("not-ready"); },
    );
    return () => { alive = false; };
  }, [enabled]);

  return enabled ? answer : "off";
}
