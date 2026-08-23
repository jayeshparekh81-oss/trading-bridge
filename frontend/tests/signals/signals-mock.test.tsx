/**
 * Phase-1a signal-feed mock UI — component tests.
 *
 * Safety-first: the top priority is locking in that the one-click confirm is a
 * NO-OP (no network request, no api.post) while the backend is unwired — so the
 * button can never place a real order today. Then the feed render, validity
 * countdown, and premium gate. Mirrors tests/billing style (vitest + RTL,
 * vi.mock for api + sonner).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// ── Mocks ────────────────────────────────────────────────────────────
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

// Guard: prove the confirm path never calls api.post (even though the component
// doesn't import it today — this fails loudly if someone wires it later).
vi.mock("@/lib/api", () => ({
  api: { post: vi.fn(), get: vi.fn(), patch: vi.fn() },
  ApiError: class ApiError extends Error {},
}));

// Re-export the real fixtures, but make MOCK_PAYWALLED switchable per test.
const gate = vi.hoisted(() => ({ paywalled: false }));
vi.mock("@/lib/mock/signals-mock", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/mock/signals-mock")>();
  return {
    ...actual,
    get MOCK_PAYWALLED() {
      return gate.paywalled;
    },
  };
});

import { toast } from "sonner";
import { api } from "@/lib/api";
import { MOCK_SIGNALS } from "@/lib/mock/signals-mock";
import { OneClickConfirmButton } from "@/components/signals/one-click-confirm-button";
import SignalsPage from "@/app/(dashboard)/signals/page";

const success = toast.success as ReturnType<typeof vi.fn>;
const post = api.post as ReturnType<typeof vi.fn>;

// ═══════════════════════════════════════════════════════════════════════
// 1. SAFETY-CRITICAL — one-click confirm is a NO-OP (cannot fire an order)
// ═══════════════════════════════════════════════════════════════════════
describe("OneClickConfirmButton — no-op safety", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.unstubAllGlobals());

  it("fires NO network request and only toasts the mock message", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    const sig = MOCK_SIGNALS[0];

    render(<OneClickConfirmButton signal={sig} />);
    // Two-step: open the confirm dialog, then confirm.
    fireEvent.click(screen.getByTestId(`confirm-${sig.id}`));
    fireEvent.click(await screen.findByTestId(`confirm-yes-${sig.id}`));

    await waitFor(() =>
      expect(success).toHaveBeenCalledWith(
        "Mock confirm — no order placed (backend not wired)",
      ),
    );
    // The whole point: nothing was placed.
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(post).not.toHaveBeenCalled();
  });

  it("does nothing until the explicit confirm click (opening the dialog alone places nothing)", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    const sig = MOCK_SIGNALS[0];

    render(<OneClickConfirmButton signal={sig} />);
    fireEvent.click(screen.getByTestId(`confirm-${sig.id}`)); // open only
    await screen.findByTestId(`confirm-yes-${sig.id}`);

    expect(success).not.toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(post).not.toHaveBeenCalled();
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 2 + 3. Feed render + validity display (via the page + real fixtures)
// ═══════════════════════════════════════════════════════════════════════
describe("SignalsPage — feed render + validity", () => {
  beforeEach(() => {
    gate.paywalled = false;
    vi.clearAllMocks();
  });

  it("renders the mock signals (symbol, side, entry/SL/target) + MOCK DATA badge", () => {
    const { container } = render(<SignalsPage />);
    const text = container.textContent ?? "";

    expect(text).toContain("Mock data"); // dev badge — never mistaken for live
    // symbols
    expect(text).toContain("BSE-JUL2026-FUT");
    expect(text).toContain("CDSL-JUL2026-FUT");
    expect(text).toContain("ANGELONE-JUL2026-FUT");
    // side badges
    expect(text).toContain("ENTRY");
    expect(text).toContain("EXIT");
    // entry / SL / target of signal 1
    expect(text).toContain("2437.50");
    expect(text).toContain("2402.00");
    expect(text).toContain("2510.00");
    // an active (pending, non-lapsed) signal shows the confirm button
    expect(screen.getByTestId("confirm-sig-mock-0001")).toBeInTheDocument();
  });

  it("computes the 5-min ENTRY countdown, EOD exit note, and Expired state", () => {
    const { container } = render(<SignalsPage />);
    const text = container.textContent ?? "";

    // sig-0001 received 1 min before the fixed anchor → 4:00 left.
    expect(text).toContain("4:00 left");
    // sig-0002 received 4 min before → 1:00 left (urgent).
    expect(text).toContain("1:00 left");
    // sig-0003 is an EXIT → valid till EOD, not an entry countdown.
    expect(text).toContain("Valid till EOD");
    // sig-0004 is past its 5-min entry window → Expired.
    expect(text).toContain("Expired");
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 4. Premium gate — paywalled → UpgradeWall, no active confirm button
// ═══════════════════════════════════════════════════════════════════════
describe("SignalsPage — premium gate", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => (gate.paywalled = false));

  it("shows the UpgradeWall (not the confirm button) when paywalled", () => {
    gate.paywalled = true;
    const { container } = render(<SignalsPage />);
    const text = container.textContent ?? "";

    // The B3 UpgradeWall renders "<feature> is a premium feature".
    expect(text).toMatch(/premium feature/i);
    // Per-row confirm buttons are replaced by a locked "Premium" chip.
    expect(screen.queryByTestId("confirm-sig-mock-0001")).toBeNull();
    expect(text).toContain("Premium");
  });

  it("shows the active confirm button when NOT paywalled", () => {
    gate.paywalled = false;
    render(<SignalsPage />);
    expect(screen.getByTestId("confirm-sig-mock-0001")).toBeInTheDocument();
  });
});
