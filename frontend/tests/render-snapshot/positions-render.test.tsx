/**
 * R4 — produce the local render the founder asked to see.
 *
 * Mounts the REAL /positions page with the REAL 1..16 Sep record and writes
 * the resulting HTML to disk. Not a mock of the page: the same component the
 * browser runs, so what is in the file is what the customer would see.
 *
 * The numbers are the measured ones — gross fill-sourced, charges from Dhan's
 * own bill, net = gross - billed. TOTAL NET is 77,486.42 (addition E), and
 * that total is produced by the page's own arithmetic here, not typed in.
 *
 * Run: npx vitest run tests/render-snapshot
 * Output: tests/render-snapshot/positions.html
 */

import { describe, it, expect, vi, beforeAll, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { writeFileSync } from "node:fs";
import { join } from "node:path";

beforeAll(() => {
  if (!("IntersectionObserver" in globalThis)) {
    class IO {
      observe() {} unobserve() {} disconnect() {}
      takeRecords() { return []; }
      root = null; rootMargin = ""; thresholds = [];
    }
    (globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = IO;
  }
});

vi.mock("@/hooks/useSystemMode", () => ({
  useSystemMode: () => ({
    paper_mode: false, kill_switch_check_enabled: true, circuit_breaker_enabled: true,
  }),
}));
const apiData = vi.hoisted(() => ({ current: {} as Record<string, unknown> }));
vi.mock("@/shared/api/use-api", () => ({
  useApi: (url: string | null) => {
    const key = url === null ? "__null__"
      : Object.keys(apiData.current).sort((a, b) => b.length - a.length)
          .find((k) => url === k || url.startsWith(k)) ?? "__miss__";
    return {
      data: apiData.current[key] ?? null, isLoading: false, error: null,
      paywalled: false, paywallUrl: null, refetch: vi.fn(),
    };
  },
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/positions",
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { id: "u1", email: "founder@tradetri.com", role: "user" } }),
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

import PositionsPage from "@/app/(dashboard)/positions/page";

const S = "89423ecc-c76e-432c-b107-0791508542f0";
const leg = (
  role: string, label: string, side: string, qty: number,
  price: string | null, order: string, ist: string,
) => ({
  leg_role: role, label, side, quantity: qty,
  price, price_display: price, broker_order_id: order,
  filled_at_ist: ist, broker_fill: true,
});

/** The real record. Every figure is a Dhan fill or Dhan's own billed charge. */
const POSITIONS = [
  {
    id: "844b8037-f192-40f8-88ce-09b091030c17", strategy_id: S,
    symbol: "BSE-SEP2026-FUT", side: "buy",
    total_quantity: 800, remaining_quantity: 0,
    avg_entry_price: "3270.0000", target_price: null, stop_loss_price: null,
    highest_price_seen: null, status: "closed",
    opened_at: "2026-09-03T04:15:17Z", closed_at: "2026-09-04T07:41:13Z",
    final_pnl: "78057.7216", pnl_attribution: "bot_only", legs_balanced: true,
    derived_gross_pnl: "80360.00", derived_realised_charges: "2302.2784",
    verification: "verified", verified_on: "2026-09-04",
    legs: [
      leg("entry", "entry", "buy", 800, "3270.00", "32226090368506", "03/09/26, 09:45 am"),
      leg("direct_partial", "partial exit", "sell", 400, "3325.40", "34226090334306", "03/09/26, 12:45 pm"),
      leg("broker_stop", "broker stop (auto)", "sell", 400, "3415.50", "312260904412406", "04/09/26, 01:11 pm"),
    ],
    duplicate_exit: {
      broker_order_id: "23226090443106", side: "sell", qty: 400, price: "3415.80",
      gross_pnl: "-4360.00", billed_charges: "133.1296", net_pnl: "-4493.1296",
      label: "system galti: duplicate exit",
      reason: "The platform SL fired 4 minutes after the engine's stop had already taken the position to zero, opening a short 400 from flat. Closed by two manual BUY 200 @3426.70.",
    },
  },
  {
    id: "a13ddeb0-d875-474b-b40e-eb1facb36970", strategy_id: S,
    symbol: "BSE-SEP2026-FUT", side: "buy",
    total_quantity: 800, remaining_quantity: 0,
    avg_entry_price: "3470.3000", target_price: null, stop_loss_price: null,
    highest_price_seen: null, status: "closed",
    opened_at: "2026-09-07T05:00:21Z", closed_at: "2026-09-08T04:12:32Z",
    final_pnl: "-63622.9570", pnl_attribution: "bot_only", legs_balanced: true,
    derived_gross_pnl: "-61020.00", derived_realised_charges: "2602.9570",
    verification: "verified", verified_on: "2026-09-08",
    legs: [
      leg("entry", "entry", "buy", 800, "3470.30", "322260907150406", "07/09/26, 10:30 am"),
      leg("broker_stop", "broker stop (auto)", "sell", 800, "3394.03", "312260908126806", "08/09/26, 09:42 am"),
    ],
  },
  {
    id: "d0086394-e66b-4b49-b557-7c337df777ac", strategy_id: S,
    symbol: "BSE-SEP2026-FUT", side: "sell",
    total_quantity: 400, remaining_quantity: 0,
    avg_entry_price: "3393.1500", target_price: null, stop_loss_price: null,
    highest_price_seen: null, status: "closed",
    opened_at: "2026-09-08T08:30:10Z", closed_at: "2026-09-11T04:01:17Z",
    final_pnl: null, pnl_attribution: "human_interfered", legs_balanced: false,
    incomplete_reason:
      "200 manual Dhan-app order se band (35226091145606, BUY 200 @3215.4, 11-09 09:31) — is trade ka P&L nahi gina",
    verification: "manual_closed", verified_on: null,
    legs: [
      leg("entry", "entry", "sell", 400, "3393.15", "34226090862006", "08/09/26, 02:00 pm"),
      leg("direct_partial", "partial exit", "buy", 200, "3310.40", "32226090941906", "09/09/26, 09:30 am"),
      { ...leg("manual_close", "manual close (Dhan app)", "buy", 200, null, "35226091145606", "11/09/26, 09:31 am"), price_display: null },
    ],
  },
  {
    id: "9165ebbe-0000-0000-0000-000000000000", strategy_id: S,
    symbol: "BSE-SEP2026-FUT", side: "buy",
    total_quantity: 800, remaining_quantity: 0,
    avg_entry_price: "3305.2000", target_price: null, stop_loss_price: null,
    highest_price_seen: null, status: "closed",
    opened_at: "2026-09-11T09:15:14Z", closed_at: "2026-09-15T04:15:10Z",
    final_pnl: "67544.7828", pnl_attribution: "bot_only", legs_balanced: true,
    derived_gross_pnl: "69160.00", derived_realised_charges: "1615.2172",
    verification: "verified", verified_on: "2026-09-15",
    legs: [
      leg("entry", "entry", "buy", 800, "3305.20", "23226091175306", "11/09/26, 02:45 pm"),
      leg("direct_partial", "partial exit", "sell", 400, "3404.05", "23226091180006", "11/09/26, 03:15 pm"),
      leg("direct_sl", "SL / trailing exit", "sell", 400, "3379.25", "222260915111506", "15/09/26, 09:45 am"),
    ],
  },
  {
    id: "6c0b2196-0000-0000-0000-000000000000", strategy_id: S,
    symbol: "BSE-SEP2026-FUT", side: "sell",
    total_quantity: 400, remaining_quantity: 400,
    avg_entry_price: "3251.5500", target_price: null, stop_loss_price: null,
    broker_stop_price: null, highest_price_seen: null, status: "open",
    opened_at: "2026-09-16T04:45:11Z", closed_at: null,
    final_pnl: null, pnl_attribution: null, legs_balanced: true,
    verification: "pending", verified_on: null,
    legs: [
      leg("entry", "entry", "sell", 400, "3251.55", "34226091617106", "16/09/26, 10:15 am"),
    ],
  },
];

afterEach(() => cleanup());

describe("the founder's local render", () => {
  it("writes positions.html and the totals are the measured ones", () => {
    apiData.current = {
      "/strategies": {
        strategies: [{ id: S, name: "BSE LTD Futures", is_paper: false }],
        count: 1,
      },
      "/strategies/positions": { positions: POSITIONS, count: POSITIONS.length },
    };
    const { container } = render(<PositionsPage />);

    // ── the totals are the page's OWN arithmetic, not typed in ──────
    const gross = screen.getByTestId("total-gross").textContent ?? "";
    const net = screen.getByTestId("total-net").textContent ?? "";
    // 80,360 - 61,020 + 69,160 - 4,360 = 84,140
    expect(gross).toMatch(/84,140/);
    // 77,486.42 — addition E, to the rupee on screen
    expect(net).toMatch(/77,486/);

    // every position's legs rendered
    expect(screen.getAllByTestId("position-legs").length).toBe(5);
    // the engine's own stop, the manual close, and the duplicate exit
    const body = container.textContent ?? "";
    expect(body).toContain("broker stop (auto)");
    expect(body).toContain("manual close (Dhan app)");
    expect(body).toContain("system galti: duplicate exit");
    expect(body).toContain("manual se band");
    expect(body).toContain("Dhan se verified");

    const html = `<!doctype html>
<meta charset="utf-8">
<title>TRADETRI /positions — local render, BSE LTD Futures</title>
<style>
  body { background:#0b0f15; color:#e6edf3; font-family: ui-sans-serif, system-ui, sans-serif; margin:0; padding:24px; }
  table { border-collapse: collapse; width:100%; }
  th, td { padding:8px 10px; font-size:13px; text-align:left; }
  thead th { text-transform:uppercase; font-size:11px; color:#8b98a5; border-bottom:1px solid #223; }
  tbody tr { border-top:1px solid rgba(255,255,255,.06); }
  tfoot { border-top:2px solid rgba(255,255,255,.15); }
  .text-profit { color:#3fb950 } .text-loss { color:#f85149 }
  .tabular-nums { font-variant-numeric: tabular-nums }
  .font-mono { font-family: ui-monospace, monospace }
  [data-testid="position-legs"] { background: rgba(255,255,255,.02) }
</style>
<p style="color:#8b98a5;font-size:12px">
  Local render from the R4 component with the measured 1..16 Sep record.
  Charges are Dhan's own billed figures. Not a screenshot of production.
</p>
${container.innerHTML}
`;
    const out = join(process.cwd(), "tests/render-snapshot/positions.html");
    writeFileSync(out, html, "utf8");
    expect(html.length).toBeGreaterThan(2000);
  });
});
