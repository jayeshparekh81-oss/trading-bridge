/**
 * GlowButton as a base-ui `render` element — nesting + behaviour.
 *
 * Two regressions are locked in here:
 *   1. HYDRATION: a trigger must not produce <button> inside <button>. base-ui
 *      has NO `asChild`; the API is `render={<Component/>}`, which REPLACES the
 *      trigger's own element instead of wrapping one.
 *   2. BEHAVIOUR: `render` only works if the target component accepts and
 *      forwards `ref` (React 19 passes it as a plain prop) and spreads the
 *      injected props (onClick/aria-*). If either is dropped, the markup looks
 *      fine but the dialog silently stops opening — so we assert it OPENS.
 */

import { describe, it, expect } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";

import { GlowButton } from "@/components/ui/glow-button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

function Harness() {
  return (
    <Dialog>
      <DialogTrigger render={<GlowButton variant="danger" />}>
        Open it
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Confirm something</DialogTitle>
        </DialogHeader>
      </DialogContent>
    </Dialog>
  );
}

describe("GlowButton inside a base-ui DialogTrigger", () => {
  it("renders exactly ONE button — no <button> inside <button>", () => {
    const { container } = render(<Harness />);
    const buttons = container.querySelectorAll("button");
    expect(buttons.length).toBe(1);
    // and that single button contains no nested button
    expect(within(buttons[0] as HTMLElement).queryByRole("button")).toBeNull();
  });

  it("keeps the GlowButton styling (render replaced the trigger element)", () => {
    const { container } = render(<Harness />);
    const btn = container.querySelector("button")!;
    // danger variant class comes from GlowButton, proving it IS the trigger
    expect(btn.className).toMatch(/from-red-500|to-loss/);
    expect(btn.textContent).toContain("Open it");
  });

  it("STILL OPENS on click (ref + props forwarding intact)", async () => {
    render(<Harness />);
    expect(screen.queryByText("Confirm something")).toBeNull();

    fireEvent.click(screen.getByRole("button"));

    expect(await screen.findByText("Confirm something")).toBeInTheDocument();
  });

  it("forwards a ref to the underlying button element", () => {
    let node: HTMLButtonElement | null = null;
    render(
      <GlowButton ref={(el) => { node = el; }}>Hi</GlowButton>,
    );
    expect(node).not.toBeNull();
    expect((node as unknown as HTMLElement).tagName).toBe("BUTTON");
  });

  it("spreads arbitrary props (onClick/aria) onto the button", () => {
    let clicked = false;
    render(
      <GlowButton aria-label="glow" onClick={() => { clicked = true; }}>
        Hi
      </GlowButton>,
    );
    const btn = screen.getByLabelText("glow");
    fireEvent.click(btn);
    expect(clicked).toBe(true);
  });
});
