import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { IndicatorHelpButton } from "@/components/indicators/IndicatorHelpButton";

describe("IndicatorHelpButton", () => {
  it("renders nothing for an unknown slug", () => {
    const { container } = render(<IndicatorHelpButton slug="not-a-real-one" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a button with default aria-label for a known slug", () => {
    render(<IndicatorHelpButton slug="rsi" />);
    const btn = screen.getByTestId("indicator-help-button");
    expect(btn).toHaveAttribute("data-slug", "rsi");
    expect(btn).toHaveAttribute("aria-label");
    expect(btn.getAttribute("aria-label")).toMatch(/help for/i);
  });

  it("opens the IndicatorDetailModal on click", () => {
    render(<IndicatorHelpButton slug="rsi" />);
    // Modal is not rendered initially.
    expect(screen.queryByTestId("indicator-detail-modal")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("indicator-help-button"));
    expect(screen.getByTestId("indicator-detail-modal")).toBeInTheDocument();
  });

  it("closes the modal when close button fires", () => {
    render(<IndicatorHelpButton slug="rsi" />);
    fireEvent.click(screen.getByTestId("indicator-help-button"));
    fireEvent.click(screen.getByTestId("indicator-modal-close"));
    expect(screen.queryByTestId("indicator-detail-modal")).not.toBeInTheDocument();
  });

  it("honours an aria-label override", () => {
    render(<IndicatorHelpButton slug="rsi" ariaLabel="custom" />);
    expect(screen.getByTestId("indicator-help-button")).toHaveAttribute(
      "aria-label",
      "custom",
    );
  });

  it("click does not propagate to parent (e.stopPropagation)", () => {
    const parentClick = vi.fn();
    render(
      <div onClick={parentClick}>
        <IndicatorHelpButton slug="rsi" />
      </div>,
    );
    fireEvent.click(screen.getByTestId("indicator-help-button"));
    expect(parentClick).not.toHaveBeenCalled();
  });
});
