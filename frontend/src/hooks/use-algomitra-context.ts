"use client";

/**
 * AlgoMitra context hooks — pathname-derived builder mode + a
 * localStorage-backed open/closed state for the Always-On panel.
 *
 * Phase 1 keeps the context surface minimal: the only piece of
 * runtime state the panel needs is which builder tier the user is
 * on, which we read from the pathname. Per-section reactivity is a
 * Phase 2 deliverable — it'll come via a shared React context the
 * builder pages can opt into without restructuring their reducers.
 *
 * `useAlgoMitraPanelState` writes to ``localStorage`` so the choice
 * persists across navigation. First-time users see the panel open
 * by default; closing once persists "closed" until they re-open.
 */

import { useCallback, useSyncExternalStore } from "react";
import { usePathname } from "next/navigation";
import { useAlgoMitraSection } from "@/components/algomitra/section-context";
import {
  DEFAULT_LANGUAGE,
  LANGUAGES,
  type BuilderMode,
  type BuilderSection,
  type Language,
} from "@/components/algomitra/coaching-tips-data";

// ── Pathname → mode + builder-route flag ──────────────────────────────

export interface AlgoMitraContext {
  /** True when the current route is one of the three builder pages. */
  isBuilderRoute: boolean;
  /** Which builder tier — only meaningful when ``isBuilderRoute``. */
  mode: BuilderMode | null;
  /** Active section the user is editing — provided by the
   *  per-builder :class:`AlgoMitraSectionProvider` (Phase 2).
   *  ``null`` when no provider is mounted (e.g. on non-Builder
   *  routes, or before Phase 2's wiring lands on a given page). */
  section: BuilderSection | null;
  /** Optional form-field focus hint. Phase 3-shaped — Phase 2 leaves
   *  it ``null`` because the providers don't track focus yet. */
  focusedField: string | null;
  /** Raw pathname for downstream consumers that want it. */
  pathname: string | null;
}

export function useAlgoMitraContext(): AlgoMitraContext {
  const pathname = usePathname();
  // Read the section provider before any early-return so the hook
  // order is stable across every render. ``useAlgoMitraSection``
  // returns ``null`` outside a provider, which is the safe default
  // the panel already handles.
  const sectionCtx = useAlgoMitraSection();
  const section = sectionCtx?.section ?? null;
  const focusedField = sectionCtx?.focusedField ?? null;

  if (!pathname) {
    return {
      isBuilderRoute: false,
      mode: null,
      section,
      focusedField,
      pathname: null,
    };
  }

  // Tolerate a leading "/" or query string suffix; the routes are
  // exact matches today but a future trailing-segment doesn't break.
  const head = pathname.split("?")[0] ?? pathname;

  if (head.startsWith("/strategies/new/beginner")) {
    return {
      isBuilderRoute: true,
      mode: "beginner",
      section,
      focusedField,
      pathname,
    };
  }
  if (head.startsWith("/strategies/new/intermediate")) {
    return {
      isBuilderRoute: true,
      mode: "intermediate",
      section,
      focusedField,
      pathname,
    };
  }
  if (head.startsWith("/strategies/new/expert")) {
    return {
      isBuilderRoute: true,
      mode: "expert",
      section,
      focusedField,
      pathname,
    };
  }
  return {
    isBuilderRoute: false,
    mode: null,
    section,
    focusedField,
    pathname,
  };
}

// ── localStorage panel open/closed state ──────────────────────────────

export type PanelState = "open" | "closed";

const STORAGE_KEY = "algomitra_panel_state";

function readStoredState(): PanelState {
  if (typeof window === "undefined") return "open";
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw === "closed" ? "closed" : "open";
  } catch {
    // ``localStorage`` access can throw in strict-storage / private
    // browsing modes — fall back to the safe default ("open" so the
    // panel surfaces for the user, who can then close it).
    return "open";
  }
}

// ── Subscription store — sidesteps the React 19 "setState in
// effect" rule by using ``useSyncExternalStore``. The store is a
// tiny set of callbacks; ``open``/``close`` write to ``localStorage``
// and notify, which causes ``useSyncExternalStore`` to re-render
// every component subscribed to the snapshot.

