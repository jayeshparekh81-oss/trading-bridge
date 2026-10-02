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
const DIRS = ["app/(public)", "app/(auth)", "app/start", "app/onboarding", "components/strategy", "components/marketing", "components/brand", "components/site", "components/billing",
  // 2 Oct 2026 (founder walked the live site as the test customer: "LOGGED-IN SCREENS ARE STILL
  // ENGLISH … extend the guard to EVERY logged-in customer screen"): the Simple chrome, the dashboard
  // chrome, the guided path and the journey, plus every file of THE ONE screen list below.
  "components/simple", "components/dashboard", "components/guided", "components/journey", "components/marketplace", "components/brokers", "components/support"];
/** Files that are NOT customer copy and are excluded with the reason. */
const EXCLUDE: { file: RegExp; why: string }[] = [
  { file: /lib\/simple\/copy\.ts$/, why: "the four-language dictionary — its `en` block IS the English option a customer may choose; the DEFAULT is Hinglish (pinned in tests/guided/loop-and-later.test.tsx)" },
];

import { ENGLISH_CTA_WORDS } from "./english-cta-words";
export { ENGLISH_CTA_WORDS };


/** Every file of THE ONE screen list (tests/copy/customer-screens.ts) — the logged-in screens included. */
function screenListFiles(): string[] {
  const src = readFileSync(resolve(__dirname, "customer-screens.ts"), "utf8");
  const body = src.slice(src.indexOf("CUSTOMER_SCREENS"), src.indexOf("FIRST_TIMER_SCREENS"));
  return [...body.matchAll(/"(src\/[^"]+\.tsx?)"/g)].map((m) => join(ROOT, m[1].slice(4)));
}

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
  const files = DIRS.flatMap((d) => walk(join(ROOT, d)))
    .concat(screenListFiles())
    .filter((f, i, arr) => arr.indexOf(f) === i)
    .filter((f) => !EXCLUDE.some((e) => e.file.test(f)));

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
