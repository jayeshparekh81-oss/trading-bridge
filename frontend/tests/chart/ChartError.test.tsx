/**
 * /chart error.tsx — Next.js App Router error boundary fallback.
 *
 * Two layers of coverage:
 *
 *   1. Unit — render ChartError directly with a fake error + a
 *      vi.fn() unstable_retry. Asserts the page-crash ErrorState
 *      mounts with the right message shape (incl. digest), and the
 *      retry button wires through to unstable_retry. Cheap and
 *      isolated.
 *
 *   2. Integration — Next.js' router-level boundary isn't reachable
 *      from a unit-test render, so we stand up an equivalent React
 *      class boundary (``TestSegmentBoundary``) that mirrors the
 *      ``error.tsx`` contract. Mounts ChartContainer with one hook
 *      forced to throw on first render; after the boundary catches
 *      the throw, ChartError renders. Click "Try again" → the test
 *      boundary's reset clears the throw flag and re-renders, and
 *      the chart resumes normal render.
 *
 * Why a stand-in boundary: Next.js wraps ``error.tsx`` in a React
 * Error Boundary at the router level. The mechanics that matter
 * for product behaviour are (a) the boundary catches, (b) the
 * fallback renders with ``error`` + ``unstable_retry`` props,
 * (c) calling ``unstable_retry`` re-renders the children. The
 * TestSegmentBoundary models exactly those three points without
 * pulling Next.js' router into the test bed.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { Component, useState, type ReactNode } from "react";
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

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    dismiss: vi.fn(),
  },
}));

// eslint-disable-next-line import/first
import ChartError from "@/app/(dashboard)/chart/error";
// eslint-disable-next-line import/first
import { ChartContainer } from "@/components/chart/ChartContainer";
// eslint-disable-next-line import/first
import { useChartHistory } from "@/hooks/useChartHistory";
// eslint-disable-next-line import/first
import { useChartWebSocket } from "@/hooks/useChartWebSocket";
// eslint-disable-next-line import/first
import { useWsToken } from "@/hooks/useWsToken";

const mockUseWsToken = useWsToken as unknown as Mock;
const mockUseHistory = useChartHistory as unknown as Mock;
const mockUseWs = useChartWebSocket as unknown as Mock;

const happyHookDefaults = () => {
  mockUseWsToken.mockReturnValue({
    token: "tok",
    version: 1,
    error: null,
    isLoading: false,
    sessionExpired: false,
  });
  mockUseHistory.mockReturnValue({
    candles: [{ time: 1, open: 1, high: 1, low: 1, close: 1 }],
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  });
  mockUseWs.mockReturnValue({
    candles: [],
    status: { kind: "connecting" },
  });
};

beforeEach(() => {
  happyHookDefaults();
});

afterEach(() => {
  vi.clearAllMocks();
});

// ─── Unit tests ───────────────────────────────────────────────────────

describe("ChartError — unit (B6)", () => {
  it("renders the page-crash ErrorState with the error message", () => {
    const err = Object.assign(new Error("Render exploded"), {
      digest: "abc123",
    });
    const retry = vi.fn();

    render(<ChartError error={err} unstable_retry={retry} />);

    expect(screen.getByTestId("chart-error-boundary")).toBeInTheDocument();
    expect(
      screen.getByTestId("chart-error-page-crash"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Chart crash ho gaya/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Render exploded.*ID: abc123/),
    ).toBeInTheDocument();
  });

  it("renders without a digest when error has none", () => {
    const err = new Error("Plain error");
    render(<ChartError error={err} unstable_retry={vi.fn()} />);

    expect(screen.getByText("Plain error")).toBeInTheDocument();
    expect(screen.queryByText(/ID:/)).toBeNull();
  });

  it("falls back to a generic message when error.message is empty", () => {
    const err = Object.assign(new Error(""), { digest: undefined });
    render(<ChartError error={err} unstable_retry={vi.fn()} />);

    expect(
      screen.getByText("Unexpected render error"),
    ).toBeInTheDocument();
  });

  it("retry button calls unstable_retry once", () => {
    const retry = vi.fn();
    render(
      <ChartError
        error={new Error("boom")}
        unstable_retry={retry}
      />,
    );

    fireEvent.click(screen.getByTestId("chart-error-retry"));

    expect(retry).toHaveBeenCalledOnce();
  });

  it("logs the error via console.error so Sentry's auto-capture picks it up", () => {
    const errSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    render(
      <ChartError
        error={new Error("logged")}
        unstable_retry={vi.fn()}
      />,
    );

    expect(errSpy).toHaveBeenCalledWith(
      "[chart] error boundary caught:",
      expect.objectContaining({ message: "logged" }),
    );
  });
});

// ─── Integration test: throw inside ChartContainer ────────────────────

interface TestSegmentBoundaryProps {
  children: ReactNode;
  fallback: (props: {
    error: Error;
    unstable_retry: () => void;
  }) => ReactNode;
}

interface TestSegmentBoundaryState {
  error: Error | null;
  key: number; // bumped on retry to force a re-mount of children
}

/**
 * Stand-in for Next.js' router-level error boundary. Models the
 * three behaviours that matter:
 *   1. componentDidCatch — catch render errors from children.
 *   2. Render the fallback with ``error`` + ``unstable_retry``
 *      props matching the App Router contract.
 *   3. unstable_retry — clear the caught error AND remount children
 *      (the v16.2.0 "re-fetch + re-render" semantics; modelled here
 *      as a key-bump so the children re-mount fresh).
 */
