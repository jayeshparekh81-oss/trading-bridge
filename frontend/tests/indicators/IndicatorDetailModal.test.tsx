import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { IndicatorDetailModal } from "@/components/indicators/IndicatorDetailModal";

describe("IndicatorDetailModal", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });
  afterEach(() => {
    window.localStorage.clear();
  });

  it("renders nothing when open=false", () => {
    render(
      <IndicatorDetailModal open={false} slug="rsi" onClose={vi.fn()} />,
    );
    expect(screen.queryByTestId("indicator-detail-modal")).not.toBeInTheDocument();
  });

  it("renders nothing when slug is null", () => {
    render(<IndicatorDetailModal open slug={null} onClose={vi.fn()} />);
    expect(screen.queryByTestId("indicator-detail-modal")).not.toBeInTheDocument();
  });

  it("renders nothing for an unknown slug", () => {
    render(
      <IndicatorDetailModal open slug="totally-fake" onClose={vi.fn()} />,
    );
    expect(screen.queryByTestId("indicator-detail-modal")).not.toBeInTheDocument();
  });

  it("renders all major sections for a known slug", () => {
    render(<IndicatorDetailModal open slug="rsi" onClose={vi.fn()} />);
    expect(screen.getByTestId("indicator-detail-modal")).toBeInTheDocument();
    expect(screen.getByTestId("indicator-modal-title")).toHaveTextContent(/rsi/i);
    expect(screen.getByTestId("indicator-modal-oneliner")).toBeInTheDocument();
    expect(screen.getByTestId("indicator-modal-facts")).toBeInTheDocument();
    expect(screen.getByTestId("indicator-modal-use-cases")).toBeInTheDocument();
    expect(screen.getByTestId("indicator-modal-signals")).toBeInTheDocument();
    expect(screen.getByTestId("indicator-modal-pitfalls")).toBeInTheDocument();
    expect(screen.getByTestId("indicator-modal-formula")).toBeInTheDocument();
    expect(
      screen.getByTestId("indicator-modal-indian-context"),
    ).toBeInTheDocument();
  });

  it("language toggle switches between hi and en copy", () => {
    render(<IndicatorDetailModal open slug="rsi" onClose={vi.fn()} />);
    // Default hi — Hindi one-liner contains 'speed'.
    expect(screen.getByTestId("indicator-modal-oneliner")).toHaveTextContent(
      /speed/i,
    );
    // Switch to en.
    fireEvent.click(screen.getByTestId("help-lang-en"));
    expect(screen.getByTestId("indicator-modal-oneliner")).toHaveTextContent(
      /measures/i,
    );
  });

  it("close button fires onClose", () => {
    const onClose = vi.fn();
    render(<IndicatorDetailModal open slug="rsi" onClose={onClose} />);
    fireEvent.click(screen.getByTestId("indicator-modal-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("bottom close button also fires onClose", () => {
    const onClose = vi.fn();
    render(<IndicatorDetailModal open slug="rsi" onClose={onClose} />);
    fireEvent.click(screen.getByTestId("indicator-modal-close-bottom"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("clicking the backdrop fires onClose; clicking inside does not", () => {
    const onClose = vi.fn();
    render(<IndicatorDetailModal open slug="rsi" onClose={onClose} />);
    const backdrop = screen.getByTestId("indicator-detail-modal");
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
    // Inner content click should NOT propagate to backdrop.
    onClose.mockClear();
    fireEvent.click(screen.getByTestId("indicator-modal-title"));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("renders the indicator's category badge", () => {
    render(<IndicatorDetailModal open slug="rsi" onClose={vi.fn()} />);
    expect(screen.getByTestId("indicator-badge")).toHaveAttribute(
      "data-category",
      "momentum",
    );
  });
});
