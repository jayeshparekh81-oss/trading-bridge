/**
 * EquityCurveChart component tests.
 *
 * recharts ResponsiveContainer measures DOM dimensions which is shaky
 * under jsdom, so tests assert the wrapping structure + empty-state
 * branch + header content rather than the SVG output.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EquityCurveChart } from "@/components/strategy-tester/EquityCurveChart";
import type { EquityCurveResponse } from "@/lib/strategy-tester/types";

const sampleEquity: EquityCurveResponse = {
  points: [
    {
      time: 1715670000,
      timestamp: "2026-05-14T09:00:00+00:00",
      equity: 100000,
      drawdownPct: 0,
      tradeId: null,
    },
    {
      time: 1715673600,
      timestamp: "2026-05-14T10:00:00+00:00",
      equity: 101250,
      drawdownPct: 0,
      tradeId: "t1",
    },
  ],
  startingEquity: 100000,
  endingEquity: 101250,
  maxEquity: 101250,
  minEquity: 100000,
};

describe("EquityCurveChart", () => {
  it("renders empty state when equity is null", () => {
    render(<EquityCurveChart equity={null} />);
    expect(screen.getByTestId("equity-empty-state")).toBeInTheDocument();
    expect(screen.queryByTestId("equity-chart-canvas")).not.toBeInTheDocument();
  });

  it("renders empty state when points array is empty", () => {
    render(
      <EquityCurveChart
        equity={{
          ...sampleEquity,
          points: [],
        }}
      />,
    );
    expect(screen.getByTestId("equity-empty-state")).toBeInTheDocument();
  });

  it("renders chart canvas with header + point count badge when data is present", () => {
    render(<EquityCurveChart equity={sampleEquity} />);
    expect(screen.getByTestId("equity-chart-canvas")).toBeInTheDocument();
    expect(screen.getByText("Equity curve")).toBeInTheDocument();
    expect(screen.getByText("2 points")).toBeInTheDocument();
  });

  it("singularises the point-count badge label when count is 1", () => {
    const single: EquityCurveResponse = {
      ...sampleEquity,
      points: [sampleEquity.points[0]],
    };
    render(<EquityCurveChart equity={single} />);
    expect(screen.getByText("1 point")).toBeInTheDocument();
  });

  it("supports a custom className passthrough", () => {
    const { container } = render(
      <EquityCurveChart
        equity={sampleEquity}
        className="custom-equity-cls"
      />,
    );
    expect(container.querySelector(".custom-equity-cls")).not.toBeNull();
  });
});
