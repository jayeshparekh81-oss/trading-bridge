/**
 * ChartContainer — orchestration tests.
 *
 * Strategy: mock the 3 hooks (useWsToken, useChartHistory,
 * useChartWebSocket) at the module level so the container's branching
 * (loading / fetch-error / disconnected overlay / candle source
 * preference) can be driven from canned state. The CandlestickChart
 * itself is stubbed with a tiny div that surfaces its ``candles``
 * length via ``data-len`` — keeps the assertion vocabulary readable
 * without dragging Lightweight Charts into jsdom.
 *
 * The real CandlestickChart is covered in
 * ``CandlestickChart.test.tsx`` via the ``createChartFn`` test seam.
 *
 * Scope explicitly excluded:
 *   - ChartWsTransport behaviour (covered by chart_ws_transport.test.ts
 *     + useChartWebSocket.binding.test.tsx — A1).
 *   - Selector internals (covered by components.test.tsx).
 */

import { fireEvent, render, screen } from "@testing-library/react";
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
    <div
      data-testid="cs-chart-mock"
      data-len={String(candles.length)}
    />
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

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    dismiss: vi.fn(),
  },
}));

// eslint-disable-next-line import/first
import { ChartContainer } from "@/components/chart/ChartContainer";
// eslint-disable-next-line import/first
import { useChartHistory } from "@/hooks/useChartHistory";
// eslint-disable-next-line import/first
import { useChartWebSocket } from "@/hooks/useChartWebSocket";
// eslint-disable-next-line import/first
import { useWsToken } from "@/hooks/useWsToken";
// eslint-disable-next-line import/first
import { toast } from "sonner";

const mockUseWsToken = useWsToken as unknown as Mock;
const mockUseHistory = useChartHistory as unknown as Mock;
const mockUseWs = useChartWebSocket as unknown as Mock;
const mockToastError = toast.error as unknown as Mock;
const mockToastDismiss = toast.dismiss as unknown as Mock;

const DISCONNECTED_TOAST_ID = "chart-broker-disconnected";

const sampleCandle = (time: number) => ({
  time,
  open: time,
  high: time + 1,
  low: time - 1,
  close: time + 0.5,
});

