/**
 * Cutover-26 (2026-09-04): a NULL P&L must be EXPLAINED, never silent.
 *
 * The founder's exit rule leaves `final_pnl` NULL where the founder's own
 * manual fills on the same contract make the bot's exit a guess, and tags the
 * record "human-interfered — not attributable". Every surface that shows a
 * realised P&L must render that tag when the API sends it.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const read = (p: string) => readFileSync(join(process.cwd(), p), "utf8");
const LABEL = "human-interfered — not attributable";

describe("human-interfered tag renders wherever a P&L can be NULL", () => {
  it("positions table: the label wins for human_interfered; a value renders otherwise; other nulls keep the dash", () => {
    const lib = read("src/lib/pnl-attribution.ts");
    expect(lib).toContain(`export const HUMAN_INTERFERED_LABEL = "${LABEL}"`);
    const src = read("src/app/(dashboard)/positions/page.tsx");
    // no page-level named export (Next's page validator), the constant lives in lib
    expect(src).not.toMatch(/^export const /m);
    expect(src).toMatch(/from "@\/lib\/pnl-attribution"/);
    expect(src).toMatch(/pnl_attribution\?: PnlAttribution \| string \| null/);
    expect(src).toMatch(/data-testid="pnl-human-interfered"/);
    // the detail (order ids / reason) is the tooltip, so the tag is auditable in place
    expect(src).toMatch(/title=\{p\.pnl_attribution_detail \?\? HUMAN_INTERFERED_FALLBACK_DETAIL\}/);
    // ORDER of the ternary: tag check first, then the value, then the dash — so a
    // stale number on a human-interfered row can never read as a P&L.
    const cell = src.slice(src.indexOf('data-testid="pnl-human-interfered"') - 400);
    const tagIdx = cell.indexOf('p.pnl_attribution === "human_interfered" ? (');
    const valueIdx = cell.indexOf("p.final_pnl !== null && p.final_pnl !== undefined ? (");
    const dashIdx = cell.indexOf('<span className="text-muted-foreground">—</span>');
    expect(tagIdx).toBeGreaterThan(-1);
    expect(valueIdx).toBeGreaterThan(tagIdx);
    expect(dashIdx).toBeGreaterThan(valueIdx);
    // an `unpriceable` row (paper / phantom / rejected — never a trade) says so, muted, with the detail as tooltip
    const unpriceableIdx = cell.indexOf('p.pnl_attribution === "unpriceable" ? (');
    expect(unpriceableIdx).toBeGreaterThan(valueIdx);
    expect(dashIdx).toBeGreaterThan(unpriceableIdx);
    expect(src).toMatch(/data-testid="pnl-unpriceable"/);
    expect(src).toMatch(/title=\{p\.pnl_attribution_detail \?\? UNPRICEABLE_FALLBACK_DETAIL\}/);
  });

  it("transparency ledger panel: the chained human-interfered count is spelled out", () => {
    const src = read("src/components/marketplace/transparency-ledger-panel.tsx");
    expect(src).toMatch(/human_interfered_positions\?: number \| null/);
    expect(src).toMatch(/data-testid="ledger-human-interfered"/);
    expect(src).toContain("human-interfered — not attributable");
    expect(src).toContain("records nothing rather than a wrong number");
    // never rendered when the count is absent or zero
    expect(src).toMatch(
      /typeof snapshot\.human_interfered_positions === "number" && snapshot\.human_interfered_positions > 0/,
    );
  });

  it("showcase card: the live line explains excluded trades and never invents P&L", () => {
    const page = read("src/app/(public)/showcase/page.tsx");
    const types = read("src/lib/showcase/data.ts");
    expect(types).toMatch(/human_interfered_trades\?: number/);
    expect(page).toContain("human-interfered — not attributable: excluded by rule, not zeroed.");
    expect(page).toMatch(/typeof live\.human_interfered_trades === "number" && live\.human_interfered_trades > 0/);
    // still no rupee figure on the showcase live line
    expect(page).not.toMatch(/₹\$\{live\./);
  });
});
