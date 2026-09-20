/**
 * NO CUSTOMER-FACING SURFACE MAY STATE A PRODUCT FACT THAT IS NO LONGER TRUE.
 *
 * Founder's test, 20 Sep 2026 (RULES #39-40): *"would this embarrass me if a
 * customer saw it today?"*
 *
 * WHY THIS FILE EXISTS. Four things were being told to customers on
 * `origin/main` that were measurably false on the same day:
 *
 *   PRICES     AlgoMitra's knowledge base said "Tier 1 — Free … Tier 2 —
 *              ₹999/mo … Tier 3 — coming soon" while
 *              `api.tradetri.com/api/pricing/plans` (HTTP 200, read 20 Sep)
 *              serves Starter ₹999 / Pro ₹2,499 / Premium ₹4,999 and no free
 *              tier at all. A price is a DB fact; copy must never hold a
 *              second copy of it.
 *   EXPIRY     "NIFTY/BANKNIFTY/FINNIFTY/MIDCPNIFTY har Tuesday-Friday alag
 *              (rotating expiry)", "Monthly: last Thursday" and "NIFTY weekly
 *              options expire **Thursday**". The founder's own record
 *              (kb/REQUIREMENTS.md §11) says NIFTY weekly is TUESDAY, and
 *              TRADETRI's own money-path code does not hard-code a weekday —
 *              `futures_resolver.py` tracks the exchange's last-Tuesday shift
 *              from the live scrip master.
 *   TIMELINE   "3-6 months: Strategy marketplace (community shared)" while the
 *              marketplace is deployed, browsable and subscribable today
 *              (paper execution only).
 *   SLA        "Target 99.9% during market hours … redundant DB … real-time
 *              status page". Measured: one postgres container on one EC2 box,
 *              `pg_stat_replication` = 0 rows, no standby, no status route.
 *
 * Plus two dead ends found by the same sweep: an error on the broker screen
 * that named what broke inside the server instead of what to do next, and
 * three places sending a customer to a "Settings → Privacy / Account" screen
 * that has never existed (no delete-account route exists in the backend
 * either).
 *
 * The vocabulary below is the exact wording that shipped, in every language
 * we ship it in. Enumerating English only is how a bilingual product keeps
 * its lie — the lesson of `no-white-box-claim.test.ts`.
 */

import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, sep } from "node:path";

const SRC = join(process.cwd(), "src");

/** A price or tier that is a DB fact, copied into shipped text. */
export const STALE_PLAN_FACT: readonly RegExp[] = [
  /Tier 1 — Free/i,
  /Tier 1 Free/i,
  /Tier 2 — ₹/i,
  /₹\s?(999|2,?499|4,?999)\s*\/\s*(mo|month|mahina|महीना)/i,
];

/** An expiry weekday stated from memory. Regulators move these. */
export const STALE_EXPIRY_FACT: readonly RegExp[] = [
  /rotating expiry/i,
  /Tuesday-Friday/i,
  /last Thursday/i,
  /weekly options \*\*Thursday\*\*/i,
  /weekly options expire \*\*Thursday\*\*/i,
];

