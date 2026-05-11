/**
 * /chart page — happy-path integration test (Item 8.1 / A3).
 *
 * The page itself is a one-line client component that renders
 * <ChartContainer />. The integration value is proving the
 * default-export wires through cleanly under the same mocked-hook
 * conditions the dashboard layout will impose at runtime.
 *
 * Strategy: same hook-mocking pattern as ChartContainer.test.tsx
 * (mock the 3 hooks + stub CandlestickChart to avoid Lightweight
 * Charts in jsdom). The dashboard layout chrome (Sidebar, TopBar,
 * MobileNav, auth gating) is NOT exercised here — those are owned
 * by the layout's own tests, and a page-level test should not
 * couple to chrome it didn't import.
 *
 * Per Next.js's vitest guide for App Router client components:
 * "render(<Page />) ... expect(screen.getByRole(...))" — no
 * additional wrapping needed for ``"use client"`` pages without
 * params/searchParams.
 */

import { render, screen } from "@testing-library/react";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type Mock,
} from "vitest";

vi.mock("@/components/chart/CandlestickChart", () => ({
  CandlestickChart: ({
    candles,
  }: {
    candles: { time: number }[];
  }) => (
    <div data-testid="cs-chart-mock" data-len={String(candles.length)} />
  ),
}));

vi.mock("@/hooks/useWsToken", () => ({
  useWsToken: vi.fn(),
}));

vi.mock("@/hooks/useChartHistory", () => ({
  useChartHistory: vi.fn(),
}));

vi.mock("@/hooks/useChartWebSocket", () => ({
  useChartWebSocket: vi.fn(),
}));

// eslint-disable-next-line import/first
import ChartPage from "@/app/(dashboard)/chart/page";
// eslint-disable-next-line import/first
import { useChartHistory } from "@/hooks/useChartHistory";
// eslint-disable-next-line import/first
import { useChartWebSocket } from "@/hooks/useChartWebSocket";
// eslint-disable-next-line import/first
import { useWsToken } from "@/hooks/useWsToken";

const mockUseWsToken = useWsToken as unknown as Mock;
const mockUseHistory = useChartHistory as unknown as Mock;
const mockUseWs = useChartWebSocket as unknown as Mock;

beforeEach(() => {
  mockUseWsToken.mockReturnValue({
    token: "tok-1",
    version: 1,
    error: null,
    isLoading: false,
    sessionExpired: false,
  });
  mockUseHistory.mockReturnValue({
    candles: [
      { time: 1, open: 1, high: 2, low: 0, close: 1.5 },
      { time: 2, open: 1.5, high: 3, low: 1, close: 2.5 },
    ],
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  });
  mockUseWs.mockReturnValue({
    candles: [],
    status: { kind: "connecting" },
      reconnectAttempt: 0,
      manualReconnect: vi.fn(),
  });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("/chart page", () => {
  it("renders the chart container chrome end-to-end", () => {
    render(<ChartPage />);

    // The page default-export resolves through to ChartContainer's
    // top-level shell — top bar + chart body.
    expect(screen.getByTestId("chart-container")).toBeInTheDocument();
    expect(screen.getByTestId("chart-top-bar")).toBeInTheDocument();
    expect(screen.getByTestId("cs-chart-mock")).toBeInTheDocument();
  });

  it("passes seeded history candles through to the chart body", () => {
    render(<ChartPage />);

    // ws.candles is empty in the default mock state, so the page
    // should be rendering history.candles (length 2) into the chart.
    expect(screen.getByTestId("cs-chart-mock")).toHaveAttribute(
      "data-len",
      "2",
    );
  });

  it("does not emit console.error during render", () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const warnSpy = vi
      .spyOn(console, "warn")
      .mockImplementation(() => {});

    render(<ChartPage />);

    expect(errSpy).not.toHaveBeenCalled();
    expect(warnSpy).not.toHaveBeenCalled();
  });
});
