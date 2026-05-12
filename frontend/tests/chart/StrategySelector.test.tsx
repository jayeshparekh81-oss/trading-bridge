/**
 * StrategySelector — Day 3 / Phase 1 tests.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  loadPersistedStrategyId,
  StrategySelector,
} from "@/components/chart/StrategySelector";

const mockFetchUserStrategies = vi.fn();
vi.mock("@/lib/chart/strategies", () => ({
  fetchUserStrategies: (...args: unknown[]) =>
    mockFetchUserStrategies(...args),
}));

const happy = {
  strategies: [
    { id: "s-active-2", name: "BANKNIFTY Scalp", is_active: true },
    { id: "s-active-1", name: "NIFTY 5m", is_active: true },
    { id: "s-paused", name: "Paused One", is_active: false },
  ],
  count: 3,
};

beforeEach(() => {
  mockFetchUserStrategies.mockReset();
  mockFetchUserStrategies.mockResolvedValue(happy);
  // Clear any persisted selections between tests.
  if (typeof window !== "undefined") {
    window.localStorage.clear();
  }
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("StrategySelector", () => {
  it("fetches the strategy list on mount and sorts active-first then alphabetical", async () => {
    render(
      <StrategySelector
        symbol="NIFTY"
        timeframe="5m"
        value={null}
        onChange={vi.fn()}
      />,
    );
    await waitFor(() =>
      expect(mockFetchUserStrategies).toHaveBeenCalledTimes(1),
    );
    const select = (await screen.findByTestId(
      "strategy-select",
    )) as HTMLSelectElement;
    const options = Array.from(select.options).map((o) => o.text);
    // First option is the placeholder. Then active alphabetised
    // (BANKNIFTY before NIFTY), then paused.
    expect(options[0]).toMatch(/None|Loading|—|nahi/i);
    expect(options[1]).toContain("BANKNIFTY");
    expect(options[2]).toContain("NIFTY");
    expect(options[3]).toContain("(paused)");
  });

  it("calls onChange + persists to localStorage on selection", async () => {
    const onChange = vi.fn();
    render(
      <StrategySelector
        symbol="NIFTY"
        timeframe="5m"
        value={null}
        onChange={onChange}
      />,
    );
    const select = (await screen.findByTestId(
      "strategy-select",
    )) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "s-active-1" } });
    expect(onChange).toHaveBeenCalledWith("s-active-1");
    expect(loadPersistedStrategyId("NIFTY", "5m")).toBe("s-active-1");
  });

  it("restores persisted selection on mount when parent value is null", async () => {
    window.localStorage.setItem(
      "tb_chart_strategy:NIFTY:5m",
      "s-active-2",
    );
    const onChange = vi.fn();
    render(
      <StrategySelector
        symbol="NIFTY"
        timeframe="5m"
        value={null}
        onChange={onChange}
      />,
    );
    await waitFor(() => expect(onChange).toHaveBeenCalledWith("s-active-2"));
  });

  it("drops a persisted id that no longer matches a real strategy (deleted)", async () => {
    window.localStorage.setItem(
      "tb_chart_strategy:NIFTY:5m",
      "s-deleted",
    );
    const onChange = vi.fn();
    render(
      <StrategySelector
        symbol="NIFTY"
        timeframe="5m"
        value={null}
        onChange={onChange}
      />,
    );
    await waitFor(() =>
      expect(mockFetchUserStrategies).toHaveBeenCalledTimes(1),
    );
    // The hook removed the orphaned persisted id and did NOT call
    // onChange (no auto-select to a different strategy).
    await new Promise((r) => setTimeout(r, 30));
    expect(onChange).not.toHaveBeenCalled();
    expect(loadPersistedStrategyId("NIFTY", "5m")).toBeNull();
  });

  it("setting value to empty string clears the persisted id", async () => {
    window.localStorage.setItem(
      "tb_chart_strategy:NIFTY:5m",
      "s-active-1",
    );
    const onChange = vi.fn();
    render(
      <StrategySelector
        symbol="NIFTY"
        timeframe="5m"
        value="s-active-1"
        onChange={onChange}
      />,
    );
    const select = (await screen.findByTestId(
      "strategy-select",
    )) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "" } });
    expect(onChange).toHaveBeenCalledWith(null);
    expect(loadPersistedStrategyId("NIFTY", "5m")).toBeNull();
  });

  it("renders the error banner when the fetch rejects", async () => {
    mockFetchUserStrategies.mockReset();
    mockFetchUserStrategies.mockImplementation(async () => {
      throw new Error("server down");
    });

    render(
      <StrategySelector
        symbol="NIFTY"
        timeframe="5m"
        value={null}
        onChange={vi.fn()}
      />,
    );
    await waitFor(() =>
      expect(
        screen.getByTestId("strategy-selector-error"),
      ).toBeInTheDocument(),
    );
  });

  it("persists per-(symbol, timeframe) — distinct keys for distinct contexts", async () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <StrategySelector
        symbol="NIFTY"
        timeframe="5m"
        value={null}
        onChange={onChange}
      />,
    );
    const select = (await screen.findByTestId(
      "strategy-select",
    )) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "s-active-1" } });

    // Different (symbol, timeframe) context — key should be a
    // distinct slot in localStorage.
    rerender(
      <StrategySelector
        symbol="BANKNIFTY"
        timeframe="15m"
        value={null}
        onChange={onChange}
      />,
    );
    expect(loadPersistedStrategyId("NIFTY", "5m")).toBe("s-active-1");
    expect(loadPersistedStrategyId("BANKNIFTY", "15m")).toBeNull();
  });
});