class TestSegmentBoundary extends Component<
  TestSegmentBoundaryProps,
  TestSegmentBoundaryState
> {
  state: TestSegmentBoundaryState = { error: null, key: 0 };

  static getDerivedStateFromError(error: Error): Partial<TestSegmentBoundaryState> {
    return { error };
  }

  retry = () => {
    this.setState((s) => ({ error: null, key: s.key + 1 }));
  };

  render() {
    if (this.state.error) {
      return this.props.fallback({
        error: this.state.error,
        unstable_retry: this.retry,
      });
    }
    return <div key={this.state.key}>{this.props.children}</div>;
  }
}

describe("ChartError — integration with ChartContainer (B6)", () => {
  // Strict-mode-style double-render of React + a thrown hook produces
  // noisy console.error output. Silence it for these tests; the
  // boundary itself logs once via console.error and we verify that
  // separately in the unit tests above.
  let errSpy: Mock;
  beforeEach(() => {
    errSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => {}) as unknown as Mock;
  });
  afterEach(() => {
    errSpy.mockRestore();
  });

  it("catches a hook throw and renders the ChartError fallback", () => {
    // Force useChartHistory to throw on this render — simulates a
    // hook-level bug or a corrupt server response that bubbles up
    // through the React render phase.
    mockUseHistory.mockImplementation(() => {
      throw new Error("history hook blew up");
    });

    render(
      <TestSegmentBoundary
        fallback={(p) => <ChartError {...p} />}
      >
        <ChartContainer />
      </TestSegmentBoundary>,
    );

    // ChartContainer's testid should NOT be present — the boundary
    // caught before it could render. The error boundary's testid
    // should be.
    expect(screen.queryByTestId("chart-container")).toBeNull();
    expect(
      screen.getByTestId("chart-error-boundary"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("history hook blew up"),
    ).toBeInTheDocument();
  });

  it("clicking 'Try again' clears the error and re-renders the chart", () => {
    // Mutable flag controlled by the test — first render throws,
    // subsequent renders return happy state.
    let shouldThrow = true;
    mockUseHistory.mockImplementation(() => {
      if (shouldThrow) {
        throw new Error("first-render boom");
      }
      return {
        candles: [{ time: 1, open: 1, high: 1, low: 1, close: 1 }],
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      };
    });

    render(
      <TestSegmentBoundary
        fallback={(p) => <ChartError {...p} />}
      >
        <ChartContainer />
      </TestSegmentBoundary>,
    );

    expect(
      screen.getByTestId("chart-error-boundary"),
    ).toBeInTheDocument();

    // Flip the flag so the next render of the children succeeds,
    // then click retry — TestSegmentBoundary re-mounts children
    // (key bump) and the chart renders normally.
    shouldThrow = false;
    fireEvent.click(screen.getByTestId("chart-error-retry"));

    expect(
      screen.queryByTestId("chart-error-boundary"),
    ).toBeNull();
    expect(screen.getByTestId("chart-container")).toBeInTheDocument();
  });
});