const _subscribers = new Set<() => void>();

function _subscribe(cb: () => void): () => void {
  _subscribers.add(cb);
  // Cross-tab updates: when another tab writes the same key, fire
  // the local subscribers so this tab's panel reflects it instantly.
  const onStorage = (e: StorageEvent) => {
    if (e.key === STORAGE_KEY) cb();
  };
  if (typeof window !== "undefined") {
    window.addEventListener("storage", onStorage);
  }
  return () => {
    _subscribers.delete(cb);
    if (typeof window !== "undefined") {
      window.removeEventListener("storage", onStorage);
    }
  };
}

function _notify(): void {
  for (const cb of _subscribers) cb();
}

function _serverSnapshot(): PanelState {
  // Match the safe default — the SSR HTML carries ``open``, and the
  // client's first paint will reconcile to the persisted value via
  // ``useSyncExternalStore``'s built-in mismatch handling.
  return "open";
}

function writeStoredState(state: PanelState): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, state);
  } catch {
    // Swallow — persistence failures don't block the toggle from
    // working in-memory.
  }
}

export interface UseAlgoMitraPanelState {
  isOpen: boolean;
  open: () => void;
  close: () => void;
  toggle: () => void;
}

export function useAlgoMitraPanelState(): UseAlgoMitraPanelState {
  const state = useSyncExternalStore(
    _subscribe,
    readStoredState,
    _serverSnapshot,
  );

  const open = useCallback(() => {
    writeStoredState("open");
    _notify();
  }, []);
  const close = useCallback(() => {
    writeStoredState("closed");
    _notify();
  }, []);
  const toggle = useCallback(() => {
    const next: PanelState = readStoredState() === "open" ? "closed" : "open";
    writeStoredState(next);
    _notify();
  }, []);

  return {
    isOpen: state === "open",
    open,
    close,
    toggle,
  };
}


// ── localStorage language preference ─────────────────────────────────


const LANG_STORAGE_KEY = "algomitra_language";
const _LANGUAGE_SET: ReadonlySet<Language> = new Set(LANGUAGES);

function _isLanguage(value: string | null): value is Language {
  return value !== null && _LANGUAGE_SET.has(value as Language);
}

function readStoredLanguage(): Language {
  if (typeof window === "undefined") return DEFAULT_LANGUAGE;
  try {
    const raw = window.localStorage.getItem(LANG_STORAGE_KEY);
    return _isLanguage(raw) ? raw : DEFAULT_LANGUAGE;
  } catch {
    return DEFAULT_LANGUAGE;
  }
}

function writeStoredLanguage(lang: Language): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(LANG_STORAGE_KEY, lang);
  } catch {
    // Persistence-failure tolerant — falls back to in-memory state.
  }
}

const _langSubscribers = new Set<() => void>();

function _langSubscribe(cb: () => void): () => void {
  _langSubscribers.add(cb);
  // Cross-tab sync: a switch in another tab fires the storage event;
  // every subscribed panel re-renders with the new language.
  const onStorage = (e: StorageEvent) => {
    if (e.key === LANG_STORAGE_KEY) cb();
  };
  if (typeof window !== "undefined") {
    window.addEventListener("storage", onStorage);
  }
  return () => {
    _langSubscribers.delete(cb);
    if (typeof window !== "undefined") {
      window.removeEventListener("storage", onStorage);
    }
  };
}

function _langNotify(): void {
  for (const cb of _langSubscribers) cb();
}

function _langServerSnapshot(): Language {
  // Match the SSR default — first client paint reconciles to the
  // persisted value via ``useSyncExternalStore``.
  return DEFAULT_LANGUAGE;
}

export interface UseAlgoMitraLanguage {
  language: Language;
  setLanguage: (lang: Language) => void;
}

export function useAlgoMitraLanguage(): UseAlgoMitraLanguage {
  const language = useSyncExternalStore(
    _langSubscribe,
    readStoredLanguage,
    _langServerSnapshot,
  );
  const setLanguage = useCallback((next: Language) => {
    writeStoredLanguage(next);
    _langNotify();
  }, []);
  return { language, setLanguage };
}
