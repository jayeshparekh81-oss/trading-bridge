/**
 * The pricing surfaces may not advertise what the platform cannot do.
 *
 * WHY THIS EXISTS. Migration 042 moved every tier to FUTURES-only in the
 * database, because options fan-out is hard-skipped and cash has no execution
 * path. But the DB is not the only place these claims live: the pricing page's
 * own FAQ restates the whole tier matrix in PROSE, a few hundred pixels below
 * the table that renders it from the database. Correct the data and skip the
 * prose, and the page contradicts itself on one screen.
 *
 * That is the same failure the Glass Box fix hit — one surface corrected, the
 * claim still live on another — so it gets a guard rather than a promise.
 *
 * Also pinned here: the 7-day free trial claim. It was asserted as fact on the
 * home page, the pricing subhead, the pricing FAQ, and a "Start Free Trial"
 * button, and it is implemented NOWHERE — plan_status has five legal values
 * and none is a trial state, signup writes no billing fields, and the
 * subscribe call sends no start_at and no Razorpay offer. A trial promise
 * attached to billing is the worst kind to be wrong about.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const read = (p: string) => readFileSync(join(process.cwd(), p), "utf8");

const PRICING = read("src/app/(public)/pricing/page.tsx");
const HOME = read("src/app/(public)/home/page.tsx");
const CHECKOUT = read("src/components/billing/plan-checkout-button.tsx");

/** Strip comments — prose explaining the rule is not a breach of it. */
const code = (s: string) =>
  s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

// ═══════════════════════════════════════════════════════════════════════
// 1. 🔴 No trial is promised anywhere it is not implemented
// ═══════════════════════════════════════════════════════════════════════

