"use client";

/**
 * The level ladder as React state, persisted in `users.notification_prefs`
 * under `_ui_ladder` through the EXISTING `PUT /api/users/me` (no backend
 * change, no migration — see lib/simple/level.ts).
 *
 * Read-merge-write: every save spreads the current `notification_prefs` so a
 * ladder write never clobbers `email`/`telegram` or the onboarding's reserved
 * keys, then `refreshUser()` re-syncs the auth context (the same discipline
 * that fixed the first-login blink).
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  PREF_KEY,
  applyFacts,
  effectiveLevel,
  initialState,
  markAnnounced,
  pendingAnnouncement,
  type LevelState,
  type ModeChoice,
  type UiLevel,
  type UnlockFacts,
} from "@/lib/simple/level";

export interface LadderValue {
  /** Null until the auth user has loaded. */
  ready: boolean;
  state: LevelState | null;
  /** What the customer sees right now (choice applied). */
  level: UiLevel;
  earned: UiLevel;
  choice: ModeChoice;
  /** Next unlock still to be announced. */
  pendingUnlock: UiLevel | null;
  observe: (facts: Partial<UnlockFacts>) => void;
  announce: (level: UiLevel) => void;
  setChoice: (choice: ModeChoice) => Promise<void>;
  markProNudgeSeen: () => void;
  markSimpleOnboardingDone: () => void;
}

/** DOM event name action sites use to report a ladder fact. */
export const LADDER_EVENT = "tradetri:ladder";

const LadderContext = createContext<LadderValue | null>(null);

function readState(prefs: Record<string, unknown> | null | undefined): LevelState | null {
  const raw = prefs?.[PREF_KEY];
  if (!raw || typeof raw !== "object") return null;
  const s = raw as Partial<LevelState>;
  if (typeof s.earned !== "number") return null;
  return {
    earned: Math.min(4, Math.max(1, Math.round(s.earned))) as UiLevel,
    choice: s.choice === "pro" || s.choice === "simple" ? s.choice : "auto",
    facts: s.facts && typeof s.facts === "object" ? s.facts : {},
    unlockedAt: s.unlockedAt && typeof s.unlockedAt === "object" ? s.unlockedAt : {},
    announced: Array.isArray(s.announced) ? (s.announced.filter((n) => [2, 3, 4].includes(n as number)) as UiLevel[]) : [],
    proNudgeSeen: !!s.proNudgeSeen,
    simpleOnboardingDone: !!s.simpleOnboardingDone,
  };
}

interface Slot {
  /** The auth user this ladder state belongs to (null = logged out). */
  key: string | null;
  state: LevelState | null;
}

function hydrate(user: NonNullable<ReturnType<typeof useAuth>["user"]>): LevelState {
  return (
    readState(user.notification_prefs as Record<string, unknown>) ??
    initialState(user, new Date().toISOString())
  );
}

export function LadderProvider({ children }: { children: ReactNode }) {
  const { user, refreshUser } = useAuth();
  const [slot, setSlot] = useState<Slot>({ key: null, state: null });
  const saved = useRef<string>("");
  const saving = useRef<Promise<void> | null>(null);

  // Hydrate when the auth user changes (login / logout / another account).
  // Adjusting state during render is React's sanctioned pattern for
  // "derive from a prop that just changed" — no effect, no extra commit.
  const userKey = user?.id ?? null;
  if (slot.key !== userKey) {
    setSlot({ key: userKey, state: user ? hydrate(user) : null });
  }
  const state = slot.key === userKey ? slot.state : null;

  const update = useCallback((fn: (s: LevelState) => LevelState) => {
    setSlot((cur) => {
      if (!cur.state) return cur;
      const next = fn(cur.state);
      return next === cur.state ? cur : { ...cur, state: next };
    });
  }, []);

  // Persist whenever the state differs from what the server has.
  useEffect(() => {
    if (!user || !state) return;
    const json = JSON.stringify(state);
    if (json === saved.current) return;
    const server = readState(user.notification_prefs as Record<string, unknown>);
    if (server && JSON.stringify(server) === json) {
      saved.current = json; // already on the server (fresh login) — nothing to write
      return;
    }
    saved.current = json;
    const prefs = { ...((user.notification_prefs as Record<string, unknown>) ?? {}), [PREF_KEY]: state };
    const run = async () => {
      try {
        await api.put("/users/me", { notification_prefs: prefs });
        await refreshUser();
      } catch {
        // Best effort: the in-memory ladder still drives the UI this session;
        // the next change retries. Never block the customer on a pref write.
        saved.current = "";
      }
    };
    saving.current = (saving.current ?? Promise.resolve()).then(run);
  }, [state, user, refreshUser]);

  const observe = useCallback(
    (facts: Partial<UnlockFacts>) => {
      update((s) => {
        const { state: next } = applyFacts(s, facts, new Date().toISOString());
        return JSON.stringify(next) === JSON.stringify(s) ? s : next;
      });
    },
    [update],
  );

  // Action sites (subscribe, connect broker, clone a template, build a
  // strategy) announce facts with a DOM event so they need no ladder import:
  //   window.dispatchEvent(new CustomEvent("tradetri:ladder", { detail: { hasSubscription: true } }))
  useEffect(() => {
    const onFact = (e: Event) => {
      const detail = (e as CustomEvent<Partial<UnlockFacts>>).detail;
      if (detail && typeof detail === "object") observe(detail);
    };
    window.addEventListener(LADDER_EVENT, onFact);
    return () => window.removeEventListener(LADDER_EVENT, onFact);
  }, [observe]);

  const announce = useCallback((level: UiLevel) => update((s) => markAnnounced(s, level)), [update]);

  const setChoice = useCallback(
    async (choice: ModeChoice) => update((s) => (s.choice === choice ? s : { ...s, choice })),
    [update],
  );

  const markProNudgeSeen = useCallback(() => update((s) => (s.proNudgeSeen ? s : { ...s, proNudgeSeen: true })), [update]);

  const markSimpleOnboardingDone = useCallback(
    () => update((s) => (s.simpleOnboardingDone ? s : { ...s, simpleOnboardingDone: true })),
    [update],
  );

  const value = useMemo<LadderValue>(() => {
    const earned = state?.earned ?? 4;
    const choice = state?.choice ?? "auto";
    return {
      ready: !!state,
      state,
      earned,
      choice,
      level: state ? effectiveLevel(earned, choice) : 4,
      pendingUnlock: state ? pendingAnnouncement(state) : null,
      observe,
      announce,
      setChoice,
      markProNudgeSeen,
      markSimpleOnboardingDone,
    };
  }, [state, observe, announce, setChoice, markProNudgeSeen, markSimpleOnboardingDone]);

  return <LadderContext.Provider value={value}>{children}</LadderContext.Provider>;
}

export function useLadder(): LadderValue {
  const ctx = useContext(LadderContext);
  if (!ctx) throw new Error("useLadder must be used within LadderProvider");
  return ctx;
}

/** Safe variant for components that may render outside the provider (tests, public pages). */
export function useLadderOptional(): LadderValue | null {
  return useContext(LadderContext);
}
