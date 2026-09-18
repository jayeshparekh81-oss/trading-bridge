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

describe("the orders page is the BOT's log, and says so", () => {
  /**
   * 🔴 THIS BLOCK REPLACES AN EARLIER, SUPERSEDED DESIGN — and the supersession
   * is the founder's, not a judgement call made here.
   *
   * The previous assertions required /trades to grow a "Broker par hue baaki
   * fills" section listing the account's OTHER fills, labelled engine_stop /
   * manual / unknown. Neither half was ever built: the backend serves no
   * `broker_fills` field at all (grep `broker_fills` under backend/app —
   * nothing), so these tests described a feature that did not exist, and had
   * been failing at HEAD before this branch touched them.
   *
   * ROUND 3 then settled the question the other way, explicitly:
   *
   *     "/trades: bot fills only incl. broker stop (auto); no manual, no other
   *      instruments."
   *
   * And the need the old section was meant to serve — the founder must learn
   * about a hand-placed trade on the bot's symbol — is met better by R3's
   * 15:50 check, which sends it to his PHONE the same day
   * (`HAATH SE TRADE ⚠️ …`) instead of publishing his personal trading on a
   * page shown to other people. Manual fills are recorded in
   * `broker_fill_provenance`, which is an audit table, not a customer surface.
   *
   * So what is pinned now is the opposite property: this page shows the bot's
   * own orders, INCLUDING the engine's broker-side stop, and nothing else.
   */

  it("the engine's own broker stop IS shown — it is the bot's exit", () => {
    // pine_replica places it straight at Dhan, so it has no platform order.
    // Excluding it would hide the fill that actually closed two round trips.
    expect(TRADES).toContain("broker_stop:");
    expect(TRADES).toContain("BROKER STOP (AUTO)");
  });

  it("the page carries no section that publishes the account's manual trades", () => {
    expect(TRADES).not.toContain("Broker par hue baaki fills");
    expect(TRADES).not.toContain("broker_fills");
  });

  it("falsification twin: the page is not simply empty of everything", () => {
    // Deleting the table would satisfy the assertion above while destroying
    // the page. It still renders our own orders, grouped one row per broker
    // order by the shared rule.
    expect(TRADES).toContain("groupLegsIntoOrders");
    expect(TRADES).toContain("LEG_ROLE_LABEL");
    expect(TRADES).toContain("brokerOrderId");
  });

  it("falsification twin: it still no longer claims manual trades are absent", () => {
    // The original copy asserted the account had no other activity, which was
    // false. Saying nothing is honest; saying "there are none" was not.
    expect(TRADES).not.toContain("Aapke manual trades yahan nahi hain");
  });
});
