/**
 * R4 — the page must SHOW the record, not just assert a total.
 *
 * The founder's goal, in his words: /positions and /trades must show the BSE
 * bot's live record since 1 Sep 2026 exactly as Dhan fills show it — every
 * AUTOMATED order (entry, partial, broker stop (auto), SL / trailing exit)
 * with qty, fill price, IST time, order id and P&L.
 *
 * A P&L whose fills cannot be read off the screen is a number the reader has
 * to take on trust, and this page is shown to other people.
 *
 * Every assertion has a falsification twin, because "delete the column" would
 * satisfy a naive "must not say X" check while making the page worse.
 *
 * ⚠️ WHAT THIS FILE CANNOT DO, measured rather than assumed. These assertions
 * read the page SOURCE. That is the right tool for WORDING — a banned phrase
 * is a fact about the text — but it cannot prove anything RENDERS. Changing
 * the legs' surrounding condition to `false` removes the entire section from
 * the customer's screen and leaves every string in this file intact: all 16
 * assertions here still passed, while the render test failed 5.
 *
 * So behaviour is pinned in tests/positions/legs-and-badge.test.tsx, which
 * mounts the page. Keep both: this one guards the copy, that one guards the
 * customer.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const read = (p: string) => readFileSync(join(process.cwd(), p), "utf8");

const POSITIONS = read("src/app/(dashboard)/positions/page.tsx");
const TRADES = read("src/app/(dashboard)/trades/page.tsx");

describe("D — no customer surface calls a billed figure modelled", () => {
  it("the P&L column no longer says 'net of modelled charges'", () => {
    expect(POSITIONS).not.toContain("net of modelled charges");
    expect(POSITIONS).not.toContain("charges are our modelled estimate");
    expect(POSITIONS).not.toContain("charges are our estimate");
  });

  it("it says where the charges actually come from", () => {
    expect(POSITIONS).toContain("charges Dhan ke bill se");
  });

  it("falsification twin: the column still EXISTS and still says what it is", () => {
    // Deleting the header would pass the assertion above while removing the
    // page's whole point.
    expect(POSITIONS).toContain("Realised P&amp;L");
    expect(POSITIONS).toContain("final_pnl");
  });

  it("an unbilled row shows gross and says the charges are still coming", () => {
    expect(POSITIONS).toContain("charges baaki");
    expect(POSITIONS).toContain("derived_gross_pnl");
  });
});

describe("the legs are on the screen", () => {
  it("renders every leg of a position", () => {
    expect(POSITIONS).toContain("position-legs");
    expect(POSITIONS).toContain("p.legs.map");
  });

  it("each leg shows qty, price, IST time and the Dhan order id", () => {
    expect(POSITIONS).toContain("leg.quantity");
    expect(POSITIONS).toContain("leg.price_display");
    expect(POSITIONS).toContain("leg.filled_at_ist");
    expect(POSITIONS).toContain("leg.broker_order_id");
  });

  it("uses the BACKEND's formatted price and time, not its own", () => {
    // One number per fact. If the page re-derived either, the screen, the CSV
    // and the alert could disagree about the same fill — and the 07:41-vs-13:11
    // confusion that started R1.1 would come straight back.
    expect(POSITIONS).toContain("price_display");
    expect(POSITIONS).toContain("filled_at_ist");
    expect(POSITIONS).not.toMatch(/leg\.price\b(?!_display)/);
  });

  it("falsification twin: a leg with no fill prints a dash, never 0.00", () => {
    expect(POSITIONS).toContain('leg.price_display ?? "—"');
    expect(POSITIONS).toContain('leg.filled_at_ist ?? "—"');
  });
});

describe("R1.2 / R1.3 — the badge has three honest states", () => {
  it("shows a verified badge only for a verified row, WITH its date", () => {
    expect(POSITIONS).toContain("verify-verified");
    expect(POSITIONS).toContain("Dhan se verified");
    expect(POSITIONS).toContain("verified_on");
  });

  it("a hand-closed row reads 'manual se band', not 'verify baaki'", () => {
    expect(POSITIONS).toContain("verify-manual-closed");
    expect(POSITIONS).toContain("manual se band");
  });

  it("everything else honestly says it has not been checked", () => {
    expect(POSITIONS).toContain("verify-pending");
    expect(POSITIONS).toContain("Dhan se verify baaki");
  });

  it("falsification twin: the three states are DISTINCT, not one label reused", () => {
    const ids = ["verify-verified", "verify-manual-closed", "verify-pending"];
    expect(new Set(ids).size).toBe(3);
    for (const id of ids) expect(POSITIONS).toContain(id);
    // and the verified badge is gated on the value, not rendered unconditionally
    expect(POSITIONS).toContain('p.verification === "verified"');
    expect(POSITIONS).toContain('p.verification === "manual_closed"');
  });
});

describe("the orders page can name the engine's own stop", () => {
  it("broker_stop has a plain label instead of rendering raw", () => {
    // pine_replica's Forever order fired and CLOSED two of the four Sept round
    // trips. Without this entry the row printed the raw string "broker_stop".
    expect(TRADES).toContain("broker_stop:");
    expect(TRADES).toContain("BROKER STOP (AUTO)");
  });

  it("a manual Dhan-app order is labelled and coloured apart from the bot's", () => {
    expect(TRADES).toContain("manual_close:");
    expect(TRADES).toContain("MANUAL (DHAN APP)");
  });

  it("the engine's stop counts as an EXIT", () => {
    // Leaving it out undercounted exits by exactly the trades the engine
    // closed itself — the page would say the bot entered more than it left.
    const exits = TRADES.match(/const EXIT_ROLES = \[([\s\S]*?)\]/);
    expect(exits).toBeTruthy();
    expect(exits![1]).toContain("broker_stop");
  });

  it("falsification twin: the label map is not a catch-all", () => {
    // A map that labelled everything would pass the tests above and stop the
    // page distinguishing an entry from a stop.
    expect(TRADES).toContain("entry:");
    expect(TRADES).toContain("direct_sl:");
    expect(TRADES).toContain("LEG_ROLE_LABEL[o.legRole] ??");
  });
});
