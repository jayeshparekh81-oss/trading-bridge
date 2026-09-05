/**
 * The level ladder — pure rules (C8, C9, C11): unlock rules, the default for
 * existing vs new vs founder accounts, the route gate in both directions.
 */
import { describe, it, expect } from "vitest";
import {
  EMPTY_FACTS,
  LADDER_LAUNCH_AT,
  applyFacts,
  canOpen,
  computeEarnedLevel,
  defaultLevelFor,
  effectiveLevel,
  initialState,
  markAnnounced,
  minLevelForPath,
  pendingAnnouncement,
  tilesForLevel,
} from "@/lib/simple/level";

describe("unlock rules", () => {
  it("Level 2 needs broker + first subscription + first signal seen — all three", () => {
    expect(computeEarnedLevel({ ...EMPTY_FACTS, brokerConnected: true, hasSubscription: true })).toBe(1);
    expect(computeEarnedLevel({ ...EMPTY_FACTS, brokerConnected: true, firstSignalSeen: true })).toBe(1);
    expect(computeEarnedLevel({ ...EMPTY_FACTS, brokerConnected: true, hasSubscription: true, firstSignalSeen: true })).toBe(2);
  });
  it("Level 3 needs a template cloned + a backtest run on top of Level 2", () => {
    const l2 = { ...EMPTY_FACTS, brokerConnected: true, hasSubscription: true, firstSignalSeen: true };
    expect(computeEarnedLevel({ ...l2, templateCloned: true })).toBe(2);
    expect(computeEarnedLevel({ ...l2, templateCloned: true, backtestRun: true })).toBe(3);
    // cloning + backtesting WITHOUT Level 2 stays Level 1 — the ladder is ordered
    expect(computeEarnedLevel({ ...EMPTY_FACTS, templateCloned: true, backtestRun: true, strategyBuilt: true })).toBe(1);
  });
  it("Level 4 needs a strategy built on top of Level 3", () => {
    const l3 = { ...EMPTY_FACTS, brokerConnected: true, hasSubscription: true, firstSignalSeen: true, templateCloned: true, backtestRun: true };
    expect(computeEarnedLevel(l3)).toBe(3);
    expect(computeEarnedLevel({ ...l3, strategyBuilt: true })).toBe(4);
  });
  it("earned never goes down; each unlock is recorded once and announced once", () => {
    const now = "2026-09-05T10:00:00Z";
    let s = initialState({ created_at: "2026-09-05T09:00:00Z" }, now);
    expect(s.earned).toBe(1);
    let r = applyFacts(s, { brokerConnected: true, hasSubscription: true, firstSignalSeen: true }, now);
    expect(r.newlyUnlocked).toEqual([2]);
    s = r.state;
    expect(pendingAnnouncement(s)).toBe(2);
    s = markAnnounced(s, 2);
    expect(pendingAnnouncement(s)).toBeNull();
    // facts cannot be un-learned: an empty observation changes nothing
    r = applyFacts(s, {}, now);
    expect(r.state.earned).toBe(2);
    expect(r.newlyUnlocked).toEqual([]);
    // jumping straight to 4 records 3 and 4 in order
    r = applyFacts(s, { templateCloned: true, backtestRun: true, strategyBuilt: true }, now);
    expect(r.newlyUnlocked).toEqual([3, 4]);
    expect(r.state.unlockedAt[3]).toBe(now);
  });
});

describe("mode choice", () => {
  it("Pro is one toggle away; Simple caps at 3 and keeps the earned level", () => {
    expect(effectiveLevel(1, "pro")).toBe(4);
    expect(effectiveLevel(4, "simple")).toBe(3);
    expect(effectiveLevel(2, "simple")).toBe(2);
    expect(effectiveLevel(3, "auto")).toBe(3);
  });
});

