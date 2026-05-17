import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...rest
  }: {
    children: React.ReactNode;
    href: string;
  } & React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

import { RiskAcknowledgment } from "@/components/compliance/RiskAcknowledgment";
import { LS_KEY_RISK_ACK } from "@/lib/compliance/disclaimer-text";

describe("RiskAcknowledgment", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });
  afterEach(() => {
    window.localStorage.clear();
  });

  it("renders unchecked by default; checkbox reflects the controlled prop", () => {
    render(<RiskAcknowledgment checked={false} onChange={vi.fn()} />);
    const cb = screen.getByTestId("risk-ack-checkbox") as HTMLInputElement;
    expect(cb.checked).toBe(false);
  });

  it("fires onChange(true) when toggled on", () => {
    const onChange = vi.fn();
    render(<RiskAcknowledgment checked={false} onChange={onChange} />);
    fireEvent.click(screen.getByTestId("risk-ack-checkbox"));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("stamps a timestamp into localStorage on first check", () => {
    const onChange = vi.fn();
    render(<RiskAcknowledgment checked={false} onChange={onChange} />);
    expect(window.localStorage.getItem(LS_KEY_RISK_ACK)).toBeNull();
    fireEvent.click(screen.getByTestId("risk-ack-checkbox"));
    const stored = window.localStorage.getItem(LS_KEY_RISK_ACK);
    expect(stored).not.toBeNull();
    // Stored value is a parseable ISO timestamp.
    expect(() => new Date(stored!)).not.toThrow();
    expect(new Date(stored!).getTime()).not.toBeNaN();
  });

  it("does NOT show error message when showError is false (default state)", () => {
    render(<RiskAcknowledgment checked={false} onChange={vi.fn()} />);
    expect(screen.queryByTestId("risk-ack-error")).not.toBeInTheDocument();
  });

  it("shows error message when showError + unchecked (submit-attempt state)", () => {
    render(
      <RiskAcknowledgment
        checked={false}
        onChange={vi.fn()}
        showError
        lang="hi"
      />,
    );
    expect(screen.getByTestId("risk-ack-error")).toBeInTheDocument();
    expect(screen.getByTestId("risk-ack-checkbox")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  });

  it("hides the error once the checkbox is checked, even with showError still on", () => {
    render(
      <RiskAcknowledgment
        checked={true}
        onChange={vi.fn()}
        showError
      />,
    );
    expect(screen.queryByTestId("risk-ack-error")).not.toBeInTheDocument();
  });

  it("link to /compliance/legal is present and renders the lang-specific copy", () => {
    render(<RiskAcknowledgment checked={false} onChange={vi.fn()} lang="en" />);
    const link = screen.getByTestId("risk-ack-link");
    expect(link).toHaveAttribute("href", "/compliance/legal");
    expect(link).toHaveTextContent(/read/i);
  });

  it("renders Hindi copy when lang='hi'", () => {
    render(<RiskAcknowledgment checked={false} onChange={vi.fn()} lang="hi" />);
    const wrapper = screen.getByTestId("risk-acknowledgment");
    expect(wrapper).toHaveAttribute("data-lang", "hi");
    expect(wrapper).toHaveTextContent(/samjha/i);
  });
});
