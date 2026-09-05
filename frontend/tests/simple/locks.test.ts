/** Visible-but-locked tiles: the copy says exactly what is still missing (A, E). */
import { describe, it, expect } from "vitest";
import { EMPTY_FACTS, effectiveLevel, factFlags, lockedTilesFor, progressFor, remainingFor } from "@/lib/simple/level";
import { buildLocked, buildProgress, lockedHint } from "@/lib/simple/locks";

describe("locked tiles", () => {
  it("Level 1 shows templates, build and learn locked, plus the Pro tile", () => {
    expect(lockedTilesFor(1)).toEqual(["templates", "build", "learn"]);
    expect(lockedTilesFor(2)).toEqual(["build", "learn"]);
    expect(lockedTilesFor(3)).toEqual([]);
    const locked = buildLocked("hinglish", 1, EMPTY_FACTS);
    expect(locked.map((l) => l.id)).toEqual(["templates", "build", "learn", "pro"]);
    expect(locked[0]).toMatchObject({ title: "Templates dekho", hint: "Broker jodo + Strategy chuno + pehla signal dekho, phir yeh khulega" });
    expect(locked[1]).toMatchObject({ title: "Apni strategy banao", hint: "Ek template try karo + ek baar test chalao, phir yeh khulega" });
    expect(locked[3]).toMatchObject({ title: "Pro mode (poora menu)", hint: "Ya abhi kholo →" });
  });
  it("the hint names ONLY what is still missing — real state, not a fresh-account zero", () => {
    const f = { ...EMPTY_FACTS, brokerConnected: true, hasSubscription: true };
    expect(remainingFor(2, f)).toEqual(["signal"]);
    expect(lockedHint("hinglish", 2, f)).toBe("pehla signal dekho, phir yeh khulega");
    expect(lockedHint("hi", 2, f)).toBe("पहला सिग्नल देखो, फिर यह खुलेगा");
    expect(lockedHint("gu", 2, { ...EMPTY_FACTS, brokerConnected: true })).toBe("સ્ટ્રેટેજી પસંદ કરો + પહેલો સિગ્નલ જુઓ, પછી આ ખુલશે");
    expect(lockedHint("en", 3, { ...EMPTY_FACTS, templateCloned: true })).toBe("run one test, then this opens");
  });
  it("a Pro account switching to Simple is levelled by its facts, capped at 3", () => {
    expect(effectiveLevel(4, "simple", EMPTY_FACTS)).toBe(1);
    expect(effectiveLevel(4, "simple", { ...EMPTY_FACTS, brokerConnected: true, hasSubscription: true, firstSignalSeen: true })).toBe(2);
    const all = { brokerConnected: true, hasSubscription: true, firstSignalSeen: true, templateCloned: true, backtestRun: true, strategyBuilt: true };
    expect(effectiveLevel(4, "simple", all)).toBe(3);
    expect(effectiveLevel(4, "pro", EMPTY_FACTS)).toBe(4);
    // stored facts are timestamps; flags derive from presence
    expect(factFlags({ brokerConnected: "2026-09-05T00:00:00Z" })).toMatchObject({ brokerConnected: true, hasSubscription: false });
  });
  it("the journey line counts levels and names the very next step", () => {
    expect(progressFor(1, EMPTY_FACTS)).toEqual({ done: 1, total: 4, next: "broker" });
    expect(progressFor(1, { ...EMPTY_FACTS, brokerConnected: true })).toEqual({ done: 1, total: 4, next: "subscribe" });
    expect(progressFor(2, EMPTY_FACTS)).toEqual({ done: 2, total: 4, next: "template" });
    expect(progressFor(3, EMPTY_FACTS)).toEqual({ done: 3, total: 4, next: "build" });
    expect(progressFor(4, EMPTY_FACTS)).toEqual({ done: 4, total: 4, next: null });
    expect(buildProgress("hinglish", 1, EMPTY_FACTS)).toEqual({ done: 1, total: 4, next: "Broker jodo" });
  });
});