describe("C11 — who starts where", () => {
  it("a NEW signup starts at Level 1", () => {
    expect(defaultLevelFor({ created_at: "2026-09-06T08:00:00Z" })).toBe(1);
  });
  it("an EXISTING account (created before the ladder launched) is Pro", () => {
    expect(defaultLevelFor({ created_at: "2026-08-01T08:00:00Z" })).toBe(4);
    expect(Date.parse(LADDER_LAUNCH_AT)).toBeGreaterThan(Date.parse("2026-09-04T00:00:00Z"));
  });
  it("founder / admin accounts stay Pro regardless of age", () => {
    expect(defaultLevelFor({ is_admin: true, created_at: "2026-09-06T08:00:00Z" })).toBe(4);
    expect(defaultLevelFor({ role: "super_admin", created_at: "2026-09-06T08:00:00Z" })).toBe(4);
  });
  it("a Pro-default account is never 'announced' into Pro and skips Simple onboarding", () => {
    const s = initialState({ created_at: "2026-01-01T00:00:00Z" }, "2026-09-05T00:00:00Z");
    expect(s.earned).toBe(4);
    expect(pendingAnnouncement(s)).toBeNull();
    expect(s.simpleOnboardingDone).toBe(true);
    expect(s.proNudgeSeen).toBe(true);
  });
  it("a new signup owes the Simple onboarding and, later, the first-Pro nudge", () => {
    const s = initialState({ created_at: "2026-09-06T00:00:00Z" }, "2026-09-06T00:00:00Z");
    expect(s.simpleOnboardingDone).toBe(false);
    expect(s.proNudgeSeen).toBe(false);
  });
});

describe("C9 — the route gate, both directions", () => {
  const L1 = ["/", "/marketplace", "/marketplace/abc-123", "/marketplace/me", "/brokers", "/signals", "/help", "/support", "/settings", "/showcase", "/pricing"];
  const L2 = ["/strategies/templates", "/strategies/templates/ema-cross"];
  const L3 = ["/strategies/new", "/strategies/new/beginner", "/strategies", "/strategies/abc", "/indicators"];
  const L4 = ["/analytics", "/chart", "/webhooks", "/compliance", "/compliance/legal", "/strategies/indicators", "/positions", "/trades", "/kill-switch", "/admin", "/indicators/requests", "/alerts"];
  it("a Level-1 customer opens only Level-1 routes", () => {
    for (const p of L1) expect(canOpen(1, p), p).toBe(true);
    for (const p of [...L2, ...L3, ...L4]) expect(canOpen(1, p), p).toBe(false);
  });
  it("Level 2 adds templates, Level 3 adds the builder + Learn Indicators, Pro opens everything", () => {
    for (const p of L2) expect(canOpen(2, p), p).toBe(true);
    for (const p of [...L3, ...L4]) expect(canOpen(2, p), p).toBe(false);
    for (const p of [...L1, ...L2, ...L3]) expect(canOpen(3, p), p).toBe(true);
    for (const p of L4) expect(canOpen(3, p), p).toBe(false);
    for (const p of [...L1, ...L2, ...L3, ...L4]) expect(canOpen(4, p), p).toBe(true);
  });
  it("Analytics, Chart, Webhooks, Compliance, Indicator Library are Level-4 surfaces", () => {
    for (const p of ["/analytics", "/chart", "/webhooks", "/compliance", "/strategies/indicators"]) expect(minLevelForPath(p)).toBe(4);
  });
  it("query strings and trailing slashes do not change the verdict", () => {
    expect(minLevelForPath("/analytics?range=1m")).toBe(4);
    expect(minLevelForPath("/marketplace/")).toBe(1);
  });
  it("tiles grow with the level and never lose the four basics", () => {
    expect(tilesForLevel(1)).toEqual(["strategy", "broker", "signals", "help"]);
    expect(tilesForLevel(2)).toEqual(["strategy", "broker", "signals", "help", "templates"]);
    expect(tilesForLevel(3)).toEqual(["strategy", "broker", "signals", "help", "templates", "build", "learn"]);
  });
});
