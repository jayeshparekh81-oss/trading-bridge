import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { IndicatorTooltip } from "@/components/indicators/IndicatorTooltip";

describe("IndicatorTooltip", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });
  afterEach(() => {
    window.localStorage.clear();
  });

  it("renders children when slug is unknown (passthrough)", () => {
    render(
      <IndicatorTooltip slug="totally-fake-indicator">
        <span data-testid="child">RSI</span>
      </IndicatorTooltip>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
    expect(screen.queryByTestId("indicator-tooltip")).not.toBeInTheDocument();
  });

  it("wraps children and starts closed for a known slug", () => {
    render(
      <IndicatorTooltip slug="rsi">
        <span>RSI</span>
      </IndicatorTooltip>,
    );
    const wrap = screen.getByTestId("indicator-tooltip");
    expect(wrap).toHaveAttribute("data-slug", "rsi");
    expect(wrap).toHaveAttribute("data-open", "false");
    expect(
      screen.queryByTestId("indicator-tooltip-popover"),
    ).not.toBeInTheDocument();
  });

  it("opens the popover on mouseEnter and closes on mouseLeave", () => {
    render(
      <IndicatorTooltip slug="rsi">
        <span>RSI</span>
      </IndicatorTooltip>,
    );
    const wrap = screen.getByTestId("indicator-tooltip");
    fireEvent.mouseEnter(wrap);
    expect(screen.getByTestId("indicator-tooltip-popover")).toBeInTheDocument();
    fireEvent.mouseLeave(wrap);
    expect(
      screen.queryByTestId("indicator-tooltip-popover"),
    ).not.toBeInTheDocument();
  });

  it("shows the indicator's name + a category badge in the popover", () => {
    render(
      <IndicatorTooltip slug="rsi">
        <span>RSI</span>
      </IndicatorTooltip>,
    );
    fireEvent.mouseEnter(screen.getByTestId("indicator-tooltip"));
    expect(screen.getByTestId("indicator-tooltip-name")).toHaveTextContent(/rsi/i);
    expect(screen.getByTestId("indicator-badge")).toHaveAttribute(
      "data-category",
      "momentum",
    );
  });

  it("renders English one-liner when tradetri_lang='en'", () => {
    window.localStorage.setItem("tradetri_lang", "en");
    render(
      <IndicatorTooltip slug="rsi">
        <span>RSI</span>
      </IndicatorTooltip>,
    );
    fireEvent.mouseEnter(screen.getByTestId("indicator-tooltip"));
    // English one-liner contains 'Measures' — Hindi version starts with 'Price'.
    expect(screen.getByTestId("indicator-tooltip-oneliner")).toHaveTextContent(
      /measures/i,
    );
  });

  it("defaults to Hindi when no localStorage is set", () => {
    render(
      <IndicatorTooltip slug="rsi">
        <span>RSI</span>
      </IndicatorTooltip>,
    );
    fireEvent.mouseEnter(screen.getByTestId("indicator-tooltip"));
    // Hindi one-liner contains 'speed measure karta'.
    expect(screen.getByTestId("indicator-tooltip-oneliner")).toHaveTextContent(
      /speed/i,
    );
  });
});
