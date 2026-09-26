/**
 * THE PHONE LAYOUT of /positions (founder's rule, 26 Sep 2026, point 7: "nothing cut
 * off at 375px"). On a phone-width screen the 13-column table is replaced by stacked
 * cards drawn by the SAME cell components — so the words and numbers are identical,
 * only the arrangement changes. Where the width is unknown (server render, no
 * matchMedia) the table stays: never a guess.
 */

import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

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
    paper_mode: false,
    kill_switch_check_enabled: true,
    circuit_breaker_enabled: true,
  }),
}));

const apiData = vi.hoisted(() => ({ current: {} as Record<string, unknown> }));
vi.mock("@/shared/api/use-api", () => ({
  useApi: (url: string | null) => {
    const key =
      url === null
        ? "__null__"
        : Object.keys(apiData.current)
            .sort((a, b) => b.length - a.length)
            .find((k) => url === k || url.startsWith(k)) ?? "__miss__";
    return {
      data: apiData.current[key] ?? null,
      isLoading: false,
      error: null,
      paywalled: false,
      paywallUrl: null,
      refetch: vi.fn(),
    };
  },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/positions",
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { id: "u1", email: "t@x.com", role: "user" } }),
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

import PositionsPage from "@/app/(dashboard)/positions/page";

const LIVE_STRATEGY = "89423ecc-c76e-432c-b107-0791508542f0";
const STRATEGIES = {
  strategies: [{ id: LIVE_STRATEGY, name: "BSE LTD Futures", is_paper: false }],
  count: 1,
};

/** The founder's two closed post-cut positions, and the open half of a third. */
const CLOSED_AT = "2026-09-08T09:59:07Z";
function position(over: Record<string, unknown> = {}) {
  return {
    id: "844b8037-0000-0000-0000-000000000001",
    strategy_id: LIVE_STRATEGY,
    symbol: "BSE-SEP2026-FUT",
    side: "buy",
    total_quantity: 800,
    remaining_quantity: 0,
    avg_entry_price: "3470.15",
    target_price: null,
    stop_loss_price: null,
    highest_price_seen: null,
    status: "closed",
    opened_at: "2026-09-07T09:34:06Z",
    closed_at: CLOSED_AT,
    final_pnl: "-12500.25",
    ...over,
  };
}

beforeEach(() => {
  apiData.current = {
    "/strategies/positions": { positions: [position()], count: 1 },
    "/strategies": STRATEGIES,
  };
});
afterEach(cleanup);


function setPhone(matches: boolean) {
  window.matchMedia = ((q: string) => ({
    matches, media: q, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

describe("positions on a phone", () => {
  it("a phone gets cards, not the wide table — with the same words", async () => {
    setPhone(true);
    apiData.current["/strategies/positions"] = { positions: [position(), position({ id: "b", status: "open", remaining_quantity: 400, closed_at: null, final_pnl: null })], count: 2 };
    render(<PositionsPage />);
    const cards = await screen.findAllByTestId("position-card");
    expect(cards.length).toBe(2);
    expect(screen.queryByRole("table")).toBeNull();
    expect(cards[0].textContent).toMatch(/Kharida/);
    expect(cards[0].textContent).toMatch(/Entry daam/);
    expect(cards[1].textContent).toMatch(/band hone par aayega/); // an open row's P&L: words, never a dash or 0
    expect(cards[0].textContent).not.toMatch(/—/);
  });

  it("a wide screen keeps the table (and the falsification twin: the cards really are phone-only)", () => {
    setPhone(false);
    render(<PositionsPage />);
    expect(screen.getByRole("table")).toBeTruthy();
    expect(screen.queryByTestId("positions-cards")).toBeNull();
  });
});
