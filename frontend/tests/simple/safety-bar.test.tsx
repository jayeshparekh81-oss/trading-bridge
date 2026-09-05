/** C5: Rok do · Sab band · Settings · Bahar — always there, always confirmed. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

vi.mock("framer-motion", () => ({
  motion: new Proxy({}, { get: () => (props: Record<string, unknown> & { children?: ReactNode }) => {
    const { children, ...rest } = props;
    const dom = Object.fromEntries(Object.entries(rest).filter(([k]) => /^(data-|aria-|className|role|id)/.test(k)));
    return <div {...dom}>{children}</div>;
  } }),
  AnimatePresence: ({ children }: { children?: ReactNode }) => <>{children}</>,
  useReducedMotion: () => true,
}));

import { SafetyBar } from "@/components/simple/safety-bar";

function setup() {
  const onPause = vi.fn(async () => "Sab ruk gaya.");
  const onStopAll = vi.fn(async () => "Sab band ho gaya.");
  const onLogout = vi.fn();
  render(<SafetyBar lang="hinglish" onPause={onPause} onStopAll={onStopAll} onLogout={onLogout} />);
  return { onPause, onStopAll, onLogout };
}

describe("SafetyBar", () => {
  it("renders the four actions", () => {
    setup();
    expect(screen.getByTestId("safety-bar")).toBeInTheDocument();
    expect(screen.getByTestId("safety-pause")).toBeInTheDocument();
    expect(screen.getByTestId("safety-stop-all")).toBeInTheDocument();
    expect(screen.getByTestId("safety-settings")).toHaveAttribute("href", "/settings");
    expect(screen.getByTestId("safety-logout")).toBeInTheDocument();
  });

  it("Sab band asks first; Haan runs it and reports done", async () => {
    const { onStopAll } = setup();
    fireEvent.click(screen.getByTestId("safety-stop-all"));
    expect(screen.getByTestId("safety-confirm")).toBeInTheDocument();
    expect(onStopAll).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("safety-confirm-yes"));
    await waitFor(() => expect(onStopAll).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByTestId("safety-done")).toHaveTextContent("Sab band ho gaya."));
  });

  it("Nahi cancels Rok do without calling anything", () => {
    const { onPause } = setup();
    fireEvent.click(screen.getByTestId("safety-pause"));
    fireEvent.click(screen.getByTestId("safety-confirm-no"));
    expect(onPause).not.toHaveBeenCalled();
    expect(screen.queryByTestId("safety-confirm")).toBeNull();
  });

  it("Bahar logs out", () => {
    const { onLogout } = setup();
    fireEvent.click(screen.getByTestId("safety-logout"));
    expect(onLogout).toHaveBeenCalledTimes(1);
  });
});
