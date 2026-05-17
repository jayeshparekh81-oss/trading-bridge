/**
 * Strategy detail page — cloned-from-template UX fix (Task 4 Resolution).
 *
 * The detail page at /strategies/{id} reads template_origin from
 * GET /api/strategies/{id}. When populated, the page must:
 *
 *   1. Suppress the "Phase 5 builder se pehle bani thi" legacy warning.
 *   2. Render a "Template-cloned strategy" info banner with the
 *      Phase-5-availability message.
 *   3. Render a "Cloned from template" badge with the template's
 *      name + category + complexity.
 *   4. Render the Template defaults preview (SL/TP/trading hours/sizing).
 *   5. Replace the disabled "Backtest unavailable (no DSL)" CTA with
 *      "Available with Strategy Builder".
 *   6. Count indicators from template_origin.config_json (not the null
 *      strategy_json).
 *
 * When template_origin is null AND strategy_json is null, the legacy
 * warning DOES still render — the genuine pre-Phase-5 legacy case.
 *
 * When strategy_json is present (hand-built strategy), neither the
 * legacy warning nor the clone badge renders — original UX intact.
 *
 * Pre-existing tests in this directory are not modified.
 */

import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

// ── Mocks ─────────────────────────────────────────────────────────────

const mockUseApi = vi.hoisted(() => vi.fn());
vi.mock("@/lib/use-api", () => ({
  useApi: mockUseApi,
}));

