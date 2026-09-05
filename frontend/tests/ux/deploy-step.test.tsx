/**
 * STEP 3 — the deploy config must be a real STEP (audit finding #2).
 *
 * It used to be an 11px grey "Settings" text button inside a collapsed row,
 * which is why nobody found it. Tradetron/StrykeX make deploy an explicit,
 * primary action.
 *
 * FOUNDER'S DECISION, enforced here: Vehicle and Direction ship visibly
 * "Coming soon" and DISABLED. Promoting this panel to a headline Deploy step
 * makes every control in it look authoritative — and those two neither persist
 * nor are enforced. A disabled "coming soon" control is honest; an enabled one
 * that silently does nothing is a lie. Quantity and Execution mode DO work and
 * stay live.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));
vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    status: number; detail: string;
    constructor(s: number, d: string) { super(d); this.status = s; this.detail = d; }
  }
  return {
    api: {
      get: vi.fn().mockResolvedValue({
        subscription_id: "s1", lots_override: null, execution_mode: "offline",
        is_paper: true, applied: false, pending_fanout_merge: true,
      }),
      patch: vi.fn(), post: vi.fn(),
    },
    ApiError,
  };
});

import { SubscriptionSettings } from "@/components/marketplace/subscription-settings";

const read = (p: string) => readFileSync(join(process.cwd(), p), "utf8");
const ME_PAGE = read("src/app/(dashboard)/marketplace/me/page.tsx");

beforeEach(() => vi.clearAllMocks());

// ═══════════════════════════════════════════════════════════════════
// The Deploy button replaced the buried expander
// ═══════════════════════════════════════════════════════════════════
describe("Deploy is a real step, not a grey text link", () => {
  it("the row renders a Deploy control", () => {
    expect(ME_PAGE).toContain('data-testid={`deploy-${sub.id}`}');
    // Plain Hinglish for the Level 1–3 customer: "Chalu karo" / "Chhupao" (Simple mode, C3).
    expect(ME_PAGE).toMatch(/"Chhupao" : "Chalu karo"/);
  });

  it("the old 11px muted Settings text button is gone", () => {
    expect(ME_PAGE).not.toContain('{open ? "Hide" : "Settings"}');
    expect(ME_PAGE).not.toContain("Settings2");
  });

  it("a freshly-subscribed row opens its panel and scrolls into view", () => {
    expect(ME_PAGE).toContain("useState(highlight)");
    expect(ME_PAGE).toContain("scrollIntoView");
  });

  it("reads ?sub= to know which row to highlight", () => {
    expect(ME_PAGE).toContain('searchParams?.get("sub")');
  });
});

// ═══════════════════════════════════════════════════════════════════
// ⚠️ HONESTY: preview controls are disabled, working ones are not
// ═══════════════════════════════════════════════════════════════════
describe("Vehicle + Direction ship disabled and marked Coming soon", () => {
  it("VEHICLE carries a visible Coming soon badge; DIRECTION no longer does", async () => {
    // Direction became real: the settings PATCH persists direction_filter and
    // the fan-out entry gate enforces it. Vehicle stays disabled — the platform
    // cannot honestly execute a futures signal as cash or options.
    render(<SubscriptionSettings subscriptionId="s1" />);
    await waitFor(() =>
      expect(screen.getByTestId("subscription-settings")).toBeInTheDocument(),
    );
    expect(screen.getByTestId("vehicle-coming-soon")).toBeInTheDocument();
    expect(screen.queryByTestId("direction-coming-soon")).toBeNull();
  });

  // base-ui disables via aria-disabled + tabindex=-1 + pointer-events-none,
  // NOT the native `disabled` attribute — so jest-dom's toBeDisabled() does not
  // see it. Asserting the real mechanism keeps this test honest: it proves the
  // control is genuinely inert, not merely greyed out.
  // NOTE: tabindex is NOT a reliable signal here — base-ui uses a roving
  // tabindex and keeps the SELECTED tab focusable (tabindex="0") even when
  // disabled. aria-disabled + data-disabled are the real markers, and the
  // click test below is the behavioural proof.
  const assertInert = (el: HTMLElement) => {
    expect(el.getAttribute("aria-disabled")).toBe("true");
    expect(el.hasAttribute("data-disabled")).toBe(true);
  };

  it("every vehicle option is genuinely inert", async () => {
    render(<SubscriptionSettings subscriptionId="s1" />);
    await waitFor(() => screen.getByTestId("vehicle-cash"));
    for (const v of ["cash", "futures", "options"]) {
      assertInert(screen.getByTestId(`vehicle-${v}`));
    }
  });

  it("every direction option is now LIVE, not inert", async () => {
    render(<SubscriptionSettings subscriptionId="s1" />);
    await waitFor(() => screen.getByTestId("direction-all"));
    for (const d of ["long", "short", "all"]) {
      const el = screen.getByTestId(`direction-${d}`);
      // the inverse of assertInert: base-ui marks a disabled trigger with
      // aria-disabled + data-disabled, and a live one carries neither.
      expect(el.getAttribute("aria-disabled")).not.toBe("true");
      expect(el.hasAttribute("data-disabled")).toBe(false);
    }
  });

  it("🔴 the direction control carries NO performance numbers", async () => {
    // The published record is the long+short system. The long-only and
    // short-only slices are explicitly NOT an independently-validated
    // standalone strategy, so no figure may sit beside this choice.
    render(<SubscriptionSettings subscriptionId="s1" />);
    const note = await screen.findByTestId("direction-record-note");
    expect(note.textContent).toMatch(/long\+short/i);
    expect(note.textContent).not.toMatch(/\d+(\.\d+)?\s*%/);
    expect(note.textContent).not.toMatch(/PF|profit factor/i);
  });

  it("clicking a disabled vehicle changes nothing", async () => {
    render(<SubscriptionSettings subscriptionId="s1" />);
    await waitFor(() => screen.getByTestId("vehicle-cash"));
    const before = screen.getByTestId("vehicle-futures").getAttribute("aria-selected");
    fireEvent.click(screen.getByTestId("vehicle-cash"));
    expect(
      screen.getByTestId("vehicle-futures").getAttribute("aria-selected"),
    ).toBe(before);
  });

  it("the WORKING controls stay enabled — quantity", async () => {
    render(<SubscriptionSettings subscriptionId="s1" />);
    await waitFor(() => screen.getByTestId("lots-override-input"));
    expect(screen.getByTestId("lots-override-input")).not.toBeDisabled();
    expect(screen.getByTestId("lots-inc")).not.toBeDisabled();
  });

  it("the WORKING controls stay enabled — paper toggle", async () => {
    render(<SubscriptionSettings subscriptionId="s1" />);
    await waitFor(() => screen.getByTestId("is-paper-toggle"));
    expect(screen.getByTestId("is-paper-toggle")).not.toBeDisabled();
  });

  it("VEHICLE is never sent; DIRECTION is", () => {
    const src = read("src/components/marketplace/subscription-settings.tsx");
    // The PATCH body must carry ONLY the three fields that persist. Checked on
    // the CODE, not the file text — the wire-up note mentions direction_filter
    // in a comment, and an earlier version of this test wrongly matched that.
    const code = src
      .split("\n")
      .filter((l) => !l.trim().startsWith("//") && !l.trim().startsWith("*"))
      .join("\n");
    // direction_filter IS sent now — it persists and is enforced.
    expect(code).toContain("direction_filter: direction");
    // vehicle is still NEVER sent: it is DERIVED from the strategy's
    // instrument_type, a fact about the strategy rather than a choice.
    expect(code).not.toContain("vehicle:");
  });
});

// ═══════════════════════════════════════════════════════════════════
// Risk legend + minimum capital stay in the panel (founder's ask)
// ═══════════════════════════════════════════════════════════════════
describe("risk context stays in the Deploy panel", () => {
  it("renders the risk legend with minimum capital", async () => {
    render(<SubscriptionSettings subscriptionId="s1" />);
    await waitFor(() => screen.getByTestId("risk-legend"));
    expect(screen.getByTestId("risk-legend")).toBeInTheDocument();
    expect(screen.getByTestId("min-capital-cash")).toBeInTheDocument();
    expect(screen.getByTestId("min-capital-futures")).toBeInTheDocument();
  });
});
