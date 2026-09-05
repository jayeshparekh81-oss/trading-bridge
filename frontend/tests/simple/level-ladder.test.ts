/**
 * Simple mode rules — guidance only, no gate (founder 2026-09-05 evening):
 * who starts in Simple vs Pro, how the journey step is computed from facts,
 * and that the module exposes NO route gate at all.
 */
import { describe, it, expect } from "vitest";
import * as level from "@/lib/simple/level";
import {
  EMPTY_FACTS,
  LADDER_LAUNCH_AT,
  LEARN_TILES,
  MAIN_TILES,
  TILE_ROUTE,
  applyFacts,
  computeEarnedLevel,
  defaultLevelFor,
  effectiveLevel,
  initialState,
  progressFor,
  remainingFor,
} from "@/lib/simple/level";

describe("journey step from facts (guidance, not a gate)", () => {
  it("step 2 = broker + first subscription + first signal seen; 3 = + template + test; 4 = + own strategy", () => {
    expect(computeEarnedLevel(EMPTY_FACTS)).toBe(1);
    const l2 = { ...EMPTY_FACTS, brokerConnected: true, hasSubscription: true, firstSignalSeen: true };
    expect(computeEarnedLevel({ ...EMPTY_FACTS, brokerConnected: true, hasSubscription: true })).toBe(1);
    expect(computeEarnedLevel(l2)).toBe(2);
    expect(computeEarnedLevel({ ...l2, templateCloned: true, backtestRun: true })).toBe(3);
    expect(computeEarnedLevel({ ...l2, templateCloned: true, backtestRun: true, strategyBuilt: true })).toBe(4);
  });
  it("facts are never un-learned; an empty observation changes nothing", () => {
    const now = "2026-09-05T10:00:00Z";
    let s = initialState({ created_at: "2026-09-05T09:00:00Z" });
    s = applyFacts(s, { brokerConnected: true }, now);
    expect(s.facts.brokerConnected).toBe(now);
    const same = applyFacts(s, {}, "2026-09-06T00:00:00Z");
    expect(same).toBe(s);
    const again = applyFacts(s, { brokerConnected: false }, "2026-09-06T00:00:00Z");
    expect(again.facts.brokerConnected).toBe(now);
  });
  it("the journey line names the very next thing to do", () => {
    expect(progressFor(1, EMPTY_FACTS)).toEqual({ done: 1, total: 4, next: "broker" });
    expect(progressFor(1, { ...EMPTY_FACTS, brokerConnected: true })).toEqual({ done: 1, total: 4, next: "subscribe" });
    expect(remainingFor(2, { ...EMPTY_FACTS, brokerConnected: true, hasSubscription: true })).toEqual(["signal"]);
    expect(progressFor(3, EMPTY_FACTS)).toEqual({ done: 3, total: 4, next: "build" });
    expect(progressFor(4, EMPTY_FACTS)).toEqual({ done: 4, total: 4, next: null });
  });
});

describe("mode", () => {
  it("Pro is a choice, never earned automatically; Simple shows the journey step capped at 3", () => {
    const all = { brokerConnected: true, hasSubscription: true, firstSignalSeen: true, templateCloned: true, backtestRun: true, strategyBuilt: true };
    expect(effectiveLevel(1, "pro", EMPTY_FACTS)).toBe(4);
    expect(effectiveLevel(1, "auto", EMPTY_FACTS)).toBe(1);
    expect(effectiveLevel(1, "auto", all)).toBe(3); // building a strategy does NOT flip the chrome to Pro
    expect(effectiveLevel(4, "auto", EMPTY_FACTS)).toBe(4); // an existing account's default is Pro
    expect(effectiveLevel(4, "simple", EMPTY_FACTS)).toBe(1); // a Pro account in Simple is levelled by its facts
    expect(effectiveLevel(4, "simple", all)).toBe(3);
  });
});

describe("who starts where", () => {
  it("a NEW signup starts in Simple; an EXISTING account and founder/admin accounts start in Pro", () => {
    expect(defaultLevelFor({ created_at: "2026-09-06T08:00:00Z" })).toBe(1);
    expect(defaultLevelFor({ created_at: "2026-08-01T08:00:00Z" })).toBe(4);
    expect(defaultLevelFor({ is_admin: true, created_at: "2026-09-06T08:00:00Z" })).toBe(4);
    expect(defaultLevelFor({ role: "super_admin", created_at: "2026-09-06T08:00:00Z" })).toBe(4);
    expect(Date.parse(LADDER_LAUNCH_AT)).toBeGreaterThan(Date.parse("2026-09-04T00:00:00Z"));
  });
  it("a Pro-default account skips the Simple onboarding and the first-Pro nudge; a new signup owes both", () => {
    const pro = initialState({ created_at: "2026-01-01T00:00:00Z" });
    expect(pro).toMatchObject({ earned: 4, choice: "auto", simpleOnboardingDone: true, proNudgeSeen: true, tipsShown: [] });
    const fresh = initialState({ created_at: "2026-09-06T00:00:00Z" });
    expect(fresh).toMatchObject({ earned: 1, choice: "auto", simpleOnboardingDone: false, proNudgeSeen: false });
  });
});

describe("NO LOCKS", () => {
  it("the module exposes no route gate and no locked-tile helpers", () => {
    const names = Object.keys(level);
    for (const banned of ["canOpen", "minLevelForPath", "lockedTilesFor", "tilesForLevel", "TILE_LEVEL", "pendingAnnouncement", "markAnnounced"]) {
      expect(names, banned).not.toContain(banned);
    }
  });
  it("the four main tiles and the three 'Aur seekhein' tiles are fixed and all have a destination", () => {
    expect(MAIN_TILES).toEqual(["strategy", "broker", "signals", "help"]);
    expect(LEARN_TILES).toEqual(["templates", "build", "pro"]);
    for (const id of MAIN_TILES) expect(TILE_ROUTE[id]).toMatch(/^\//);
    expect(TILE_ROUTE.templates).toBe("/strategies/templates");
    expect(TILE_ROUTE.build).toBe("/strategies/new/beginner");
  });
});
