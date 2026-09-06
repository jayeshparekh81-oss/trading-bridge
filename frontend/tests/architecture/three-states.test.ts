/**
 * ADR 0001 §4 — every data surface ships loading, empty and error.
 *
 * The audit of 2026-09-06 found only 11 of 48 data surfaces complete. The
 * failure mode is not cosmetic, and it is worth stating plainly because it is
 * what makes this a rule rather than a preference:
 *
 *   `useApi` KEEPS THE FALLBACK VISIBLE WHEN A REQUEST FAILS
 *   (src/shared/api/use-api.ts — "Keep fallback data visible if available").
 *
 * So a caller that passes `fallback` and never reads `error` does not render a
 * blank box on failure. It renders the fallback AS IF IT WERE THE TRUTH. On a
 * trading product that means an outage shows "₹0.00 today" and "0 open
 * positions" — a customer can believe they are flat when they are not. The
 * founder met the same class of bug as B1: a subscriber told they had no
 * subscription, because an empty array and a failed request looked identical.
 *
 * This test therefore enforces one precise thing: a file that fetches must be
 * able to SEE its own failure. Whether it then renders a banner or a retry is
 * a design choice; being unable to tell success from failure is not.
 */
import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const SRC = join(process.cwd(), "src");
const read = (p: string) => readFileSync(p, "utf8");

function walk(dir: string, out: string[] = []): string[] {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.tsx?$/.test(n)) out.push(p);
  }
  return out;
}

const rel = (p: string) => p.slice(process.cwd().length + 1);

/** Comments mention `useApi` too; only real calls count. */
const stripComments = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

/**
 * Customer-facing files that fetch. Excluded: the admin console (a staff tool),
 * and use-api.ts itself, which defines the hook rather than calling it.
 */
const fetchers = walk(SRC)
  .filter((p) => !p.includes("/admin/"))
  .filter((p) => rel(p) !== "src/shared/api/use-api.ts")
  .filter((p) => /\buseApi\s*[<(]/.test(stripComments(read(p))));

/**
 * Does the file observe the failure of its own fetch?
 *   const { error } = useApi(...)          -> yes
 *   const x = useApi(...);  x.error        -> yes
 *   const { data } = useApi(...)           -> NO: a failure is invisible to it
 */
function observesError(raw: string): boolean {
  const src = stripComments(raw);
  // Destructured directly off the call.
  if (/\{[^}]*\berror\b[^}]*\}\s*=\s*useApi\s*[<(]/.test(src)) return true;
  // Named result, then `.error` (possibly renamed via `: alias`).
  const named = [...src.matchAll(/(?:const|let)\s+(\w+)\s*=\s*useApi\s*[<(]/g)].map((m) => m[1]);
  if (named.some((n) => new RegExp(`\\b${n}\\s*\\.\\s*error\\b`).test(src))) return true;
  // Destructured with a rename: { error: signalsError }
  if (/\{[^}]*\berror\s*:\s*\w+[^}]*\}\s*=\s*useApi\s*[<(]/.test(src)) return true;
  return false;
}

/**
 * Files that fetch but deliberately do not surface their own error, each with a
 * reason. This is a DEBT LEDGER, not an amnesty: the count may shrink, never
 * grow, and the test below enforces that.
 */
const BLIND_TO_ERRORS: Record<string, string> = {
  "src/components/marketplace/ledger-history-modal.tsx":
    "Ledger history is supplementary detail inside an already-loaded panel; the panel owns the error surface.",
  "src/hooks/useAlgoMitraLive.ts":
    "Coaching hints are advisory garnish — a failed hint must stay silent rather than raise an alarm about money.",
};

describe("ADR 0001 §4 — a data surface can see its own failure", () => {
  it("every fetching file observes its error, or is a declared, reasoned exception", () => {
    const blind = fetchers
      .filter((p) => !observesError(read(p)))
      .map(rel)
      .filter((p) => !BLIND_TO_ERRORS[p]);
    expect(
      blind,
      "These files call useApi and never look at `error`. Because useApi keeps the fallback\n" +
        "visible on failure, an outage renders as real data — a zero P&L or an empty list the\n" +
        "customer will believe. Read the error and say something true, or add the file to\n" +
        "BLIND_TO_ERRORS with a reason:\n  " +
        blind.join("\n  "),
    ).toEqual([]);
  });

  it("the debt ledger only shrinks", () => {
    // Lowering this number is the point. Raising it needs a deliberate edit and
    // an argument, which is exactly the conversation that should happen.
    expect(Object.keys(BLIND_TO_ERRORS).length).toBeLessThanOrEqual(2);
  });

  it("every declared exception still points at a file that fetches", () => {
    const all = new Set(fetchers.map(rel));
    const stale = Object.keys(BLIND_TO_ERRORS).filter((p) => !all.has(p));
    expect(stale, `Exception for a file that no longer fetches: ${stale.join(", ")}`).toEqual([]);
  });

  it("every declared exception carries a real reason", () => {
    for (const [file, reason] of Object.entries(BLIND_TO_ERRORS)) {
      expect(reason.length, `${file}: reason too short`).toBeGreaterThan(30);
      expect(reason, `${file}: placeholder reason`).not.toMatch(/^(TODO|FIXME|later|n\/a)/i);
    }
  });
});

/**
 * The money-facing surfaces get a second, stricter check. On these, a number
 * rendered during loading or after a failure is not a gap — it is a false
 * statement about the customer's money or exposure.
 */
describe("ADR 0001 §4 — money-facing surfaces never print a number they have not got", () => {
  const MONEY_SURFACES = [
    "src/app/(dashboard)/page.tsx", // Overview: today's P&L, open positions
    "src/app/(dashboard)/positions/page.tsx", // status chips
    "src/app/(dashboard)/trades/page.tsx", // execution stats
    "src/app/(dashboard)/analytics/page.tsx", // round trips, total P&L
  ];

  it.each(MONEY_SURFACES)("%s observes its fetch errors", (file) => {
    expect(observesError(read(join(process.cwd(), file)))).toBe(true);
  });
});