describe("the 7-day free trial claim is gone", () => {
  const SURFACES: [string, string][] = [
    ["pricing page", PRICING],
    ["home page", HOME],
    ["checkout button", CHECKOUT],
  ];

  it.each(SURFACES)("%s promises no trial period", (_name, src) => {
    const body = code(src);
    // No duration-shaped trial claim ("7-day free trial", "14 day free trial").
    expect(body).not.toMatch(/\d+\s*[-\s]?\s*day free trial/i);
    // ...and no plan is said to CONTAIN one, however the sentence is built.
    expect(body).not.toMatch(/(includes?|come[s]? with|get[s]?) a[^".]*free trial/i);
  });

  it("the guest CTA no longer says 'Start Free Trial'", () => {
    expect(code(CHECKOUT)).not.toMatch(/Start Free Trial/);
    expect(CHECKOUT).toContain("Get Started");
  });

  it("🔴 the FAQ answers the trial question with NO, not with silence", () => {
    // Deleting the question would leave a customer to assume either way.
    expect(PRICING).toContain('q: "Is there a free trial?"');
    const answer = PRICING.split('q: "Is there a free trial?"')[1].slice(0, 400);
    expect(answer).toMatch(/^\s*,?\s*a: "No\b/m);
  });

  it("keeps the 'no credit card' line ONLY where it is true", () => {
    // Signing up genuinely takes no card; SUBSCRIBING opens a card-required
    // Razorpay checkout. So the claim is true beside a signup CTA and false
    // beside the plans.
    expect(HOME).toContain("No credit card required.");
    expect(code(HOME)).not.toMatch(/all plans include.*no credit card/i);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 2. 🔴 The prose FAQ may not contradict the DB-driven table above it
// ═══════════════════════════════════════════════════════════════════════

describe("the tier prose tracks migration 042", () => {
  const faq = PRICING.split('q: "What does each plan actually unlock?"')[1]
    ?.slice(0, 600) ?? "";

  it("the question still exists to be checked", () => {
    expect(faq).not.toBe("");
  });

  it("does not sell CASH or OPTIONS as included", () => {
    expect(faq).not.toMatch(/CASH \+ OPTIONS/);
    expect(faq).not.toMatch(/in CASH\b/);
    // Naming them as NOT included is the whole point, so a bare mention is
    // allowed only in that shape.
    if (/cash|option/i.test(faq)) {
      expect(faq).toMatch(/coming|not include|no plan includes/i);
    }
  });

  it("says futures, which is what actually executes", () => {
    expect(faq).toMatch(/FUTURES/);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 3. The comparison table matches 042's key set
// ═══════════════════════════════════════════════════════════════════════

describe("the comparison table's rows match the migrated blob", () => {
  const rows = PRICING.split("const faqs")[0];

  it("dropped the Shadow Stop-Loss row along with the key", () => {
    // It had no backend at all; false on every tier it renders an empty row.
    expect(code(rows)).not.toMatch(/shadowSl/);
    expect(code(rows)).not.toMatch(/Shadow Stop-Loss/);
  });

  it("renders comingSoon in its OWN row, labelled not-included", () => {
    expect(rows).toMatch(/key: "comingSoon"/);
    const line = rows.split("\n").find((l) => l.includes('key: "comingSoon"')) ?? "";
    expect(line).toMatch(/not included/i);
    expect(line).toMatch(/list: true/);
  });

  it("de-escalates the AI label from 'Smart Signals' to advisory", () => {
    expect(code(rows)).not.toMatch(/AI Smart Signals/);
    const line = rows.split("\n").find((l) => l.includes('key: "ai"')) ?? "";
    expect(line).toMatch(/advisory/i);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 4. 🔴 Features are only sold where a CUSTOMER can use them
// ═══════════════════════════════════════════════════════════════════════

const ALGOMITRA = read("src/lib/algomitra-faqs.ts");
const HELP = read("src/lib/help/faq-content.ts");
const LAYOUT = read("src/app/layout.tsx");

describe("CSV export is advertised ONLY because a customer can now reach it", () => {
  // The feature was set false in 042 because nothing in the UI called the
  // endpoint. It is TRUE again (043) because /trades now has an Export CSV
  // button that downloads what the page shows. These tie the claim to the
  // control so neither can drift alone.
  const TRADES = read("src/app/(dashboard)/trades/page.tsx");

  it("🔴 the control exists and hits the executions export, not the empty legacy table", () => {
    expect(TRADES).toContain('data-testid="export-csv"');
    expect(TRADES).toContain('"/strategies/executions/export"');
    expect(code(TRADES)).not.toContain("/users/me/trades/export");
  });

  it("AlgoMitra's answer names that button, and no longer says it is missing", () => {
    const i = ALGOMITRA.indexOf('id: "trade-export"');
    const answer = ALGOMITRA.slice(i, i + 900);
    expect(answer).toMatch(/Export CSV/);
    expect(answer).not.toMatch(/koi Export button nahi hai/);
    expect(answer).not.toMatch(/Export button\s*→/); // the old imaginary path
  });
});

describe("pricing lives in ONE place", () => {
  it("🔴 /help states no price, period, or trial of its own", () => {
    const body = code(HELP);
    expect(body).not.toMatch(/free trial/i);
    expect(body).not.toMatch(/3-month/i);
    // "Free during the paper-trading phase … No credit card needed"
    expect(body).not.toMatch(/no credit card needed/i);
    expect(body).not.toMatch(/credit card ki zaroorat nahi/i);
  });

  it("/help points at /pricing instead of going silent", () => {
    expect(HELP).toContain('id: "pricing-where"');
    expect(HELP).toMatch(/\/pricing/);
  });

  it("🔴 AlgoMitra no longer says tiers are unfinalised", () => {
    // They ARE published — /pricing takes money for them today.
    const body = code(ALGOMITRA);
    expect(body).not.toMatch(/finalis|finaliz/i);
    expect(body).not.toMatch(/target Q3/i);
    expect(body).not.toMatch(/early access is discounted/i);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 5. 🔴 The claim that travels furthest: SEO + link previews
// ═══════════════════════════════════════════════════════════════════════

describe("site metadata does not ship the caps 041 removed", () => {
  it("no '6 brokers' or '200 strategies' in meta OR og description", () => {
    // These render into every page's <meta description> and into og:description
    // on every shared link — the first thing anyone sees from a share.
    expect(LAYOUT).not.toMatch(/6 brokers/i);
    expect(LAYOUT).not.toMatch(/200 strategies/i);
  });

  it("both copies were replaced, not just the first", () => {
    // metadata.description and openGraph.description are separate strings; a
    // single-replace fix would leave the share preview stale.
    const hits = LAYOUT.match(/Every signal is shown before it acts/g) ?? [];
    expect(hits.length).toBe(2);
  });
});
