/** The journey line and AlgoMitra's "Aur seekhein" one-liners, in four languages. */
import { describe, it, expect } from "vitest";
import { EMPTY_FACTS } from "@/lib/simple/level";
import { buildProgress, tipFor } from "@/lib/simple/journey";

describe("journey line", () => {
  it("counts steps and names the next one, per language", () => {
    expect(buildProgress("hinglish", 1, EMPTY_FACTS)).toEqual({ done: 1, total: 4, next: "Broker jodo" });
    expect(buildProgress("hi", 1, { ...EMPTY_FACTS, brokerConnected: true })).toEqual({ done: 1, total: 4, next: "स्ट्रैटेजी चुनो" });
    expect(buildProgress("gu", 2, EMPTY_FACTS)).toEqual({ done: 2, total: 4, next: "એક ટેમ્પલેટ અજમાવો" });
    expect(buildProgress("en", 4, EMPTY_FACTS)).toEqual({ done: 4, total: 4, next: null });
  });
});

describe("Aur seekhein tips", () => {
  it("one line per tile, prefixed by AlgoMitra, in every language, no lock words", () => {
    for (const lang of ["hinglish", "hi", "gu", "en"] as const) {
      for (const id of ["templates", "build", "pro"] as const) {
        const tip = tipFor(lang, id);
        expect(tip.startsWith("AlgoMitra: ")).toBe(true);
        expect(tip.length).toBeGreaterThan(20);
        expect(tip).not.toMatch(/🔒|khulega|खुलेगा|ખુલશે|unlock/i);
      }
    }
    expect(tipFor("hinglish", "templates")).toContain("taiyar strategies");
    expect(tipFor("hinglish", "pro")).toContain("poora menu");
  });
});
