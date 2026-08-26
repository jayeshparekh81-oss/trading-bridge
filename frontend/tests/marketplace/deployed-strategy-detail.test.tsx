/**
 * Step 6 — the two additive feed fields, where the customer actually sees them.
 *
 *   1. listing_title. The row used to render "Listing a1b2c3d4…" — a raw UUID
 *      prefix where the strategy's name belongs. Useless to a customer looking
 *      at a list of things they pay for.
 *   2. the widened open_position — side / entry / remaining / stop / target.
 *
 * And the thing that must NOT be here: any live or unrealised P&L. There is no
 * LTP behind this feed, so a P&L number would be stale or invented. Asserted,
 * not just intended.
 */

import { describe, it, expect, vi, beforeAll } from "vitest";
import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
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

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/marketplace/me",
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { id: "u1", email: "t@x.com", role: "user" } }),
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

const subsData: { current: unknown } = { current: { subscriptions: [], count: 0 } };
vi.mock("@/lib/use-api", () => ({
  useApi: (url: string | null) => ({
    data: url === "/marketplace/subscriptions/me" ? subsData.current : null,
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

import MySubscriptionsPage from "@/app/(dashboard)/marketplace/me/page";
import { PositionDetail } from "@/components/marketplace/position-detail";

const ME_PAGE = readFileSync(
  join(process.cwd(), "src/app/(dashboard)/marketplace/me/page.tsx"), "utf8");

function sub(over: Record<string, unknown> = {}) {
  return {
    id: "s1",
    listing_id: "a1b2c3d4-0000-0000-0000-000000000000",
    subscriber_id: "u1",
    subscribed_at: "2026-08-01T00:00:00Z",
    access_until: null,
    status: "active",
    amount_paid_inr: 0,
    execution_mode: "auto",
    ...over,
  };
}

function mountPage(subs: unknown[]) {
  subsData.current = { subscriptions: subs, count: subs.length };
  return render(<MySubscriptionsPage />);
}

// ═══════════════════════════════════════════════════════════════════════
// 1. The strategy has a NAME
// ═══════════════════════════════════════════════════════════════════════

describe("listing_title replaces the UUID stub", () => {
  it("renders the strategy's name", () => {
    mountPage([sub({ listing_title: "Nifty Momentum Pro" })]);
    expect(screen.getByTestId("sub-title-s1").textContent).toBe(
      "Nifty Momentum Pro",
    );
  });

  it("no longer shows the raw UUID stub when a title exists", () => {
    mountPage([sub({ listing_title: "Nifty Momentum Pro" })]);
    expect(screen.queryByText(/Listing a1b2c3d4…/)).toBeNull();
  });

  it("falls back to the id stub ONLY when the title is missing", () => {
    mountPage([sub({ listing_title: null })]);
    expect(screen.getByTestId("sub-title-s1").textContent).toContain("a1b2c3d4");
  });

  it("the fallback is not the normal case — the title is preferred in source", () => {
    expect(ME_PAGE).toContain("sub.listing_title ?? `Listing");
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 2. The widened position
// ═══════════════════════════════════════════════════════════════════════

const POS = {
  id: "p1",
  symbol: "BSE-AUG2026-FUT",
  quantity: 4,
  side: "long",
  avg_entry_price: "742.5000",
  remaining_quantity: 4,
  stop_loss_price: "730.0000",
  target_price: "770.0000",
  opened_at: "2026-08-26T04:30:00Z",
};

describe("open_position detail", () => {
  it("shows side, entry, remaining, stop and target", () => {
    render(<PositionDetail position={POS} />);
    const text = screen.getByTestId("position-detail-p1").textContent ?? "";
    expect(text).toContain("BSE-AUG2026-FUT");
    expect(text).toContain("LONG");
    expect(text).toContain("742.5000");
    expect(text).toContain("730.0000");
    expect(text).toContain("770.0000");
    expect(text).toContain("4");
  });

  it("renders prices VERBATIM — no float re-rounding", () => {
    render(<PositionDetail position={{ ...POS, avg_entry_price: "742.5000" }} />);
    const text = screen.getByTestId("position-detail-p1").textContent ?? "";
    // "742.5" would mean someone parseFloat'd money on the way to the screen
    expect(text).toContain("742.5000");
  });

  it("omits a fact rather than inventing a placeholder for it", () => {
    render(
      <PositionDetail
        position={{ id: "p1", symbol: "X", quantity: 1, side: null,
          avg_entry_price: null, stop_loss_price: null, target_price: null }}
      />,
    );
    const text = screen.getByTestId("position-detail-p1").textContent ?? "";
    expect(text).not.toMatch(/Stop|Target|Entry/);
    expect(text).not.toMatch(/undefined|null|NaN/);
    // remaining still falls back to the quantity alias
    expect(text).toContain("Remaining");
  });

  it("falls back to the quantity alias when remaining_quantity is absent", () => {
    render(<PositionDetail position={{ id: "p1", symbol: "X", quantity: 7 }} />);
    expect(screen.getByTestId("position-detail-p1").textContent).toContain("7");
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 3. NO P&L — the number we cannot source
// ═══════════════════════════════════════════════════════════════════════

describe("no unsourceable P&L", () => {
  it("the position card shows no P&L", () => {
    render(<PositionDetail position={POS} />);
    const text = screen.getByTestId("position-detail-p1").textContent ?? "";
    expect(text).not.toMatch(/P&L|PnL|Profit|Loss|Unrealised|Unrealized|%/i);
  });

  it("the page never computes one either", () => {
    const src = readFileSync(
      join(process.cwd(), "src/components/marketplace/position-detail.tsx"), "utf8");
    const code = src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
    expect(code).not.toMatch(/pnl|unrealis|unrealiz|current_price|ltp/i);
  });

  it("renders the position only when there IS one", () => {
    expect(ME_PAGE).toContain("{sub.open_position ? (");
  });
});


// ═══════════════════════════════════════════════════════════════════════
// 4. The components are actually WIRED (adversarial-review finding)
// ═══════════════════════════════════════════════════════════════════════
//
// Every other test here renders PositionDetail / ExecutionLog directly, so
// deleting them from the page would leave the whole suite green while the
// customer saw nothing. These assert the wiring itself.

describe("the components are reachable from the page", () => {
  it("renders the position card for a subscription that has one", () => {
    mountPage([
      sub({
        listing_title: "Nifty Momentum Pro",
        open_position: {
          id: "p1", symbol: "BSE-AUG2026-FUT", quantity: 2,
          side: "long", avg_entry_price: "742.5000", paper_mode: true,
        },
      }),
    ]);
    const card = screen.getByTestId("position-detail-p1");
    expect(card).toBeInTheDocument();
    // and it is LABELLED where the customer sees it, not just in isolation
    expect(card.textContent).toContain("SIMULATED");
  });

  it("shows NO position card when there is no position", () => {
    mountPage([sub({ listing_title: "X", open_position: null })]);
    expect(screen.queryByTestId(/^position-detail-/)).toBeNull();
  });

  it("mounts the execution log inside the expanded Deploy panel", () => {
    expect(ME_PAGE).toContain("<ExecutionLog");
    expect(ME_PAGE).toContain("subscriptionId={sub.id}");
    // lazily — enabled is tied to the expand, not always true
    expect(ME_PAGE).toContain("enabled={open}");
  });

  it("imports both components rather than re-implementing them", () => {
    expect(ME_PAGE).toContain(
      'from "@/components/marketplace/execution-log"');
    expect(ME_PAGE).toContain(
      'from "@/components/marketplace/position-detail"');
  });

  it("timestamps carry the year — rows a year apart must differ", () => {
    render(
      <PositionDetail
        position={{ ...POS, opened_at: "2025-08-26T04:30:00Z" }} />);
    const a = screen.getByTestId("position-detail-p1").textContent ?? "";
    expect(a).toMatch(/25/);
  });
});
