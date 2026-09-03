/**
 * The Export CSV button on /trades — the control that makes "CSV Export" a
 * real plan feature instead of a ✗.
 *
 * WHY THE ENDPOINT MATTERS MORE THAN THE BUTTON. `/users/me/trades/export`
 * already existed and streams CSV — of the legacy `trades` table, which the
 * strategy engine never writes (0 rows on prod against 107
 * `strategy_executions`). A button wired there would download a header-only
 * file for every customer: a hollow feature dressed as a real one. The button
 * MUST hit `/strategies/executions/export`, the CSV of what this page shows.
 *
 * Also locked: it never renders behind the paywall (the endpoint is gated
 * identically, so it would only 402), and it is disabled with no rows (an
 * empty file is not a feature).
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const apiState: {
  current: {
    data: unknown;
    isLoading: boolean;
    error: string | null;
    refetch: () => void;
    paywalled: boolean;
    paywallUrl: string | null;
  };
} = {
  current: {
    data: null, isLoading: false, error: null, refetch: vi.fn(),
    paywalled: false, paywallUrl: null,
  },
};
vi.mock("@/lib/use-api", () => ({ useApi: () => apiState.current }));

// vi.mock factories are hoisted above every `const` in this file, so anything
// they close over must be created with vi.hoisted() or it is read before init.
const { download, toast } = vi.hoisted(() => ({
  download: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
}));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, download } };
});
vi.mock("sonner", () => ({ toast }));

// Render each motion.<tag> as the plain <tag> (GlowButton is motion.button —
// a <div> stand-in would swallow `disabled`) and drop animation props.
vi.mock("framer-motion", async () => {
  const React = await vi.importActual<typeof import("react")>("react");
  return {
    motion: new Proxy({}, {
      get: (_t, tag: string) =>
        ({ children, ...rest }: { children?: React.ReactNode } & Record<string, unknown>) => {
          const { variants: _v, initial: _i, animate: _a, whileHover: _w, whileTap: _p, ...dom } = rest;
          return React.createElement(tag, dom, children);
        },
    }),
  };
});

import TradesPage from "@/app/(dashboard)/trades/page";

const ROW = {
  id: "e1", signal_id: "s1", leg_number: 1, leg_role: "entry", symbol: "BSE-FUT",
  side: "BUY", quantity: 4, order_type: "market", price: "2400.5",
  broker_order_id: "DH-1", broker_status: "TRADED", error_code: null,
  error_message: null, placed_at: "2026-09-01T04:00:00Z", completed_at: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  apiState.current = {
    data: { executions: [ROW], count: 1 }, isLoading: false, error: null,
    refetch: vi.fn(), paywalled: false, paywallUrl: null,
  };
});

describe("Export CSV on /trades", () => {
  it("🔴 downloads the EXECUTIONS csv, not the empty legacy trades one", async () => {
    download.mockResolvedValue(1234);
    render(<TradesPage />);
    fireEvent.click(screen.getByTestId("export-csv"));
    await waitFor(() => expect(download).toHaveBeenCalledTimes(1));
    const [endpoint, filename] = download.mock.calls[0];
    expect(endpoint).toBe("/strategies/executions/export");
    expect(endpoint).not.toContain("/users/me/trades");
    expect(filename).toBe("tradetri-executions.csv");
    expect(toast.success).toHaveBeenCalled();
  });

  it("surfaces the API's message on failure instead of failing silently", async () => {
    const { ApiError } = await import("@/lib/api");
    download.mockRejectedValue(new ApiError(402, "Plan required"));
    render(<TradesPage />);
    fireEvent.click(screen.getByTestId("export-csv"));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Plan required"));
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("is disabled with zero rows — an empty file is not a feature", () => {
    apiState.current = { ...apiState.current, data: { executions: [], count: 0 } };
    render(<TradesPage />);
    expect(screen.getByTestId("export-csv")).toBeDisabled();
  });

  it("is disabled while the list is still loading", () => {
    apiState.current = { ...apiState.current, data: null, isLoading: true };
    render(<TradesPage />);
    expect(screen.getByTestId("export-csv")).toBeDisabled();
  });

  it("🔴 does not render behind the paywall at all", () => {
    apiState.current = {
      ...apiState.current, data: null, paywalled: true, paywallUrl: "/pricing",
    };
    render(<TradesPage />);
    expect(screen.queryByTestId("export-csv")).toBeNull();
  });
});

describe("the claim is tied to the control", () => {
  it("AlgoMitra's export answer names a button that actually exists", () => {
    const page = readFileSync(
      join(process.cwd(), "src/app/(dashboard)/trades/page.tsx"), "utf8");
    const faq = readFileSync(
      join(process.cwd(), "src/lib/algomitra-faqs.ts"), "utf8");
    // The control:
    expect(page).toContain('data-testid="export-csv"');
    expect(page).toContain("Export CSV");
    // The claim about it — must say the button exists, not that it doesn't.
    const i = faq.indexOf('id: "trade-export"');
    const answer = faq.slice(i, i + 900);
    expect(answer).toMatch(/Export CSV/);
    expect(answer).not.toMatch(/koi Export button nahi hai/);
  });
});