// next/link — render as a plain anchor so we can spot the View Backtest URL.
vi.mock("next/link", () => ({
  __esModule: true,
  default: ({
    href,
    children,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
    className?: string;
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

// framer-motion — pass-through so the page renders synchronously.
vi.mock("framer-motion", () => ({
  motion: {
    div: ({
      children,
      ...rest
    }: {
      children: React.ReactNode;
      [k: string]: unknown;
    }) => <div {...rest}>{children}</div>,
  },
}));

// Heavy panels — replaced with stubs so the test focuses on the
// audit-relevant DetailBody region. None of these interact with the
// template-origin branching.
vi.mock("@/components/strategies/version-history-panel", () => ({
  VersionHistoryPanel: () => <div data-testid="stub-version-history" />,
}));
vi.mock("@/components/strategies/strategy-actions-menu", () => ({
  StrategyActionsMenu: () => <div data-testid="stub-actions-menu" />,
}));
vi.mock("@/components/strategies/trust-score-badge", () => ({
  TrustScoreBadge: () => <div data-testid="stub-trust-score" />,
}));
vi.mock("@/components/strategies/safety-pre-flight-panel", () => ({
  SafetyPreFlightPanel: () => <div data-testid="stub-safety-preflight" />,
}));
vi.mock("@/components/strategies/go-live-button", () => ({
  GoLiveButton: () => <button data-testid="stub-go-live" />,
}));
vi.mock("@/components/strategies/go-live-modal", () => ({
  GoLiveModal: () => null,
}));
vi.mock("@/components/strategies/order-result-card", () => ({
  OrderResultCard: () => null,
}));

// ── Page import (after mocks) ─────────────────────────────────────────

import StrategyDetailPage from "@/app/(dashboard)/strategies/[id]/page";

// ── Fixtures ──────────────────────────────────────────────────────────

const baseStrategyRow = {
  id: "11111111-2222-3333-4444-555555555555",
  name: "Parabolic SAR Reversal (from template)",
  is_active: true,
  created_at: "2026-05-17T18:00:00Z",
  updated_at: "2026-05-17T18:00:00Z",
};

const cloneTemplateOrigin = {
  template_slug: "parabolic-sar-reversal",
  template_name: "Parabolic SAR Reversal",
  template_category: "Trend Following",
  template_complexity: "beginner",
  cloned_at: "2026-05-17T18:00:00Z",
  config_json: {
    indicators: ["parabolic_sar"],
    entry_long: { condition: "parabolic_sar flips below close" },
    exit_long: { condition: "parabolic_sar flips above close" },
    stop_loss_pct: 1.5,
    take_profit_pct: 3.5,
    position_sizing: { method: "fixed_amount", amount_inr: 30000 },
    max_open_positions: 1,
    trading_hours: { start: "09:15", end: "15:15" },
  },
};

// Pages in this codebase use `React.use(params)`. React 19's `use()`
// short-circuits on a thenable that exposes a `status === "fulfilled"`
// + `value` field (the same shape React itself caches on the thenable).
// Building one synchronously avoids React having to suspend the render
// and wait for a microtask flush — which jsdom doesn't reliably pump
// across vitest's render boundary.
function syncResolvedThenable<T>(value: T): PromiseLike<T> & {
  status: "fulfilled";
  value: T;
} {
  const t: PromiseLike<T> & { status: "fulfilled"; value: T } = {
    status: "fulfilled",
    value,
    then: (resolve) => {
      if (resolve) resolve(value);
      return t as unknown as PromiseLike<unknown>;
    },
  };
  return t;
}

const params = syncResolvedThenable({ id: baseStrategyRow.id });

beforeEach(() => {
  mockUseApi.mockReset();
});

// ── Test cases ────────────────────────────────────────────────────────

describe("Strategy detail — cloned-from-template (Task 4 Resolution)", () => {
  it("template_origin populated → shows template banner + clone badge + preview + 'Available with Strategy Builder' CTA, NO legacy warning", async () => {
    mockUseApi.mockReturnValue({
      data: {
        ...baseStrategyRow,
        strategy_json: null,
        template_origin: cloneTemplateOrigin,
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<StrategyDetailPage params={params} />);

    // (1) The "Template-cloned strategy" banner with the Phase-5 message.
    //     Async wait because the page uses React.use(params) which suspends.
    await waitFor(() => {
      expect(
        screen.getByText(/Template-cloned strategy/i),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText(/Strategy Builder \(Phase 5\)/i),
    ).toBeInTheDocument();

    // (2) The clone badge with template metadata.
    expect(screen.getByText(/Cloned from template/i)).toBeInTheDocument();
    expect(
      screen.getByText(cloneTemplateOrigin.template_name),
    ).toBeInTheDocument();
    expect(
      screen.getByText(cloneTemplateOrigin.template_category),
    ).toBeInTheDocument();

    // (3) Template defaults preview is rendered.
    expect(screen.getByText(/Template defaults/i)).toBeInTheDocument();
    expect(screen.getByText(/1.5%/)).toBeInTheDocument(); // SL
    expect(screen.getByText(/3.5%/)).toBeInTheDocument(); // TP
    expect(screen.getByText(/09:15.*15:15/)).toBeInTheDocument();

    // (4) Indicator chip rendered from template_origin.config_json.
    expect(screen.getByText("parabolic_sar")).toBeInTheDocument();

    // (5) The legacy warning is NOT rendered.
    expect(
      screen.queryByText(/Phase 5 builder se pehle bani thi/i),
    ).not.toBeInTheDocument();

    // (6) CTA: the new "Available with Strategy Builder" button.
    expect(
      screen.getByText(/Available with Strategy Builder/i),
    ).toBeInTheDocument();
    // (6b) The old disabled-no-DSL copy is NOT used.
    expect(
      screen.queryByText(/Backtest unavailable \(no DSL\)/i),
    ).not.toBeInTheDocument();
  });

  it("template_origin null + strategy_json null → legacy warning DOES render (genuine pre-Phase-5 row)", async () => {
    mockUseApi.mockReturnValue({
      data: {
        ...baseStrategyRow,
        name: "Old legacy strategy",
        strategy_json: null,
        template_origin: null,
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<StrategyDetailPage params={params} />);

    await waitFor(() => {
      expect(
        screen.getByText(/Phase 5 builder se pehle bani thi/i),
      ).toBeInTheDocument();
    });
    expect(
      screen.queryByText(/Template-cloned strategy/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Cloned from template/i),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/Backtest unavailable \(no DSL\)/i),
    ).toBeInTheDocument();
  });

  it("strategy_json present (hand-built) → no legacy warning, no clone badge, View Backtest link active", async () => {
    mockUseApi.mockReturnValue({
      data: {
        ...baseStrategyRow,
        name: "Hand-built strategy",
        strategy_json: {
          indicators: [{ name: "ema_9" }, { name: "ema_21" }],
        },
        template_origin: null,
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<StrategyDetailPage params={params} />);

    await waitFor(() => {
      expect(screen.getByText(/Hand-built strategy/i)).toBeInTheDocument();
    });
    expect(
      screen.queryByText(/Phase 5 builder se pehle bani thi/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Template-cloned strategy/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Cloned from template/i),
    ).not.toBeInTheDocument();

    const backtestLink = screen.getByRole("link", { name: /View Backtest/i });
    expect(backtestLink).toBeInTheDocument();
    expect(backtestLink).toHaveAttribute(
      "href",
      `/strategies/${baseStrategyRow.id}/backtest`,
    );
  });
});
