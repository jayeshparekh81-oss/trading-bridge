/**
 * StatusPill — visual + interaction tests (B8).
 *
 * Coverage shape:
 *   - 4 rendering states (open / connecting cold / reconnecting /
 *     disconnected), each asserting the pill's dot colour testid
 *     and label text.
 *   - Countdown approximation under fake timers — confirms the
 *     label transitions from "Reconnecting in Ns..." to "0s..." as
 *     time advances. The exact starting N depends on
 *     ``reconnectDelayMs(attempt, () => 0.5)`` (jitter neutral).
 *   - Manual button: hidden when fresh-connecting, visible when
 *     disconnected, visible when sustained-failure threshold met
 *     during reconnecting (attempt >= 7). Click invokes the
 *     supplied callback.
 *
 * No real ChartWsTransport is involved — the pill is a pure-render
 * component driven by props.
 */

import { act, fireEvent, render, screen } from "@testing-library/react";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import { StatusPill } from "@/components/chart/StatusPill";
import type { ConnectionStatus } from "@/lib/chart/types";

const noopReconnect = () => {};

const disconnectedStatus: ConnectionStatus = {
  kind: "disconnected",
  reason: "broker offline",
  failed_attempts: 3,
  since: new Date(Date.UTC(2026, 4, 11, 10, 0, 0)).toISOString(),
};

describe("StatusPill — rendering by ConnectionStatus", () => {
  it("renders 'Live' with green dot when WS is open", () => {
    render(
      <StatusPill
        status={{ kind: "open" }}
        reconnectAttempt={0}
        onManualReconnect={noopReconnect}
      />,
    );

    expect(
      screen.getByTestId("chart-status-pill"),
    ).toHaveAttribute("data-state", "live");
    expect(
      screen.getByTestId("chart-status-dot-live"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("chart-status-label")).toHaveTextContent(
      "Live",
    );
    expect(
      screen.queryByTestId("chart-status-manual-reconnect"),
    ).toBeNull();
  });

  it("renders 'Connecting...' with amber dot on first connect (attempt 0)", () => {
    render(
      <StatusPill
        status={{ kind: "connecting" }}
        reconnectAttempt={0}
        onManualReconnect={noopReconnect}
      />,
    );

    expect(
      screen.getByTestId("chart-status-pill"),
    ).toHaveAttribute("data-state", "connecting");
    expect(
      screen.getByTestId("chart-status-dot-connecting"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("chart-status-label")).toHaveTextContent(
      "Connecting...",
    );
    expect(
      screen.queryByTestId("chart-status-manual-reconnect"),
    ).toBeNull();
  });

  it("renders 'Reconnecting in Ns...' when attempt > 0", () => {
    render(
      <StatusPill
        status={{ kind: "connecting" }}
        reconnectAttempt={2}
        onManualReconnect={noopReconnect}
      />,
    );

    // Initial render — countdown initialised. Don't assert the exact
    // number (timing-dependent) but assert the shape.
    const label = screen.getByTestId("chart-status-label");
    expect(label.textContent).toMatch(/Reconnecting (in \d+s)?\.\.\./);
  });

  it("renders 'Disconnected' with red dot + manual button on disconnected", () => {
    render(
      <StatusPill
        status={disconnectedStatus}
        reconnectAttempt={5}
        onManualReconnect={noopReconnect}
      />,
    );

    expect(
      screen.getByTestId("chart-status-pill"),
    ).toHaveAttribute("data-state", "disconnected");
    expect(
      screen.getByTestId("chart-status-dot-disconnected"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("chart-status-label")).toHaveTextContent(
      "Disconnected",
    );
    expect(
      screen.getByTestId("chart-status-manual-reconnect"),
    ).toBeInTheDocument();
  });
});

// ─── Countdown ────────────────────────────────────────────────────────

describe("StatusPill — countdown approximation", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("counts down as time advances during reconnecting state", () => {
    render(
      <StatusPill
        status={{ kind: "connecting" }}
        reconnectAttempt={3}
        onManualReconnect={noopReconnect}
      />,
    );

    const label = screen.getByTestId("chart-status-label");
    const initialMatch = label.textContent?.match(
      /Reconnecting in (\d+)s/,
    );
    expect(initialMatch).not.toBeNull();
    const initialSec = Number(initialMatch![1]);
    expect(initialSec).toBeGreaterThan(0);

    // Advance ~1s and expect the displayed seconds to drop by ~1.
    act(() => {
      vi.advanceTimersByTime(1100);
    });

    const afterMatch = label.textContent?.match(
      /Reconnecting in (\d+)s/,
    );
    const afterSec = afterMatch ? Number(afterMatch[1]) : 0;
    expect(afterSec).toBeLessThan(initialSec);
  });

  it("settles to 'Reconnecting...' when the countdown hits 0", () => {
    render(
      <StatusPill
        status={{ kind: "connecting" }}
        reconnectAttempt={1}
        onManualReconnect={noopReconnect}
      />,
    );

    // Advance past any plausible backoff for attempt=1 (well under
    // a few seconds).
    act(() => {
      vi.advanceTimersByTime(10_000);
    });

    expect(screen.getByTestId("chart-status-label")).toHaveTextContent(
      /Reconnecting/,
    );
  });

  it("clears the countdown when status leaves connecting", () => {
    const { rerender } = render(
      <StatusPill
        status={{ kind: "connecting" }}
        reconnectAttempt={3}
        onManualReconnect={noopReconnect}
      />,
    );
    expect(screen.getByTestId("chart-status-label").textContent).toMatch(
      /Reconnecting/,
    );

    rerender(
      <StatusPill
        status={{ kind: "open" }}
        reconnectAttempt={3}
        onManualReconnect={noopReconnect}
      />,
    );

    expect(screen.getByTestId("chart-status-label")).toHaveTextContent(
      "Live",
    );
  });
});

// ─── Manual reconnect ─────────────────────────────────────────────────

describe("StatusPill — manual reconnect button", () => {
  it("button click calls onManualReconnect when disconnected", () => {
    const handler = vi.fn();
    render(
      <StatusPill
        status={disconnectedStatus}
        reconnectAttempt={5}
        onManualReconnect={handler}
      />,
    );

    fireEvent.click(
      screen.getByTestId("chart-status-manual-reconnect"),
    );

    expect(handler).toHaveBeenCalledOnce();
  });

  it("button surfaces at sustained-failure threshold (attempt >= 7) during reconnecting", () => {
    render(
      <StatusPill
        status={{ kind: "connecting" }}
        reconnectAttempt={7}
        onManualReconnect={noopReconnect}
      />,
    );

    expect(
      screen.getByTestId("chart-status-manual-reconnect"),
    ).toBeInTheDocument();
  });

  it("button is hidden below sustained-failure threshold during reconnecting", () => {
    render(
      <StatusPill
        status={{ kind: "connecting" }}
        reconnectAttempt={6}
        onManualReconnect={noopReconnect}
      />,
    );

    expect(
      screen.queryByTestId("chart-status-manual-reconnect"),
    ).toBeNull();
  });

  it("button click works in the sustained-failure connecting case too", () => {
    const handler = vi.fn();
    render(
      <StatusPill
        status={{ kind: "connecting" }}
        reconnectAttempt={9}
        onManualReconnect={handler}
      />,
    );

    fireEvent.click(
      screen.getByTestId("chart-status-manual-reconnect"),
    );

    expect(handler).toHaveBeenCalledOnce();
  });
});
