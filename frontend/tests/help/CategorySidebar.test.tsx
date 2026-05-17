import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CategorySidebar } from "@/components/help/CategorySidebar";
import {
  CATEGORIES,
  type FAQCategory,
} from "@/lib/help/faq-content";

function makeCounts(): Record<FAQCategory, number> {
  return {
    "getting-started": 4,
    account: 3,
    brokers: 4,
    chart: 4,
    strategies: 4,
    backtest: 3,
    "live-trading": 3,
    pricing: 3,
    compliance: 3,
    troubleshooting: 4,
  };
}

describe("CategorySidebar", () => {
  it("renders an 'All' button plus one button per category", () => {
    render(
      <CategorySidebar
        categories={CATEGORIES}
        active={null}
        onChange={vi.fn()}
        counts={makeCounts()}
        lang="en"
      />,
    );
    expect(screen.getByTestId("help-category-all")).toBeInTheDocument();
    for (const c of CATEGORIES) {
      expect(
        screen.getByTestId(`help-category-${c.id}`),
      ).toBeInTheDocument();
    }
  });

  it("clicking a category fires onChange with that id", () => {
    const onChange = vi.fn();
    render(
      <CategorySidebar
        categories={CATEGORIES}
        active={null}
        onChange={onChange}
        counts={makeCounts()}
        lang="en"
      />,
    );
    fireEvent.click(screen.getByTestId("help-category-brokers"));
    expect(onChange).toHaveBeenCalledWith("brokers");
  });

  it("clicking 'All' fires onChange with null", () => {
    const onChange = vi.fn();
    render(
      <CategorySidebar
        categories={CATEGORIES}
        active="brokers"
        onChange={onChange}
        counts={makeCounts()}
        lang="en"
      />,
    );
    fireEvent.click(screen.getByTestId("help-category-all"));
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it("active category has aria-pressed=true", () => {
    render(
      <CategorySidebar
        categories={CATEGORIES}
        active="chart"
        onChange={vi.fn()}
        counts={makeCounts()}
        lang="en"
      />,
    );
    expect(screen.getByTestId("help-category-chart")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByTestId("help-category-brokers")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("renders Hindi labels when lang='hi'", () => {
    render(
      <CategorySidebar
        categories={CATEGORIES}
        active={null}
        onChange={vi.fn()}
        counts={makeCounts()}
        lang="hi"
      />,
    );
    // 'Brokers (Dhan / Fyers)' is identical en+hi for that category, so
    // pick one that diverges — 'Troubleshooting' → 'Problem solving'.
    expect(
      screen.getByTestId("help-category-troubleshooting"),
    ).toHaveTextContent("Problem solving");
  });

  it("shows per-category counts in the badge", () => {
    render(
      <CategorySidebar
        categories={CATEGORIES}
        active={null}
        onChange={vi.fn()}
        counts={makeCounts()}
        lang="en"
      />,
    );
    expect(
      screen.getByTestId("help-category-brokers"),
    ).toHaveTextContent("4");
    // 'All' shows the sum of all category counts.
    const total = Object.values(makeCounts()).reduce((a, b) => a + b, 0);
    expect(
      screen.getByTestId("help-category-all"),
    ).toHaveTextContent(String(total));
  });
});
