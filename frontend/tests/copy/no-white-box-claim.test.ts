/**
 * The white-box claim is GONE from marketing copy, and must not creep back.
 *
 * Why this test exists, in one paragraph, because whoever trips it will need it:
 *
 * TRADETRI publicly claimed "Strategy rules are transparent and replicable — no
 * black box" and "white-box (fully transparent) strategies only". Both became
 * false the moment marketplace listings were deliberately MASKED — a subscriber
 * sees "Strategy S1" and no rules at all. Masking is the settled product
 * decision; the claim is what had to go. On a financial product a false
 * transparency claim is misrepresentation, not marketing polish.
 *
 * The real differentiator is EXECUTION transparency — you see every signal
 * before it acts, with price/stop/target, and you approve it — not RULE
 * disclosure. Copy may say the former. It may not say the latter.
 *
 * Also pinned: the AI-conviction claims. The validator has never once REJECTED
 * a signal on the live strategy being sold (0 of 40; 26 carry no decision at
 * all), so copy claiming users "see why a trade was skipped" describes an event
 * that has never happened. It is advisory, and must be described that way.
 */

import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, sep } from "node:path";

const SRC = join(process.cwd(), "src");

/** Legal + regulatory pages are EXCLUDED and tracked separately below: their
 *  wording is the founder's call and may need review, not a silent edit. */
const LEGAL = [
  "app/(public)/terms/page.tsx",
  "app/(public)/disclaimer/page.tsx",
  "app/(public)/sebi/page.tsx",
];

function walk(dir: string, out: string[] = []): string[] {
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(tsx?|mdx?)$/.test(e)) out.push(p);
  }
  return out;
}

/** Strip comments — prose ABOUT the rule is not the rule being broken. */
function code(path: string): string {
  return readFileSync(path, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

const MARKETING = walk(SRC).filter(
  (p) => !LEGAL.some((l) => p.endsWith(l.replace(/\//g, sep))),
);

describe("no white-box / rule-disclosure claim in marketing copy", () => {
  it("the phrase 'white-box' appears nowhere", () => {
    const hits = MARKETING.filter((p) => /white[- ]?box/i.test(code(p)))
      .map((p) => p.replace(SRC, "src"));
    expect(hits).toEqual([]);
  });

  it("no claim that strategy RULES are transparent or replicable", () => {
    const bad = /rules are transparent|replicable|no black box|fully transparent\)? strateg/i;
    const hits = MARKETING.filter((p) => bad.test(code(p))).map((p) => p.replace(SRC, "src"));
    expect(hits).toEqual([]);
  });

  it("the unverifiable Ledger claim is gone, not reworded", () => {
    const page = code(join(SRC, "app/(public)/showcase/page.tsx"));
    expect(page).not.toMatch(/verifiable on the Ledger/i);
    // and nothing replaced it with an equivalent promise
    expect(page).not.toMatch(/every live result is/i);
  });
});

describe("AI conviction is described as ADVISORY, not as a gate", () => {
  const bad = [
    /why (it|each trade) (passed|was taken)/i,
    /or skipped/i,
    /only trades when it clears/i,
  ];

  it.each(bad)("no copy claims %s", (re) => {
    const hits = MARKETING.filter((p) => re.test(code(p))).map((p) => p.replace(SRC, "src"));
    expect(hits).toEqual([]);
  });

  it("the OPAQUE comparison row is gone — it described us", () => {
    const home = code(join(SRC, "app/(public)/home/page.tsx"));
    expect(home).not.toMatch(/title: "OPAQUE"/);
    expect(home).not.toMatch(/Black-box signals/i);
  });
});

describe("what the copy DOES say is the true claim", () => {
  it("showcase leads on seeing the signal, and says rules stay with the creator", () => {
    const page = readFileSync(join(SRC, "app/(public)/showcase/page.tsx"), "utf8");
    expect(page).toContain("Every signal, before it acts");
    expect(page).toMatch(/internal rules stay with the creator/i);
    expect(page).toMatch(/shows you every signal and every fill/i);
  });

  it("keeps the claims that are still TRUE", () => {
    const page = readFileSync(join(SRC, "app/(public)/showcase/page.tsx"), "utf8");
    expect(page).toMatch(/Your money, your broker/);
    expect(page).toMatch(/Paper-trade first/);
    expect(page).toMatch(/No guaranteed returns are claimed/);
  });
});

describe("legal + regulatory pages are tracked, not silently edited", () => {
  it("still carry the claim — flagged for a deliberate decision", () => {
    const still = LEGAL.filter((rel) => /white[- ]?box/i.test(readFileSync(join(SRC, rel), "utf8")));
    // This is an INVENTORY, not an approval. If these are rewritten later,
    // update this list in the same commit so the count stays honest.
    expect(still.sort()).toEqual([...LEGAL].sort());
  });
});
