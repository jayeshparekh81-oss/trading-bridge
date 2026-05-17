/**
 * useOnboarding — localStorage-backed state for the first-login tour.
 *
 * Persisted keys:
 *   - tradetri_onboarding_completed (boolean) — finished OR skipped
 *   - tradetri_onboarding_skipped   (boolean) — user pressed "Later"
 *   - tradetri_lang                 ("en" | "hi") — UI language
 *
 * Show logic: tour visible only when NOT completed AND NOT skipped.
 *
 * A `tradetri:onboarding-restart` window event clears the flags and
 * re-arms the tour without a page reload — bound to the "Restart tour"
 * menu item in the top bar.
 */

"use client";

import { useCallback, useEffect, useState } from "react";

import type { Lang } from "@/lib/onboarding/tourSteps";

export const LS_KEY_COMPLETED = "tradetri_onboarding_completed";
export const LS_KEY_SKIPPED = "tradetri_onboarding_skipped";
export const LS_KEY_LANG = "tradetri_lang";
export const RESTART_EVENT = "tradetri:onboarding-restart";

const DEFAULT_LANG: Lang = "hi";

function safeRead(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeWrite(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* quota / private mode — silently drop */
  }
}

function safeRemove(key: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* idem */
  }
}

function parseLang(raw: string | null): Lang {
  return raw === "en" || raw === "hi" ? raw : DEFAULT_LANG;
}

export interface OnboardingState {
  /** Tour should display now. */
  shouldShow: boolean;
  /** Current UI language. */
  lang: Lang;
  /** Persist a finished tour. */
  markCompleted: () => void;
  /** Persist a "Later" decision (also hides the tour). */
  markSkipped: () => void;
  /** Swap language and persist. */
  setLang: (next: Lang) => void;
  /** Clear all flags and re-show the tour. */
  restart: () => void;
}

export function useOnboarding(): OnboardingState {
  const [shouldShow, setShouldShow] = useState(false);
  const [lang, setLangState] = useState<Lang>(DEFAULT_LANG);

  useEffect(() => {
    const completed = safeRead(LS_KEY_COMPLETED) === "true";
    const skipped = safeRead(LS_KEY_SKIPPED) === "true";
    setShouldShow(!completed && !skipped);
    setLangState(parseLang(safeRead(LS_KEY_LANG)));
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const handler = () => {
      safeRemove(LS_KEY_COMPLETED);
      safeRemove(LS_KEY_SKIPPED);
      setShouldShow(true);
    };
    window.addEventListener(RESTART_EVENT, handler);
    return () => window.removeEventListener(RESTART_EVENT, handler);
  }, []);

  const markCompleted = useCallback(() => {
    safeWrite(LS_KEY_COMPLETED, "true");
    setShouldShow(false);
  }, []);

  const markSkipped = useCallback(() => {
    safeWrite(LS_KEY_SKIPPED, "true");
    setShouldShow(false);
  }, []);

  const setLang = useCallback((next: Lang) => {
    safeWrite(LS_KEY_LANG, next);
    setLangState(next);
  }, []);

  const restart = useCallback(() => {
    safeRemove(LS_KEY_COMPLETED);
    safeRemove(LS_KEY_SKIPPED);
    setShouldShow(true);
  }, []);

  return { shouldShow, lang, markCompleted, markSkipped, setLang, restart };
}

/** Imperative restart for components outside the React tree (e.g. the
 *  top-bar menu item that doesn't share state with the layout-mounted
 *  tour). Dispatches the same custom event the hook listens for. */
export function triggerOnboardingRestart(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(RESTART_EVENT));
}
