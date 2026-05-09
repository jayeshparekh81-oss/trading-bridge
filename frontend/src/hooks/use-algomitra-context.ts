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
import type { BuilderMode } from "@/components/algomitra/coaching-tips-data";

// ── Pathname → mode + builder-route flag ──────────────────────────────

export interface AlgoMitraContext {
  /** True when the current route is one of the three builder pages. */
  isBuilderRoute: boolean;
  /** Which builder tier — only meaningful when ``isBuilderRoute``. */
  mode: BuilderMode | null;
  /** Raw pathname for downstream consumers that want it. */
  pathname: string | null;
}

export function useAlgoMitraContext(): AlgoMitraContext {
  const pathname = usePathname();
  if (!pathname) {
    return { isBuilderRoute: false, mode: null, pathname: null };
  }

  // Tolerate a leading "/" or query string suffix; the routes are
  // exact matches today but a future trailing-segment doesn't break.
  const head = pathname.split("?")[0] ?? pathname;

  if (head.startsWith("/strategies/new/beginner")) {
    return { isBuilderRoute: true, mode: "beginner", pathname };
  }
  if (head.startsWith("/strategies/new/intermediate")) {
    return { isBuilderRoute: true, mode: "intermediate", pathname };
  }
  if (head.startsWith("/strategies/new/expert")) {
    return { isBuilderRoute: true, mode: "expert", pathname };
  }
  return { isBuilderRoute: false, mode: null, pathname };
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
