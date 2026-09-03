/**
 * The rule-disclosure claim is GONE from shipped copy, and must not creep back
 * — IN ANY LANGUAGE OR SYNONYM.
 *
 * WHY THIS FILE WAS REWRITTEN. Its first version scanned for the English
 * strings "white-box", "or skipped", "why it passed". It passed, and the claim
 * was still live on the login page — the first screen every customer sees —
 * because the product ships the same claim under two spellings this test had
 * never heard of:
 *
 *   "Glass Box · Transparent Algo Trading"        <- a SYNONYM for white-box
 *   "aap dekh sakte ho har trade kyun liya
 *    ya chhoda gaya"                              <- the HINGLISH of
 *                                                    "why a trade was taken
 *                                                     or skipped"
 *
 * Found only by loading the production site and reading it. A guard that
 * enumerates English phrasings on a bilingual product is not a guard; it is a
 * spellchecker for one of the two languages we ship.
 *
 * SO THE RULE HERE IS: enumerate the CLAIM, in every language and synonym we
 * actually ship, and keep the vocabulary in one exported list so adding a new
 * marketing phrase means adding it here too. The last test in this file fails
 * if the vocabulary ever shrinks.
 *
 * THE CLAIMS, and why each is false:
 *
 *  1. RULE DISCLOSURE ("white box" / "glass box" / "rules are replicable").
 *     False since marketplace listings were deliberately MASKED — a subscriber
 *     sees "Strategy S1" and no rules at all. Masking is the settled product
 *     decision; the claim is what had to go.
 *
 *  2. SKIP-REASON VISIBILITY ("why a trade was taken or skipped" /
 *     "kyun liya ya chhoda gaya"). Describes an event that has never happened:
 *     on the live strategy being sold the validator has REJECTED 0 of 40
 *     signals, and 26 of those carry no decision at all.
 *
 * The true claim — EXECUTION transparency, "you see every signal before it
 * acts" — is asserted positively at the bottom, so a future edit cannot quietly
 * delete the honest version along with the dishonest one.
 */

import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, sep } from "node:path";

const SRC = join(process.cwd(), "src");

/**
 * Legal + regulatory copy, tracked separately: wording there is the founder's
 * call and may need review, not a silent edit.
 */
const LEGAL = [
  "app/(public)/terms/page.tsx",
  "app/(public)/disclaimer/page.tsx",
  "app/(public)/sebi/page.tsx",
  "lib/compliance/disclaimer-text.ts",
];

/**
 * Social/video drafts. NOT rendered by the app, but they publish the same
 * claim when posted, so they are inventoried rather than ignored.
 */
const UNSHIPPED_DRAFTS = ["lib/marketing/", "lib/tutorials/"];

// ─────────────────────────────────────────────────────────────────────
// THE CLAIM VOCABULARY — every language and synonym we actually ship.
// Adding a new marketing phrase for either claim means adding it HERE.
// ─────────────────────────────────────────────────────────────────────

/** Claim 1 — that the strategy's RULES are visible/replicable. */
export const RULE_DISCLOSURE_CLAIM: readonly RegExp[] = [
  /white[\s-]?box/i,          // en
  /glass[\s-]?box/i,          // en — the synonym that survived v1 of this test
  /transparent algo trading/i, // en — the eyebrow it shipped inside
  /rules are (transparent|visible)/i,
  /replicable/i,
  /no black[\s-]?box/i,       // en
  /black[\s-]?box nahi/i,     // hinglish — "not a black box"
  /fully transparent\)? strateg/i,
];

/** Claim 2 — that the user can see why a trade was SKIPPED. */
export const SKIP_REASON_CLAIM: readonly RegExp[] = [
  /or skipped/i,                       // en
  /why (it|each trade) (passed|was taken)/i, // en
  /only trades when it clears/i,       // en
  /chhoda gaya/i,                      // hinglish — "was skipped/left"
  /kyun liya/i,                        // hinglish — "why taken"
  /auto[\s-]?reject/i,                 // en/hinglish — implies rejection happens
];

const ALL_CLAIMS = [...RULE_DISCLOSURE_CLAIM, ...SKIP_REASON_CLAIM];

function walk(dir: string, out: string[] = []): string[] {
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(tsx?|mdx?)$/.test(e)) out.push(p);
  }
  return out;
}

