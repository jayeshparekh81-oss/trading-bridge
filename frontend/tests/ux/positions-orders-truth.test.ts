/**
 * Two promises the UI was making that the data could not keep.
 *
 * 1. THE POSITIONS SUBTITLE. It read "Abhi jo trades khuli hain, unka live
 *    P&L." The page has never shown a live P&L: `final_pnl` is written only
 *    when a trade CLOSES and is reconciled against the broker's fills, so
 *    every OPEN row under that sentence had no P&L at all. Showing one would
 *    mean polling an LTP per open position on the same Dhan quota the trading
 *    engine uses — a separate founder decision, not something a subtitle gets
 *    to imply.
 *
 * 2. THE ORDERS PAGE SAYING THE ACCOUNT'S OTHER FILLS "ARE NOT HERE". True of
 *    our table, silent about the account. Six real fills on BSE-SEP2026-FUT in
 *    Sept 2026 had no row — including the ENTIRE exit of the 07-Sep round trip,
 *    taken by pine_replica's own resting stop (order 312260908126806). The page
 *    now carries a second, separately-labelled section for them.
 *
 * Each assertion has a falsification twin so a blanket edit — deleting the
 * blurb, or emptying the page — cannot pass.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const read = (p: string) => readFileSync(join(process.cwd(), p), "utf8");

const NAV = read("src/lib/nav/pro-nav.ts");
const TRADES = read("src/app/(dashboard)/trades/page.tsx");

describe("the positions subtitle does not promise a live P&L", () => {
  it("no longer claims live P&L", () => {
    const positionsBlurb = NAV.match(/href:\s*"\/positions"[\s\S]{0,600}?blurb:\s*"([^"]+)"/);
    expect(positionsBlurb, "the /positions nav entry lost its blurb").toBeTruthy();
    expect(positionsBlurb![1].toLowerCase()).not.toContain("live p&l");
  });

  it("falsification twin: the entry still HAS a blurb and still points at /positions", () => {
    // A blanket deletion would satisfy the assertion above while making the
    // nav worse, so the twin pins that something honest is still said.
    const positionsBlurb = NAV.match(/href:\s*"\/positions"[\s\S]{0,600}?blurb:\s*"([^"]+)"/);
    expect(positionsBlurb![1].trim().length).toBeGreaterThan(10);
    expect(NAV).toContain('href: "/positions"');
  });
});

describe("the orders page shows the account's other fills, labelled", () => {
  it("renders a broker-fills section fed by the API", () => {
    expect(TRADES).toContain("broker_fills");
    expect(TRADES).toContain("Broker par hue baaki fills");
  });

  it("labels each fill by who placed it, and never guesses", () => {
    expect(TRADES).toContain("FILL_SOURCE_LABEL");
    for (const source of ["engine_stop", "manual", "unknown"]) {
      expect(TRADES, `${source} has no label`).toContain(source);
    }
  });

  it("distinguishes 'not read yet' from 'nothing happened'", () => {
    // The dangerous case. An empty list must never render as an assertion that
    // the account was quiet — that is the same silence this section exists to
    // end, just one layer up.
    expect(TRADES).toContain("broker_fills_known");
    expect(TRADES).toContain("brokerFillsKnown");
  });

  it("falsification twin: the two populations are NOT merged", () => {
    // Our orders carry our ids; these carry none. Merging them into one list
    // would put fills we never placed into the platform's own order log.
    expect(TRADES).toContain("groupLegsIntoOrders");
    expect(TRADES).not.toMatch(/executions\s*\.concat\(\s*brokerFills/);
    expect(TRADES).not.toMatch(/\[\s*\.\.\.all\s*,\s*\.\.\.brokerFills\s*\]/);
  });

  it("falsification twin: the page no longer claims manual trades are absent", () => {
    expect(TRADES).not.toContain("Aapke manual trades yahan nahi hain");
  });
});
