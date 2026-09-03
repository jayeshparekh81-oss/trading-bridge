/**
 * /chart — the Strategy Tester follows the CUSTOMER's selection.
 *
 * It used to be pinned to a hardcoded strategy id — the founder's live
 * real-money BSE strategy — for every visitor. Every chart load fired three
 * 403s (the tester endpoints are ownership-gated), the console filled with
 * "Failed to load resource", and a live-money strategy id sat in every
 * customer's browser. Found by walking the site as a fresh test account.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const testerCalls: string[] = [];
vi.mock("@/components/strategy-tester/StrategyTesterPanel", () => ({
  StrategyTesterPanel: ({ strategyId }: { strategyId: string }) => {
    testerCalls.push(strategyId);
    return <div data-testid="tester">tester for {strategyId}</div>;
  },
}));

// A stand-in chart that exposes the selector callback the real one has.
vi.mock("@/components/chart/ChartContainer", () => ({
  ChartContainer: ({ onStrategyChange }: { onStrategyChange?: (id: string | null) => void }) => (
    <div>
      <button onClick={() => onStrategyChange?.("my-strategy-1")}>pick</button>
      <button onClick={() => onStrategyChange?.(null)}>clear</button>
    </div>
  ),
}));

import ChartPage from "@/app/(dashboard)/chart/page";

describe("/chart strategy tester", () => {
  it("🔴 renders NO tester until the customer picks a strategy", () => {
    render(<ChartPage />);
    expect(screen.queryByTestId("tester")).toBeNull();
    expect(screen.getByTestId("chart-tester-hint")).toBeInTheDocument();
    expect(testerCalls).toEqual([]);
  });

  it("follows the customer's pick, and clears with it", () => {
    render(<ChartPage />);
    fireEvent.click(screen.getByText("pick"));
    expect(screen.getByTestId("tester").textContent).toContain("my-strategy-1");
    fireEvent.click(screen.getByText("clear"));
    expect(screen.queryByTestId("tester")).toBeNull();
  });

  it("🔴 the founder's live strategy id is gone from the page source", () => {
    const src = readFileSync(join(process.cwd(), "src/app/(dashboard)/chart/page.tsx"), "utf8");
    expect(src).not.toContain("89423ecc");
    expect(src).not.toMatch(/MVP_STRATEGY_ID/);
  });

  it("ChartContainer exposes the callback the page relies on", () => {
    const src = readFileSync(join(process.cwd(), "src/components/chart/ChartContainer.tsx"), "utf8");
    expect(src).toMatch(/onStrategyChange\?: \(strategyId: string \| null\) => void/);
    expect(src).toMatch(/onStrategyChange\?\.\(strategyId\)/);
  });
});
