/**
 * Two honesty rules, both about not letting the UI claim what the backend
 * cannot guarantee.
 *
 * 1. A DIRECTION choice may not carry the published performance record. The
 *    showcase artifact does publish long-only and short-only figures — and they
 *    look BETTER than the both-sides headline (long: 805 trades, 81.7% win,
 *    PF 5.68 vs 1,149 / 76.8% / 5.01) — but the artifact disowns them itself:
 *    "a SLICE of the full long+short system ... NOT an independently-validated
 *    standalone strategy ... trading only one side is not a tested
 *    configuration." Those longs were taken inside a system that also traded
 *    shorts; while a short was open no long could be entered, so a genuinely
 *    long-only engine would have taken a DIFFERENT SET of trades.
 *
 * 2. SEGMENT is a fact about the strategy, not a customer choice, and an
 *    undeclared strategy shows nothing rather than a guessed "futures".
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  directionRecordPolicy,
  mayShowRecordFor,
  BOTH_SIDES_NOTE,
  SINGLE_SIDE_NOTE,
  type Direction,
} from "@/lib/direction-record";
import {
  instrumentFact,
  INSTRUMENT_FACT,
  VEHICLE_ALLOWED_DIRECTIONS,
} from "@/lib/billing/subscription-settings";

// ═══════════════════════════════════════════════════════════════════════
// 1. 🔴 A single-side choice carries NO record
// ═══════════════════════════════════════════════════════════════════════

describe("direction record policy", () => {
  it("BOTH sides may show the published record — it is the tested config", () => {
    const p = directionRecordPolicy("all");
    expect(p.showNumbers).toBe(true);
    expect(p.note).toBe(BOTH_SIDES_NOTE);
  });

  it.each<Direction>(["long", "short"])(
    "%s-only shows NO numbers, and says why",
    (dir) => {
      const p = directionRecordPolicy(dir);
      expect(p.showNumbers).toBe(false);
      expect(p.note).toBe(SINGLE_SIDE_NOTE);
    },
  );

  it("says plainly that one side alone was never tested", () => {
    expect(SINGLE_SIDE_NOTE).toMatch(/alag se test NAHI hua/i);
    expect(SINGLE_SIDE_NOTE).toMatch(/long\+short/i);
  });

  it("mayShowRecordFor is the guard a render site can hang off", () => {
    expect(mayShowRecordFor("all")).toBe(true);
    expect(mayShowRecordFor("long")).toBe(false);
    expect(mayShowRecordFor("short")).toBe(false);
  });

  it("🔴 no slice figure is hardcoded anywhere in the module", () => {
    const src = readFileSync(
      join(process.cwd(), "src/lib/direction-record.ts"),
      "utf8",
    );
    const code = src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
    // the long-slice headline numbers must not appear as VALUES in the code —
    // quoting them in the docstring is the point, shipping them is the bug
    for (const n of ["81.74", "5.6843", "805", "65.12", "3.8609", "344"]) {
      expect(code).not.toContain(n);
    }
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 2. Segment is a fact, and never a guess
// ═══════════════════════════════════════════════════════════════════════

describe("instrument type is displayed as a fact", () => {
  it.each([
    ["futures", "This strategy trades FUTURES"],
    ["cash", "This strategy trades CASH"],
    ["options", "This strategy trades OPTIONS"],
  ])("%s renders a statement, not a choice", (value, expected) => {
    expect(instrumentFact(value)).toBe(expected);
  });

  it("normalises case and whitespace", () => {
    expect(instrumentFact("  FUTURES ")).toBe(INSTRUMENT_FACT.futures);
  });

  it.each([null, undefined, "", "equity", "fno", "unknown"])(
    "shows NOTHING for %p rather than guessing futures",
    (value) => {
      expect(instrumentFact(value as string | null)).toBeNull();
    },
  );

  it("the phrasing is a statement — no imperative, no choice", () => {
    for (const text of Object.values(INSTRUMENT_FACT)) {
      expect(text).toMatch(/^This strategy trades /);
      expect(text).not.toMatch(/choose|select|pick|your/i);
    }
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 3. The Vehicle picker stays DISABLED
// ═══════════════════════════════════════════════════════════════════════

describe("the DIRECTION picker is now real", () => {
  const settings = readFileSync(
    join(process.cwd(), "src/components/marketplace/subscription-settings.tsx"),
    "utf8",
  );

  it("is no longer preview-only — the coming-soon marker is gone", () => {
    expect(settings).not.toContain('data-testid="direction-coming-soon"');
  });

  it("triggers are enabled by the VEHICLE constraint, not hardcoded disabled", () => {
    expect(settings).toMatch(/disabled=\{!allowed\}/);
    expect(settings).toContain("VEHICLE_ALLOWED_DIRECTIONS[vehicle].includes(d)");
  });

  it("sends direction_filter on save", () => {
    expect(settings).toContain("direction_filter: direction");
  });

  it("is settable", () => {
    expect(settings).toContain("setDirection");
    expect(settings).toMatch(/onValueChange=\{\(v\) => setDirection/);
  });

  it("🔴 carries the both-sides note and NO performance numbers", () => {
    expect(settings).toContain('data-testid="direction-record-note"');
    expect(settings).toContain("SINGLE_SIDE_NOTE");
    // no slice figure may sit beside the control
    for (const n of ["81.74", "5.6843", "805", "65.12", "3.8609", "344", "76.76", "5.0083"]) {
      expect(settings).not.toContain(n);
    }
  });
});

describe("the Vehicle picker is not enabled", () => {
  const settings = readFileSync(
    join(process.cwd(), "src/components/marketplace/subscription-settings.tsx"),
    "utf8",
  );

  it("every vehicle trigger is still disabled", () => {
    expect(settings).toMatch(/data-testid=\{`vehicle-\$\{v\}`\}\s+disabled/);
  });

  it("still carries the coming-soon marker", () => {
    expect(settings).toContain('data-testid="vehicle-coming-soon"');
  });

  it("never sends VEHICLE to the backend — it is derived, not chosen", () => {
    // Direction IS now sent (it is enforced). Vehicle is not and must not be:
    // the platform cannot honestly execute a futures signal as cash/options.
    const save = settings.slice(settings.indexOf("async function save"), settings.indexOf("async function save") + 1600);
    expect(save).not.toMatch(/vehicle:/);
    expect(save).toContain("direction_filter: direction");
  });

  it("cash is still recorded as long-only — it cannot be shorted", () => {
    expect(VEHICLE_ALLOWED_DIRECTIONS.cash).toEqual(["long"]);
  });
});
