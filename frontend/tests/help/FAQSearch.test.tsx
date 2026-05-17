import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FAQSearch } from "@/components/help/FAQSearch";

describe("FAQSearch", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the placeholder text", () => {
    render(<FAQSearch onChange={vi.fn()} placeholder="hello search" />);
    const input = screen.getByTestId("help-search-input");
    expect(input).toHaveAttribute("placeholder", "hello search");
  });

  it("does NOT fire onChange before the debounce window elapses", () => {
    const onChange = vi.fn();
    render(<FAQSearch onChange={onChange} debounceMs={200} />);
    fireEvent.change(screen.getByTestId("help-search-input"), {
      target: { value: "broker" },
    });
    // Initial render fires with "" — clear that, we care about post-keystroke.
    onChange.mockClear();
    // Advance 150ms — still inside the window, no call.
    act(() => {
      vi.advanceTimersByTime(150);
    });
    expect(onChange).not.toHaveBeenCalled();
  });

  it("fires onChange with the trimmed value after the debounce settles", () => {
    const onChange = vi.fn();
    render(<FAQSearch onChange={onChange} debounceMs={200} />);
    fireEvent.change(screen.getByTestId("help-search-input"), {
      target: { value: "  broker  " },
    });
    act(() => {
      vi.advanceTimersByTime(250);
    });
    expect(onChange).toHaveBeenCalledWith("broker");
  });

  it("only fires the last keystroke (cancels in-flight debounce)", () => {
    const onChange = vi.fn();
    render(<FAQSearch onChange={onChange} debounceMs={200} />);
    const input = screen.getByTestId("help-search-input");
    onChange.mockClear();
    fireEvent.change(input, { target: { value: "b" } });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    fireEvent.change(input, { target: { value: "br" } });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    fireEvent.change(input, { target: { value: "broker" } });
    act(() => {
      vi.advanceTimersByTime(250);
    });
    // Only the final settled state fires through.
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenLastCalledWith("broker");
  });

  it("fires synchronously when debounceMs is 0", () => {
    const onChange = vi.fn();
    render(<FAQSearch onChange={onChange} debounceMs={0} />);
    onChange.mockClear();
    fireEvent.change(screen.getByTestId("help-search-input"), {
      target: { value: "x" },
    });
    expect(onChange).toHaveBeenCalledWith("x");
  });
});
