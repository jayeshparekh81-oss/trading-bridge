/**
 * ONE VOICE on every customer-facing route (founder, 2 Oct 2026: "Hinglish everywhere on
 * customer-facing pages, same as Simple Mode"). The five-page pass of 2 Oct replaced the English CTA
 * vocabulary below — and still MISSED two buttons that were served live: the public top-bar "Start
 * Free" (app/(public)/layout.tsx) and the Showcase card's "Start Free" (strategy-card.tsx). This guard
 * scans the RENDERED copy of every customer-facing route and component for that vocabulary; a comment
 * may name a word, the screen may not.
 *
 * Twin (proven 2 Oct): re-insert "Start Free" as rendered text in any listed file → RED.
 */
import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

const ROOT = resolve(__dirname, "../../src");

/** Every customer-facing route + the components that draw their CTAs. */
const DIRS = ["app/(public)", "app/(auth)", "app/start", "app/onboarding", "components/strategy", "components/marketing", "components/brand", "components/site", "components/billing"];

/** The English CTA / heading vocabulary the 2 Oct voice pass replaced (his customers' words now). */
export const ENGLISH_CTA_WORDS: RegExp[] = [
  /\bStart Free\b/,
  /\bGet Started\b/,
  /\bMost Popular\b/,
  /\bGet in Touch\b/,
  /\bSend on WhatsApp\b/,
  /\bOur Journey\b/,
  /\bOur Mission\b/,
  /\bLoading plans…/,
  /\bFeature Comparison\b/,
  /\bFrequently Asked Questions\b/,
  /\bSend a Message\b/,
  /\bSee pricing\b/,
  /\bWhat Ships When\b/,
  /\bLearn more\b/i,
  /\bSign up\b/i,
  /\bSubscribe now\b/i,
];

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (/\.(tsx|ts)$/.test(name) && !/\.test\./.test(name)) out.push(p);
  }
  return out;
}

/** Rendered copy only: strip block comments, line comments and JSX comment blocks. */
export function renderedCopy(src: string): string {
  return src
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, "")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "")
    .replace(/([^:"'])\/\/.*$/gm, "$1");
}

describe("no English CTA vocabulary on any customer-facing route (rendered copy)", () => {
  const files = DIRS.flatMap((d) => walk(join(ROOT, d)));

  it("covers the public layout, the auth doors, the start/onboarding paths and the CTA components", () => {
    const rel = files.map((f) => f.slice(ROOT.length + 1));
    expect(rel).toContain("app/(public)/layout.tsx");
    expect(rel).toContain("components/strategy/strategy-card.tsx");
    expect(rel).toContain("app/(public)/home/page.tsx");
    expect(rel).toContain("app/(auth)/login/page.tsx");
    expect(rel).toContain("components/billing/plan-checkout-button.tsx");
    expect(rel.length).toBeGreaterThan(20);
  });

  for (const re of ENGLISH_CTA_WORDS) {
    it(`${re} is on no screen`, () => {
      const hits = files
        .filter((f) => re.test(renderedCopy(readFileSync(f, "utf8"))))
        .map((f) => f.slice(ROOT.length + 1));
      expect(hits).toEqual([]);
    });
  }

  it("the comment stripper keeps rendered text and drops comments (self-check)", () => {
    expect(renderedCopy('// Start Free\n{/* Get Started */}\n<b>Shuru karo</b>')).not.toMatch(/Start Free|Get Started/);
    expect(renderedCopy('<b>Start Free</b>')).toMatch(/Start Free/);
  });
});
