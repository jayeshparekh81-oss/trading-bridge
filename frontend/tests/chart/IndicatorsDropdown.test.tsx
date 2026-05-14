/**
 * IndicatorsDropdown — Phase 2 / Phase 3 control tests.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  IndicatorsDropdown,
  loadPersistedToggles,
} from "@/components/chart/IndicatorsDropdown";

vi.mock("sonner", () => ({
  toast: { info: vi.fn(), error: vi.fn(), dismiss: vi.fn() },
}));

const defaults = {
  sma20: true,
  ema50: true,
  rsi: true,
  macd: false,
  volume: true,
};

beforeEach(() => {
  if (typeof window !== "undefined") window.localStorage.clear();
});

afterEach(() => vi.clearAllMocks());

describe("IndicatorsDropdown", () => {
  it("renders the toggle button with the active count", () => {
    render(<IndicatorsDropdown value={defaults} onChange={vi.fn()} />);
    const btn = screen.getByTestId("indicators-dropdown-toggle");
    expect(btn).toHaveTextContent("Indicators");
    expect(btn).toHaveTextContent("(4)"); // sma + ema + rsi + volume
  });

  it("opens the menu on click and renders the five toggles (Phase 4 added Volume)", () => {
    render(<IndicatorsDropdown value={defaults} onChange={vi.fn()} />);
    fireEvent.click(screen.getByTestId("indicators-dropdown-toggle"));
    expect(screen.getByTestId("indicators-dropdown-menu")).toBeInTheDocument();
    expect(screen.getByTestId("indicator-toggle-sma20")).toBeChecked();
    expect(screen.getByTestId("indicator-toggle-ema50")).toBeChecked();
    expect(screen.getByTestId("indicator-toggle-rsi")).toBeChecked();
    expect(screen.getByTestId("indicator-toggle-macd")).not.toBeChecked();
    expect(screen.getByTestId("indicator-toggle-volume")).toBeChecked();
  });

  it("toggling a checkbox fires onChange with the patched state", () => {
    const onChange = vi.fn();
    render(<IndicatorsDropdown value={defaults} onChange={onChange} />);
    fireEvent.click(screen.getByTestId("indicators-dropdown-toggle"));
    fireEvent.click(screen.getByTestId("indicator-toggle-sma20"));
    expect(onChange).toHaveBeenLastCalledWith({ ...defaults, sma20: false });
  });

  it("persists changes to localStorage", () => {
    const onChange = vi.fn();
    render(<IndicatorsDropdown value={defaults} onChange={onChange} />);
    fireEvent.click(screen.getByTestId("indicators-dropdown-toggle"));
    fireEvent.click(screen.getByTestId("indicator-toggle-macd"));
    expect(loadPersistedToggles()).toMatchObject({ macd: true });
  });

  it("'add custom' fires a sonner info toast", async () => {
    const { toast } = await import("sonner");
    render(<IndicatorsDropdown value={defaults} onChange={vi.fn()} />);
    fireEvent.click(screen.getByTestId("indicators-dropdown-toggle"));
    fireEvent.click(screen.getByTestId("indicator-add-custom"));
    expect(toast.info).toHaveBeenCalledWith(
      expect.stringMatching(/jaldi aayenge/i),
    );
  });

  it("outside-click closes the menu", () => {
    render(
      <div>
        <IndicatorsDropdown value={defaults} onChange={vi.fn()} />
        <div data-testid="outside">outside</div>
      </div>,
    );
    fireEvent.click(screen.getByTestId("indicators-dropdown-toggle"));
    expect(screen.queryByTestId("indicators-dropdown-menu")).toBeInTheDocument();
    fireEvent.mouseDown(screen.getByTestId("outside"));
    expect(screen.queryByTestId("indicators-dropdown-menu")).toBeNull();
  });
});

describe("loadPersistedToggles", () => {
  it("returns defaults when nothing persisted", () => {
    expect(loadPersistedToggles()).toMatchObject({
      sma20: true,
      ema50: true,
      rsi: true,
      macd: false,
    });
  });

  it("merges persisted partial state with defaults (forward-compat)", () => {
    window.localStorage.setItem(
      "tb_chart_indicators",
      JSON.stringify({ sma20: false }),
    );
    const t = loadPersistedToggles();
    expect(t.sma20).toBe(false);
    // Other fields fall back to defaults — added in a future phase
    // without invalidating the operator's stored prefs.
    expect(t.ema50).toBe(true);
    expect(t.macd).toBe(false);
  });

  it("falls back to defaults on corrupt JSON", () => {
    window.localStorage.setItem("tb_chart_indicators", "not_json");
    expect(loadPersistedToggles()).toMatchObject({
      sma20: true,
      ema50: true,
    });
  });
});