/** Something shipped, described as months away. */
export const SHIPPED_BUT_CALLED_FUTURE: readonly RegExp[] = [
  /marketplace \(community/i,
  /marketplace \(community-shared\)/i,
];

/** A reliability promise nothing on this box can keep. */
export const UNKEEPABLE_SLA: readonly RegExp[] = [
  /99\.9\s*%/,
  /redundant DB/i,
  /status page jaldi/i,
  // NOTE: the phrase "uptime guarantee" itself is NOT banned — it is the
  // customer's own question ("What is the uptime guarantee?") and the honest
  // answer has to repeat it in order to say there isn't one.
];

/** A screen or button that does not exist. */
export const SCREEN_THAT_DOES_NOT_EXIST: readonly RegExp[] = [
  /Settings → Privacy/i,
  /Settings → Account/i,
];

/** An error that says what broke instead of what to do (RULES #40). */
export const WHAT_FAILED_NOT_WHAT_TO_DO: readonly RegExp[] = [
  /Backend returned/i,
  /Failed to connect broker/i,
  /Failed to start reconnect/i,
  /Reconnect not supported for/i,
];

const ALL = [
  ...STALE_PLAN_FACT,
  ...STALE_EXPIRY_FACT,
  ...SHIPPED_BUT_CALLED_FUTURE,
  ...UNKEEPABLE_SLA,
  ...SCREEN_THAT_DOES_NOT_EXIST,
  ...WHAT_FAILED_NOT_WHAT_TO_DO,
];

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
const SHIPPED = walk(SRC);

/** This guard's own source is the one file allowed to hold the vocabulary. */
const hits = (re: RegExp) => SHIPPED.filter((p) => re.test(code(p))).map(rel);

// ═══════════════════════════════════════════════════════════════════════
// 1. 🔴 No shipped file states a fact we have measured to be false
// ═══════════════════════════════════════════════════════════════════════

describe("plan prices live in the DB, never in copy", () => {
  it.each(STALE_PLAN_FACT)("no file matches %s", (re) => {
    expect(hits(re)).toEqual([]);
  });
});

describe("no expiry weekday is stated from memory", () => {
  it.each(STALE_EXPIRY_FACT)("no file matches %s", (re) => {
    expect(hits(re)).toEqual([]);
  });
});

describe("nothing already shipped is described as months away", () => {
  it.each(SHIPPED_BUT_CALLED_FUTURE)("no file matches %s", (re) => {
    expect(hits(re)).toEqual([]);
  });
});

describe("no uptime promise we do not run", () => {
  it.each(UNKEEPABLE_SLA)("no file matches %s", (re) => {
    expect(hits(re)).toEqual([]);
  });
});

describe("no customer is sent to a screen that does not exist", () => {
  it.each(SCREEN_THAT_DOES_NOT_EXIST)("no file matches %s", (re) => {
    expect(hits(re)).toEqual([]);
  });
});

describe("an error says what to DO, not what failed", () => {
  it.each(WHAT_FAILED_NOT_WHAT_TO_DO)("no file matches %s", (re) => {
    expect(hits(re)).toEqual([]);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 2. 🔴 The honest replacements are actually there
// ═══════════════════════════════════════════════════════════════════════

describe("the corrected facts ship", () => {
  const faqs = readFileSync(join(SRC, "lib", "algomitra-faqs.ts"), "utf8");
  const help = readFileSync(join(SRC, "lib", "help", "faq-content.ts"), "utf8");
  const brokers = readFileSync(
    join(SRC, "app", "(dashboard)", "brokers", "page.tsx"),
    "utf8",
  );

  it("the pricing answer points at the one source instead of a number", () => {
    expect(faqs).toMatch(/pricing page pe hain/);
    expect(faqs).toMatch(/\/pricing/);
  });

  it("the expiry answer names Tuesday and the broker's contract list", () => {
    expect(faqs).toMatch(/weekly expiry TUESDAY/);
    expect(faqs).toMatch(/broker ki contract list/);
    expect(help).toMatch(/weekly options expire \*\*Tuesday\*\*/);
  });

  it("the roadmap says the marketplace is live, and names its one limit", () => {
    expect(faqs).toMatch(/Abhi live hai/);
    expect(faqs).toMatch(/Live today/);
    expect(faqs).toMatch(/paper mode/);
  });

  it("the uptime answer admits there is no SLA and no standby", () => {
    expect(faqs).toMatch(/koi uptime guarantee ya SLA nahi hai/);
    expect(faqs).toMatch(/standby copy nahi hai/);
  });

  it("the broker screen tells the customer what to do next", () => {
    expect(brokers).toMatch(/FYERS_CONNECT_FAILED/);
    expect(brokers).toMatch(/dobara/);
    expect(brokers).toMatch(/WhatsApp/);
  });

  it("the support answer's count matches the number of routes it lists", () => {
    for (const m of faqs.matchAll(/"(Do|Two|दो|બે) options:\\n1\./g)) {
      expect(m[0]).toBeTruthy();
    }
    expect(faqs).not.toMatch(/"(Teen|Three|तीन|ત્રણ) options:/);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 3. 🔴 The guard catches what actually shipped, and spares what is innocent
// ═══════════════════════════════════════════════════════════════════════

describe("the vocabulary catches the exact strings that shipped on 20 Sep 2026", () => {
  const fires = (text: string) => ALL.some((re) => re.test(text));

  it("catches AlgoMitra's wrong prices", () => {
    expect(fires("   • Tier 1 — Free (basic webhook → broker bridge)")).toBe(true);
    expect(fires("   • Tier 2 — ₹999/mo (kill switch, multi-strategy, paper mode)")).toBe(true);
  });

  it("catches the wrong expiry facts, in both places they lived", () => {
    expect(fires("Weekly: NIFTY/BANKNIFTY/FINNIFTY/MIDCPNIFTY har Tuesday-Friday alag (rotating expiry).")).toBe(true);
    expect(fires("Monthly: stocks aur indexes ka last Thursday.")).toBe(true);
    expect(fires("NIFTY weekly options expire **Thursday** — this is the only weekly-options index left")).toBe(true);
  });

  it("catches the marketplace being called 3-6 months away", () => {
    expect(fires("- Strategy marketplace (community shared)")).toBe(true);
    expect(fires("- Strategy marketplace (community-shared)")).toBe(true);
  });

  it("catches the uptime claim", () => {
    expect(fires("Target 99.9% during market hours (9:15-15:30 IST). Infrastructure: AWS Mumbai region, redundant DB, Redis cache, Vercel edge.")).toBe(true);
  });

  it("catches the screens that do not exist", () => {
    expect(fires("Settings → Account → Delete Account.")).toBe(true);
    expect(fires("Settings → Privacy → 'Export data' / 'Delete account'.")).toBe(true);
  });

  it("catches the broker screen's jargon errors", () => {
    expect(fires('toast.error("Backend returned no OAuth URL.")')).toBe(true);
    expect(fires('e instanceof ApiError ? e.detail : "Failed to connect broker"')).toBe(true);
  });

  it("does NOT fire on the honest replacements now shipping", () => {
    expect(fires("NIFTY ka weekly expiry TUESDAY hai.")).toBe(false);
    expect(fires("Seedhi baat: koi uptime guarantee ya SLA nahi hai")).toBe(false);
    expect(fires("Fyers ka login page nahi khul paya. 1 minute ruk kar dobara “Connect” dabao.")).toBe(false);
    expect(fires("Strategy marketplace — browse karo, subscribe karo")).toBe(false);
    expect(fires("Saare plans aur current prices pricing page pe hain — /pricing kholo.")).toBe(false);
  });

  it("does NOT fire on a real price rendered from the pricing API", () => {
    expect(fires("{formatCurrency(plan.price.price_per_month_inr)}")).toBe(false);
    expect(fires("₹999")).toBe(false);
  });
});
