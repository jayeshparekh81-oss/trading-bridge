/**
 * OPTIONS honesty note on the pricing surfaces.
 *
 * Every certified performance number we publish is FUTURES-basis (NRML). A tier
 * that advertises OPTIONS beside those numbers, with no note, invites a
 * customer to read futures-derived drawdown/win-rate as if it described
 * options.
 *
 * NOTE ON TIMING: no tier advertises options TODAY — that arrives with the
 * deferred plan migration. These tests pin the guard so it fires the moment a
 * tier does, rather than being remembered later.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { OptionsMetricsNote } from "@/components/billing/options-metrics-note";
import {
  CROSS_SEGMENT_METRICS_WARNING,
  FUTURES_BASIS_LABEL,
  OPTIONS_TIER_NOTE,
  mentionsOptions,
} from "@/lib/risk-labels";

// ═══════════════════════════════════════════════════════════════════════
// Detection
// ═══════════════════════════════════════════════════════════════════════
describe("mentionsOptions", () => {
  it.each([
    ["Options"],
    ["CASH + OPTIONS"],
    ["options trading"],
    ["Cash, Options aur Futures"],
  ])("detects %s", (v) => {
    expect(mentionsOptions([v])).toBe(true);
  });

  it.each([
    ["1 strategy"],
    ["CASH only"],
    ["Kill Switch"],
    ["Priority support"],
    ["FUTURES"],
  ])("does not fire on %s", (v) => {
    expect(mentionsOptions([v])).toBe(false);
  });

  it("finds options anywhere in the list", () => {
    expect(mentionsOptions(["3 strategies", "CASH + OPTIONS", "Long + Short"])).toBe(
      true,
    );
  });

  it("tolerates null / undefined / empty", () => {
    expect(mentionsOptions(null)).toBe(false);
    expect(mentionsOptions(undefined)).toBe(false);
    expect(mentionsOptions([])).toBe(false);
    expect(mentionsOptions([null, undefined])).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// Rendering
// ═══════════════════════════════════════════════════════════════════════
describe("OptionsMetricsNote", () => {
  it("renders NOTHING for a plan without options", () => {
    const { container } = render(
      <OptionsMetricsNote features={["1 strategy", "CASH only", "Long only"]} />,
    );
    expect(container.firstChild).toBeNull();
    expect(screen.queryByTestId("options-metrics-note")).toBeNull();
  });

  it("renders the note for a plan WITH options", () => {
    render(<OptionsMetricsNote features={["3 strategies", "CASH + OPTIONS"]} />);
    const el = screen.getByTestId("options-metrics-note");
    expect(el).toBeInTheDocument();
    expect(el.textContent).toContain(OPTIONS_TIER_NOTE);
  });

  it("renders when forced (a column that IS options)", () => {
    render(<OptionsMetricsNote features={[]} force />);
    expect(screen.getByTestId("options-metrics-note")).toBeInTheDocument();
  });

  it("states the futures basis explicitly", () => {
    render(<OptionsMetricsNote features={["OPTIONS"]} />);
    const text = screen.getByTestId("options-metrics-note").textContent ?? "";
    expect(text).toContain(FUTURES_BASIS_LABEL);
    expect(text).toMatch(/NRML/);
  });

  it("says options have no verified numbers of their own", () => {
    render(<OptionsMetricsNote features={["OPTIONS"]} />);
    const text = screen.getByTestId("options-metrics-note").textContent ?? "";
    expect(text).toMatch(/verified/i);
    expect(text).toMatch(/nahi/i);
  });

  it("is visible copy, not a tooltip", () => {
    render(<OptionsMetricsNote features={["OPTIONS"]} />);
    const el = screen.getByTestId("options-metrics-note");
    expect(el).toBeVisible();
    expect(el.getAttribute("aria-hidden")).not.toBe("true");
  });
});

// ═══════════════════════════════════════════════════════════════════════
// Single source — must not drift from the risk legend
// ═══════════════════════════════════════════════════════════════════════
describe("copy is composed from the existing constants", () => {
  it("embeds FUTURES_BASIS_LABEL rather than restating it", () => {
    expect(OPTIONS_TIER_NOTE).toContain(FUTURES_BASIS_LABEL);
  });

  it("agrees with the cross-segment warning about the basis", () => {
    // Both must name futures-basis; neither may claim options metrics exist.
    expect(CROSS_SEGMENT_METRICS_WARNING.toLowerCase()).toContain("futures-basis");
    expect(OPTIONS_TIER_NOTE.toLowerCase()).toContain("futures-basis");
  });

  it("never implies options performance is measured", () => {
    const low = OPTIONS_TIER_NOTE.toLowerCase();
    for (const bad of ["options returns", "options performance of", "proven options"]) {
      expect(low).not.toContain(bad);
    }
  });
});