beforeEach(() => {
  mockUseWsToken.mockReturnValue({
    token: "tok-1",
    version: 1,
    error: null,
    isLoading: false,
    sessionExpired: false,
  });
  mockUseHistory.mockReturnValue({
    candles: [],
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

describe("ChartContainer — mount + hook wiring", () => {
  it("mounts the top bar + chart mock and seeds hooks with NIFTY/5m/NSE", () => {
    render(<ChartContainer />);

    expect(screen.getByTestId("chart-container")).toBeInTheDocument();
    expect(screen.getByTestId("chart-top-bar")).toBeInTheDocument();
    expect(screen.getByTestId("symbol-input")).toHaveValue("NIFTY");
    expect(screen.getByTestId("cs-chart-mock")).toBeInTheDocument();

    expect(mockUseHistory).toHaveBeenCalledWith(
      expect.objectContaining({
        symbol: "NIFTY",
        exchange: "NSE",
        timeframe: "5m",
      }),
    );
    expect(mockUseWs).toHaveBeenCalledWith(
      expect.objectContaining({
        symbol: "NIFTY",
        timeframe: "5m",
        token: "tok-1",
        tokenVersion: 1,
        sessionExpired: false,
      }),
    );
  });

  it("honours initialSymbol / initialTimeframe / exchange props", () => {
    render(
      <ChartContainer
        initialSymbol="BANKNIFTY"
        initialTimeframe="15m"
        exchange="BSE"
      />,
    );

    expect(mockUseHistory).toHaveBeenCalledWith(
      expect.objectContaining({
        symbol: "BANKNIFTY",
        exchange: "BSE",
        timeframe: "15m",
      }),
    );
    expect(mockUseWs).toHaveBeenCalledWith(
      expect.objectContaining({
        symbol: "BANKNIFTY",
        timeframe: "15m",
      }),
    );
  });

  it("forwards sessionExpired from token state to the WS hook", () => {
    mockUseWsToken.mockReturnValue({
      token: "tok-1",
      version: 1,
      error: null,
      isLoading: false,
      sessionExpired: true,
    });

    render(<ChartContainer />);

    expect(mockUseWs).toHaveBeenCalledWith(
      expect.objectContaining({ sessionExpired: true }),
    );
  });
});

describe("ChartContainer — UI states", () => {
  it("renders LoadingState when history is loading and no candles yet", () => {
    mockUseHistory.mockReturnValue({
      candles: [],
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    });

    render(<ChartContainer />);

    expect(screen.getByTestId("chart-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("cs-chart-mock")).toBeNull();
  });

  it("renders fetch ErrorState and retry calls history.refetch", () => {
    const refetch = vi.fn();
    mockUseHistory.mockReturnValue({
      candles: [],
      isLoading: false,
      error: new Error("Network down"),
      refetch,
    });

    render(<ChartContainer />);

    expect(screen.getByTestId("chart-error-fetch")).toBeInTheDocument();
    expect(screen.getByText("Network down")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("chart-error-retry"));

    expect(refetch).toHaveBeenCalledOnce();
  });

  it("suppresses the fetch ErrorState once candles exist (graceful degradation)", () => {
    // A transient fetch error after the first successful load should
    // not blank the chart — the user keeps reading the last-known
    // candles while the next refetch attempt runs.
    mockUseHistory.mockReturnValue({
      candles: [sampleCandle(1)],
      isLoading: false,
      error: new Error("blip"),
      refetch: vi.fn(),
    });

    render(<ChartContainer />);

    expect(screen.queryByTestId("chart-error-fetch")).toBeNull();
    expect(screen.getByTestId("cs-chart-mock")).toBeInTheDocument();
  });

  it("fires toast.error with stable id when WS status is disconnected", () => {
    mockUseWs.mockReturnValue({
      candles: [sampleCandle(1)],
      status: {
        kind: "disconnected",
        reason: "broker offline",
        failed_attempts: 3,
        since: Date.UTC(2026, 4, 11, 10, 0, 0),
      },
      reconnectAttempt: 0,
      manualReconnect: vi.fn(),
    });

    render(<ChartContainer />);

    expect(mockToastError).toHaveBeenCalledTimes(1);
    const [title, opts] = mockToastError.mock.calls[0];
    expect(title).toBe("Broker connection toot gaya");
    expect(opts).toMatchObject({
      id: DISCONNECTED_TOAST_ID,
      description: expect.stringMatching(/broker offline.*3 attempts/),
    });
    // No inline overlay should be rendered any more.
    expect(
      screen.queryByTestId("chart-disconnected-overlay"),
    ).toBeNull();
  });

  it("does not fire toast.error when WS is connecting", () => {
    mockUseWs.mockReturnValue({
      candles: [],
      status: { kind: "connecting" },
      reconnectAttempt: 0,
      manualReconnect: vi.fn(),
    });

    render(<ChartContainer />);

    expect(mockToastError).not.toHaveBeenCalled();
    // The else branch still dismisses-by-id (no-op when no toast
    // exists) — confirms the effect ran with the connecting branch.
    expect(mockToastDismiss).toHaveBeenCalledWith(DISCONNECTED_TOAST_ID);
  });
});

describe("ChartContainer — disconnect toast lifecycle", () => {
  it("dismisses the toast when status transitions away from disconnected", () => {
    mockUseWs.mockReturnValue({
      candles: [sampleCandle(1)],
      status: {
        kind: "disconnected",
        reason: "broker offline",
        failed_attempts: 1,
        since: Date.UTC(2026, 4, 11, 10, 0, 0),
      },
      reconnectAttempt: 0,
      manualReconnect: vi.fn(),
    });

    const { rerender } = render(<ChartContainer />);
    expect(mockToastError).toHaveBeenCalledTimes(1);
    mockToastDismiss.mockClear();

    // Status flips back to connected — effect re-fires, takes the
    // else branch, dismisses the toast by stable id.
    mockUseWs.mockReturnValue({
      candles: [sampleCandle(1)],
      status: { kind: "connected" },
      reconnectAttempt: 0,
      manualReconnect: vi.fn(),
    });
    rerender(<ChartContainer />);

    expect(mockToastDismiss).toHaveBeenCalledWith(DISCONNECTED_TOAST_ID);
  });

  it("dismisses the toast on unmount so it doesn't leak to other routes", () => {
    mockUseWs.mockReturnValue({
      candles: [sampleCandle(1)],
      status: {
        kind: "disconnected",
        reason: "broker offline",
        failed_attempts: 1,
        since: Date.UTC(2026, 4, 11, 10, 0, 0),
      },
      reconnectAttempt: 0,
      manualReconnect: vi.fn(),
    });

    const { unmount } = render(<ChartContainer />);
    mockToastDismiss.mockClear();

    unmount();

    expect(mockToastDismiss).toHaveBeenCalledWith(DISCONNECTED_TOAST_ID);
  });
});

describe("ChartContainer — user-driven re-seeding", () => {
  it("symbol change re-invokes history + ws hooks with the new symbol", () => {
    render(<ChartContainer />);

    fireEvent.click(screen.getByTestId("symbol-quick-BANKNIFTY"));

    expect(mockUseHistory.mock.lastCall?.[0]).toMatchObject({
      symbol: "BANKNIFTY",
    });
    expect(mockUseWs.mock.lastCall?.[0]).toMatchObject({
      symbol: "BANKNIFTY",
    });
  });

  it("timeframe change re-invokes history + ws hooks with the new timeframe", () => {
    render(<ChartContainer />);

    fireEvent.click(screen.getByTestId("timeframe-15m"));

    expect(mockUseHistory.mock.lastCall?.[0]).toMatchObject({
      timeframe: "15m",
    });
    expect(mockUseWs.mock.lastCall?.[0]).toMatchObject({
      timeframe: "15m",
    });
  });
});

describe("ChartContainer — candle source preference", () => {
  it("prefers ws.candles when WS has any data", () => {
    mockUseHistory.mockReturnValue({
      candles: [sampleCandle(1)],
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    mockUseWs.mockReturnValue({
      candles: [sampleCandle(1), sampleCandle(2)],
      status: { kind: "connected" },
      reconnectAttempt: 0,
      manualReconnect: vi.fn(),
    });

    render(<ChartContainer />);

    expect(screen.getByTestId("cs-chart-mock")).toHaveAttribute(
      "data-len",
      "2",
    );
  });

  it("falls back to history.candles when ws.candles is empty", () => {
    mockUseHistory.mockReturnValue({
      candles: [sampleCandle(1), sampleCandle(2)],
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

    render(<ChartContainer />);

    expect(screen.getByTestId("cs-chart-mock")).toHaveAttribute(
      "data-len",
      "2",
    );
  });

  it("forwards history.candles as initialCandles to the WS hook", () => {
    const seed = [sampleCandle(1), sampleCandle(2)];
    mockUseHistory.mockReturnValue({
      candles: seed,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<ChartContainer />);

    expect(mockUseWs).toHaveBeenCalledWith(
      expect.objectContaining({ initialCandles: seed }),
    );
  });
});

describe("ChartContainer — StatusPill wiring (B8)", () => {
  it("renders the StatusPill in the top bar reflecting WS status", () => {
    mockUseWs.mockReturnValue({
      candles: [],
      status: { kind: "open" },
      reconnectAttempt: 0,
      manualReconnect: vi.fn(),
    });

    render(<ChartContainer />);

    const pill = screen.getByTestId("chart-status-pill");
    expect(pill).toBeInTheDocument();
    expect(pill).toHaveAttribute("data-state", "live");
    // Pill lives inside the top bar, not the chart body.
    expect(
      screen.getByTestId("chart-top-bar"),
    ).toContainElement(pill);
  });

  it("clicking the manual reconnect button calls ws.manualReconnect", () => {
    const manualReconnect = vi.fn();
    mockUseWs.mockReturnValue({
      candles: [sampleCandle(1)],
      status: {
        kind: "disconnected",
        reason: "broker offline",
        failed_attempts: 3,
        since: Date.UTC(2026, 4, 11, 10, 0, 0),
      },
      reconnectAttempt: 5,
      manualReconnect,
    });

    render(<ChartContainer />);

    fireEvent.click(
      screen.getByTestId("chart-status-manual-reconnect"),
    );

    expect(manualReconnect).toHaveBeenCalledOnce();
  });
});
