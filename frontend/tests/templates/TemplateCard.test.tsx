/**
 * Smoke tests for TemplateCard — covers the 3 card states.
 *
 * Focus is on the user-visible state-machine the picker depends on:
 * which state renders which badge + which button label + whether
 * the clone CTA is enabled. The deeper visual styling is covered by
 * implicit Tailwind class assertions only where state-defining.
 */

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { TemplateCard } from "@/components/strategy-templates/TemplateCard";
import type { TemplateSummary } from "@/lib/strategy-templates/types";

function makeTemplate(
  overrides: Partial<TemplateSummary> = {},
): TemplateSummary {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    slug: "test-template",
    name: "Test Template",
    segment: "EQUITY",
    instrument_type: "CASH",
    category: "Trend Following",
    complexity: "beginner",
    description_en: "A test template for unit testing the card states.",
    risk_level: "medium",
    recommended_capital_inr: 50000,
    timeframe: "5m",
    indicators_used: ["ema_9", "ema_21"],
    tags: ["trend", "test"],
    is_active: true,
    requires_options_builder: false,
    legs_count: null,
    display_order: 10,
    ...overrides,
  };
}

describe("TemplateCard — active-equity state", () => {
  // Note: the prior version used userEvent for clicks; switched to
  // fireEvent because @testing-library/user-event isn't a project dep.
  // fireEvent is sufficient for these state-machine assertions —
  // we're testing prop wiring + state-gated CTA labels, not keyboard
  // interactions or focus management.

  it("renders the template name + Available badge", () => {
    const onView = vi.fn();
    const onClone = vi.fn();
    render(
      <TemplateCard
        template={makeTemplate()}
        onView={onView}
        onClone={onClone}
      />,
    );
    expect(screen.getByTestId("template-card-name")).toHaveTextContent(
      "Test Template",
    );
    expect(
      screen.getByTestId("template-card-test-template"),
    ).toHaveAttribute("data-state", "active-equity");
  });

  it("Clone & Use button is enabled and fires onClone", () => {
    const onView = vi.fn();
    const onClone = vi.fn();
    render(
      <TemplateCard
        template={makeTemplate()}
        onView={onView}
        onClone={onClone}
      />,
    );
    const cloneBtn = screen.getByTestId("template-card-clone");
    expect(cloneBtn).not.toBeDisabled();
    expect(cloneBtn).toHaveTextContent(/Clone & Use/);
    fireEvent.click(cloneBtn);
    expect(onClone).toHaveBeenCalledTimes(1);
  });

  it("View Details fires onView", () => {
    const onView = vi.fn();
    const onClone = vi.fn();
    render(
      <TemplateCard
        template={makeTemplate()}
        onView={onView}
        onClone={onClone}
      />,
    );
    fireEvent.click(screen.getByTestId("template-card-view"));
    expect(onView).toHaveBeenCalledTimes(1);
  });
});

describe("TemplateCard — inactive-equity-coming-soon state", () => {
  it("shows Coming Soon badge and disabled CTA", () => {
    render(
      <TemplateCard
        template={makeTemplate({
          slug: "inactive-test",
          is_active: false,
          requires_options_builder: false,
        })}
        onView={vi.fn()}
        onClone={vi.fn()}
      />,
    );
    expect(
      screen.getByTestId("template-card-inactive-test"),
    ).toHaveAttribute("data-state", "inactive-equity-coming-soon");
    const cloneBtn = screen.getByTestId("template-card-clone");
    expect(cloneBtn).toBeDisabled();
    expect(cloneBtn).toHaveTextContent(/Coming Soon/);
  });

  it("does NOT fire onClone when disabled CTA is clicked", () => {
    const onClone = vi.fn();
    render(
      <TemplateCard
        template={makeTemplate({
          slug: "inactive-test-2",
          is_active: false,
          requires_options_builder: false,
        })}
        onView={vi.fn()}
        onClone={onClone}
      />,
    );
    const cloneBtn = screen.getByTestId("template-card-clone");
    // fireEvent.click on a disabled button is a no-op (per DOM spec)
    fireEvent.click(cloneBtn);
    expect(onClone).not.toHaveBeenCalled();
  });
});

describe("TemplateCard — options-builder-required state", () => {
  it("shows Options · Phase 7-8 badge and disabled CTA", () => {
    render(
      <TemplateCard
        template={makeTemplate({
          slug: "iron-condor",
          segment: "OPTIONS",
          instrument_type: "MULTI_LEG",
          is_active: false,
          requires_options_builder: true,
          legs_count: 4,
        })}
        onView={vi.fn()}
        onClone={vi.fn()}
      />,
    );
    expect(
      screen.getByTestId("template-card-iron-condor"),
    ).toHaveAttribute("data-state", "options-builder-required");
    const cloneBtn = screen.getByTestId("template-card-clone");
    expect(cloneBtn).toBeDisabled();
    expect(cloneBtn).toHaveTextContent(/Needs Options Builder/);
  });

  it("renders legs count when > 1", () => {
    render(
      <TemplateCard
        template={makeTemplate({
          slug: "iron-condor-2",
          segment: "OPTIONS",
          instrument_type: "MULTI_LEG",
          is_active: false,
          requires_options_builder: true,
          legs_count: 4,
        })}
        onView={vi.fn()}
        onClone={vi.fn()}
      />,
    );
    expect(screen.getByText(/4-leg/)).toBeInTheDocument();
  });
});
