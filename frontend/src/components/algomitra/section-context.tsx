"use client";

/**
 * AlgoMitra section context — Phase 2 propagation primitive.
 *
 * Each Builder page wraps its content with
 * :class:`AlgoMitraSectionProvider` and passes the section the user
 * is currently editing. The Always-On panel reads the value via
 * :func:`useAlgoMitraSection` and auto-expands the matching tip
 * accordion.
 *
 * The context is intentionally a plain React Context (not a
 * subscription store) — section changes are page-driven and
 * synchronous, so the simpler primitive works and re-renders only
 * the panel when the value changes.
 *
 * When no provider wraps the tree (e.g. on non-Builder routes the
 * panel never renders anyway), the consumer returns ``null`` and the
 * panel falls back to its Phase 1 accordion behaviour.
 */

import { createContext, useContext, useMemo, type ReactNode } from "react";
import type { BuilderSection } from "./coaching-tips-data";

interface AlgoMitraSectionValue {
  /** Active section the panel should auto-expand. ``null`` when the
   *  active section is unknown — the panel falls back to its first
   *  accordion item. */
  section: BuilderSection | null;
  /** Optional active form-field hint. Phase 2 doesn't render this
   *  yet but the field is reserved so Phase 3 can light up the
   *  matching tip line without the providers needing to change. */
  focusedField: string | null;
}

const AlgoMitraSectionContext = createContext<AlgoMitraSectionValue | null>(
  null,
);

interface AlgoMitraSectionProviderProps {
  section: BuilderSection | null;
  focusedField?: string | null;
  children: ReactNode;
}

export function AlgoMitraSectionProvider({
  section,
  focusedField = null,
  children,
}: AlgoMitraSectionProviderProps) {
  // Memoise the value object so unchanged props don't churn consumers
  // — most renders of the Builder pages don't change ``section`` and
  // we want to avoid forcing the panel to re-render on every reducer
  // tick.
  const value = useMemo<AlgoMitraSectionValue>(
    () => ({ section, focusedField }),
    [section, focusedField],
  );
  return (
    <AlgoMitraSectionContext.Provider value={value}>
      {children}
    </AlgoMitraSectionContext.Provider>
  );
}

/** Hook for consumers (the Always-On panel, future tip surfaces).
 *  Returns ``null`` outside any provider — caller must handle that
 *  case to support routes where the provider isn't wired. */
export function useAlgoMitraSection(): AlgoMitraSectionValue | null {
  return useContext(AlgoMitraSectionContext);
}
