/**
 * Founder decision (2026-09-04): no surface may promise a blockchain that is
 * not built. The ledger is an off-chain, hash-linked (prior_hash) append-only
 * record, empty until the first snapshot. Founder-held files are excluded:
 * lib/compliance/disclaimer-text.ts, (public)/sebi, (dashboard)/compliance/legal.
 */

import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const HELD = [/lib\/compliance\/disclaimer-text\.ts$/, /\(public\)\/sebi\//, /\(dashboard\)\/compliance\/legal\//];
const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
function walk(dir: string, acc: string[] = []): string[] {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) walk(p, acc);
    else if (/\.(tsx?)$/.test(e.name)) acc.push(p);
  }
  return acc;
}
const files = walk(join(process.cwd(), "src")).filter((f) => !HELD.some((h) => h.test(f)));

describe("no on-chain promise outside founder-held legal text", () => {
  it.each([
    [/on-chain hash/i], [/anchored on-chain/i], [/immutable (on-chain|ledger|record|hash)/i], [/tamper-proof/i], [/polygon/i], [/chain not yet live/i],
    [/public blockchain (is|pe commit karna)/i], [/blockchain[^.\n]{0,40}(later|baad ka) phase/i],
  ])("%s appears in no rendered copy", (re) => {
    const hits = files.filter((f) => re.test(strip(readFileSync(f, "utf8"))));
    expect(hits).toEqual([]);
  });
  it("the hardcoded '0 trades reconciled' banner literal is gone", () => {
    const page = readFileSync(join(process.cwd(), "src/app/(public)/showcase/page.tsx"), "utf8");
    expect(page).not.toMatch(/0 trades reconciled/);
    expect(page).toMatch(/No ledger snapshots have been published yet/);
  });
  it("showcase and the ledger panel state what is true: off-chain, hash-linked, tamper-evident, empty until the first snapshot", () => {
    const page = strip(readFileSync(join(process.cwd(), "src/app/(public)/showcase/page.tsx"), "utf8"));
    expect(page).toMatch(/off-chain/);
    expect(page).toMatch(/tamper-evident/);
    expect(page).toMatch(/previous snapshot's hash|pichhle snapshot ke hash/);
    expect(page).toMatch(/no snapshots yet/i);
    const panel = strip(readFileSync(join(process.cwd(), "src/components/marketplace/transparency-ledger-panel.tsx"), "utf8"));
    expect(panel).toMatch(/Off-chain · hash-linked/);
    expect(panel).not.toMatch(/Phase 2 \(off-chain\)/);
  });
  it("only a 'tracking_active' status claims live tracking", () => {
    const page = readFileSync(join(process.cwd(), "src/app/(public)/showcase/page.tsx"), "utf8");
    expect(page).toMatch(/live\.status === "tracking_active"\)\s*return \{ em: "Live tracking active\."/);
  });
});