/** Strip comments — prose ABOUT the rule is not a violation of it. */
function code(path: string): string {
  return readFileSync(path, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

const rel = (p: string) => p.replace(SRC + sep, "src" + sep);
const inList = (p: string, list: readonly string[]) =>
  list.some((l) => p.includes(l.replace(/\//g, sep)));

/** Everything the APP renders: excludes legal (tracked) and drafts (tracked). */
const SHIPPED = walk(SRC).filter(
  (p) => !inList(p, LEGAL) && !inList(p, UNSHIPPED_DRAFTS),
);

// ═══════════════════════════════════════════════════════════════════════
// 1. 🔴 The claim, in EVERY language we ship
// ═══════════════════════════════════════════════════════════════════════

describe("no rule-disclosure claim in shipped copy, any language", () => {
  it.each(RULE_DISCLOSURE_CLAIM)("no file matches %s", (re) => {
    const hits = SHIPPED.filter((p) => re.test(code(p))).map(rel);
    expect(hits).toEqual([]);
  });
});

describe("no skip-reason claim in shipped copy, any language", () => {
  it.each(SKIP_REASON_CLAIM)("no file matches %s", (re) => {
    const hits = SHIPPED.filter((p) => re.test(code(p))).map(rel);
    expect(hits).toEqual([]);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 2. 🔴 PROOF the guard catches what v1 missed
// ═══════════════════════════════════════════════════════════════════════

describe("the guard actually catches the two phrases that survived v1", () => {
  const matchesAny = (text: string) => ALL_CLAIMS.some((re) => re.test(text));

  it("catches the SYNONYM: 'Glass Box · Transparent Algo Trading'", () => {
    expect(matchesAny("Glass Box · Transparent Algo Trading")).toBe(true);
    expect(matchesAny("GLASS BOX")).toBe(true);
    expect(matchesAny("glass-box")).toBe(true);
  });

  it("catches the HINGLISH: 'kyun liya ya chhoda gaya'", () => {
    expect(
      matchesAny(
        "Black-box nahi — aap dekh sakte ho har trade kyun liya ya chhoda gaya.",
      ),
    ).toBe(true);
    expect(matchesAny("chhoda gaya")).toBe(true);
    expect(matchesAny("Black-box nahi")).toBe(true);
  });

  it("still catches the ORIGINAL english phrasings", () => {
    expect(matchesAny("white-box (fully transparent) strategies only")).toBe(true);
    expect(matchesAny("Strategy rules are transparent and replicable")).toBe(true);
    expect(matchesAny("you see why each trade was taken or skipped")).toBe(true);
  });

  it("does NOT fire on the honest claim", () => {
    expect(matchesAny("Every signal, before it acts")).toBe(false);
    expect(matchesAny("You see each entry and exit with its price, stop and target")).toBe(false);
    expect(matchesAny("Strategy internals stay with the creator")).toBe(false);
    expect(matchesAny("Har signal apne conviction score ke saath dikhta hai")).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 3. The vocabulary must not shrink
// ═══════════════════════════════════════════════════════════════════════

describe("the claim vocabulary is bilingual and cannot be quietly narrowed", () => {
  it("covers BOTH languages we ship", () => {
    const src = readFileSync(join(process.cwd(), "tests/copy/no-white-box-claim.test.ts"), "utf8");
    // hinglish entries must be present — deleting them is how v1 failed
    expect(src).toMatch(/chhoda gaya/);
    expect(src).toMatch(/black\[\\s-\]\?box nahi/i);
    expect(RULE_DISCLOSURE_CLAIM.length).toBeGreaterThanOrEqual(8);
    expect(SKIP_REASON_CLAIM.length).toBeGreaterThanOrEqual(6);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 4. The illustrative REJECTION is gone
// ═══════════════════════════════════════════════════════════════════════

describe("the conviction demo shows no rejection", () => {
  const panel = readFileSync(
    join(SRC, "components/brand/conviction-panel.tsx"), "utf8");

  it("has no below-threshold sample row", () => {
    const scores = [...panel.matchAll(/score:\s*([\d.]+)/g)].map((m) => Number(m[1]));
    expect(scores.length).toBeGreaterThan(0);
    // THRESHOLD is 0.6; a row beneath it renders as REJECTED
    expect(scores.every((s) => s >= 0.6)).toBe(true);
  });

  it("the caption promises nothing about skipped trades", () => {
    expect(code(join(SRC, "components/brand/conviction-panel.tsx")))
      .not.toMatch(/chhoda gaya|or skipped/i);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 5. The TRUE claim survives, and the tracked lists stay honest
// ═══════════════════════════════════════════════════════════════════════

describe("the honest claim is still made", () => {
  const showcase = readFileSync(join(SRC, "app/(public)/showcase/page.tsx"), "utf8");

  it("showcase leads on seeing the signal", () => {
    expect(showcase).toContain("Every signal, before it acts");
    expect(showcase).toMatch(/internal rules stay with the creator/i);
    expect(showcase).toMatch(/shows you every signal and every fill/i);
  });

  it("keeps the claims that are still TRUE", () => {
    expect(showcase).toMatch(/Your money, your broker/);
    expect(showcase).toMatch(/Paper-trade first/);
    expect(showcase).toMatch(/No guaranteed returns are claimed/);
  });
});

describe("legal + unshipped drafts are tracked, not silently edited", () => {
  it("legal copy still carries the claim — flagged for a deliberate decision", () => {
    const still = LEGAL.filter((r) =>
      ALL_CLAIMS.some((re) => re.test(readFileSync(join(SRC, r), "utf8"))),
    );
    expect(still.length).toBeGreaterThan(0);
  });

  it("social/video drafts still carry it — they publish the claim when posted", () => {
    const drafts = walk(SRC).filter((p) => inList(p, UNSHIPPED_DRAFTS));
    const carrying = drafts.filter((p) =>
      ALL_CLAIMS.some((re) => re.test(readFileSync(p, "utf8"))),
    );
    // INVENTORY, not approval. Rewriting them should shrink this to zero.
    expect(carrying.length).toBeGreaterThan(0);
  });
});
