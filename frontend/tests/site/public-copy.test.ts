/**
 * ONE SITE — item 5: PUBLIC COPY = APP TRUTH.
 *
 * Every public claim was audited against the real routes (2026-09-06). The
 * ones that were false are pinned here so they cannot creep back, and the
 * "3 simple steps" on the home page must be the SAME three steps Simple mode
 * shows a new customer (lib/simple/copy.ts).
 */
import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { t } from "@/lib/simple/copy";

const root = process.cwd();
function walk(dir: string, out: string[] = []): string[] {
  for (const f of readdirSync(dir)) {
    const p = join(dir, f);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(tsx?|jsx?)$/.test(f)) out.push(p);
  }
  return out;
}
const PUBLIC_TREE = [
  ...walk(join(root, "src/app/(public)")).filter((p) => !p.includes("/dev-preview/")),
  ...walk(join(root, "src/components/marketing")),
  ...walk(join(root, "src/components/brand")),
  join(root, "src/app/layout.tsx"),
  join(root, "src/lib/compliance/disclaimer-text.ts"),
];
const src = (p: string) => readFileSync(p, "utf8");
const home = src(join(root, "src/app/(public)/home/page.tsx"));

// Claims the audit found false, with what the app actually does.
const FORBIDDEN: [RegExp, string][] = [
  [/one-click deploy/i, "there is no deploy step: build + backtest + paper-test"],
  [/slippage and latency/i, "slippage/latency are not shown on the customer's trades"],
  [/AES-256/, "credentials use Fernet (AES-128-CBC + HMAC); say 'encrypted at rest'"],
  [/HMAC-signed webhooks/i, "HMAC on webhooks is optional; say 'token-authenticated, optional HMAC'"],
  [/Never lose more than you set/i, "a market-order square-off cannot promise an exact number"],
  [/verified Track Record/i, "the live record is in verification, nothing is verified yet"],
  [/Set up in 3 minutes/i, "no backing for a time promise"],
  [/take effect immediately/i, "plan changes start next billing cycle (billing.py change_plan)"],
  [/"Telegram Alerts"/, "Telegram transport is off (telegram_enabled=False)"],
  [/AI-Powered/i, "the conviction score is rule-based, not deep learning"],
  [/act\s+karne\s+se\s+pehle/i, "Hinglish form of 'before it acts' — own webhooks have no approval step"],
  [/July 2026|June 9, 2026|August 2026/, "stale dates — no dates are promised"],
  [/\b6\b[^\n]{0,40}Broker integrations|value: 6, label: "Broker integrations"/, "2 brokers are live (Dhan, Fyers); 4 are stubs"],
];

describe("public copy carries no promise the app does not keep", () => {
  for (const [re, why] of FORBIDDEN) {
    it(`never says ${re} — ${why}`, () => {
      for (const p of PUBLIC_TREE) {
        const text = src(p).replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
        expect(text, p.replace(root, "")).not.toMatch(re);
      }
    });
  }

  it('"you approve it" is not claimed for the customer\'s own webhooks (approval is manual-mode subscriptions only)', () => {
    for (const p of ["src/app/(public)/home/page.tsx", "src/app/(public)/about/page.tsx", "src/app/(public)/showcase/page.tsx"]) {
      expect(src(join(root, p)), p).not.toMatch(/before it acts|you approve it/i);
    }
  });

  it("the broker strip lists only the brokers that are live, and marks the rest coming soon", () => {
    expect(home).toContain('["Dhan", "Fyers"]');
    expect(home).toMatch(/Zerodha, Upstox, AngelOne, Shoonya: coming soon/);
  });
});

describe('"Start in 3 simple steps" = the real Simple-mode steps', () => {
  it("home shows Bhasha chuno → Broker jodo → Strategy chuno, in that order", () => {
    const titles = ["ob_step_lang", "ob_step_broker", "ob_step_strategy"].map((k) => t("hinglish", k as Parameters<typeof t>[1]));
    expect(titles).toEqual(["Bhasha chuno", "Broker jodo", "Strategy chuno"]);
    const idx = titles.map((title) => home.indexOf(`title: "${title}"`));
    expect(idx.every((i) => i > 0)).toBe(true);
    expect(idx).toEqual([...idx].sort((a, b) => a - b));
    expect(home).not.toMatch(/title: "Connect"|title: "Set up"|title: "Trade"/);
  });

  it("the builder claim says build + backtest + paper-test", () => {
    expect(home).toMatch(/Build, backtest and paper-test/);
  });
});
