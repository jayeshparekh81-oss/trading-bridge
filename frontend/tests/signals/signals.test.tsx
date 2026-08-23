/**
 * Signal-feed wiring — component tests (real endpoints, PAPER-gated confirm).
 *
 * Safety-first: the top priority is proving the one-click confirm hits EXACTLY
 * the subscriber confirm endpoint — a single signal-scoped POST — and NEVER a
 * raw order / execute / direct-exit / square-off path, and that its toast says
 * PAPER (no real order). Then: feed render off the real shape, server-driven
 * validity display, empty-state, error-state, and the premium gate. Mirrors
 * tests/billing style (vitest + RTL, vi.mock for api + use-api + sonner).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// ── Mocks ────────────────────────────────────────────────────────────
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

// Real api client is mocked: assert exactly which endpoint the button calls.
// ApiError is a real class here so the 409 (lapsed) branch can be exercised.
vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    status: number;
    detail: string;
    data?: unknown;
    constructor(status: number, detail: string, data?: unknown) {
      super(detail);
      this.status = status;
      this.detail = detail;
      this.data = data;
    }
  }
  return { api: { post: vi.fn(), get: vi.fn(), patch: vi.fn() }, ApiError };
});

// The page's data source. A hoisted, per-test-mutable return value so each test
// drives loading / error / paywalled / signals without a real network call.
const apiState = vi.hoisted(() => ({
  current: {
    data: null as unknown,
    isLoading: false,
    error: null as string | null,
    paywalled: false,
    paywallUrl: null as string | null,
    refetch: vi.fn(),
  },
}));
vi.mock("@/lib/use-api", () => ({ useApi: () => apiState.current }));

import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import type { SubscriberSignal } from "@/lib/signals";
import { OneClickConfirmButton } from "@/components/signals/one-click-confirm-button";
import SignalsPage from "@/app/(dashboard)/signals/page";

const success = toast.success as ReturnType<typeof vi.fn>;
const info = toast.info as ReturnType<typeof vi.fn>;
const error = toast.error as ReturnType<typeof vi.fn>;
const warning = toast.warning as ReturnType<typeof vi.fn>;
const post = api.post as ReturnType<typeof vi.fn>;
const get = api.get as ReturnType<typeof vi.fn>;
const patch = api.patch as ReturnType<typeof vi.fn>;

// Raw money-moving paths the confirm button must NEVER touch.
const FORBIDDEN_PATHS = [
  "/orders",
  "/execute",
  "/execution",
  "/place",
  "/live",
  "/fanout",
  "/direct-exit",
  "/square-off",
  "/kill",
  "/webhook",
  "/trades",
  "/strategies/",
];

/** The confirm control must move money through NO other api method — a call
 *  routed via api.get/api.patch would otherwise slip past the post-only guards. */
function expectNoOtherApiCalls() {
  expect(get).not.toHaveBeenCalled();
  expect(patch).not.toHaveBeenCalled();
}

function makeSignal(overrides: Partial<SubscriberSignal> = {}): SubscriberSignal {
  return {
    id: "sig-1",
    listing_id: "list-1",
    listing_title: "Strategy S1",
    symbol: "BSE-JUL2026-FUT",
    action: "ENTRY",
    side: "buy",
    entry: "2437.50",
    stop_loss: "2402.00",
    target: "2510.00",
    received_at: "2026-08-23T06:30:00Z",
    status: "received",
    validity: {
      window: "entry",
      valid: true,
      expires_at: "2026-08-23T06:35:00Z",
      seconds_remaining: 240,
    },
    ...overrides,
  };
}

const confirmResult = {
  signal_id: "sig-1",
  subscription_id: "sub-1",
  status: "confirmed_paper" as const,
  placed_real: false,
  execution_id: "exec-1",
  broker_order_id: "PAPER-abc123",
  quantity: 4,
  price: "100",
  validity: makeSignal().validity,
  note: "PAPER confirmation (paper-gated; no real order placed).",
};

function setFeed(signals: SubscriberSignal[]) {
  apiState.current = {
    ...apiState.current,
    data: { signals, count: signals.length },
    isLoading: false,
    error: null,
    paywalled: false,
  };
}

// ═══════════════════════════════════════════════════════════════════════
// 1. SAFETY-CRITICAL — confirm hits EXACTLY the confirm endpoint (no raw path)
// ═══════════════════════════════════════════════════════════════════════
describe("OneClickConfirmButton — endpoint safety", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.unstubAllGlobals());

  it("POSTs exactly the confirm endpoint (no order/execute/exit path) and toasts PAPER", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    post.mockResolvedValueOnce(confirmResult);
    const sig = makeSignal();

    render(<OneClickConfirmButton signal={sig} />);
    // Two-step: open the confirm dialog, then confirm.
    fireEvent.click(screen.getByTestId(`confirm-${sig.id}`));
    fireEvent.click(await screen.findByTestId(`confirm-yes-${sig.id}`));

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));

    // EXACTLY the subscriber confirm endpoint — the signal id in the path, no body.
    expect(post).toHaveBeenCalledWith(
      "/marketplace/subscriptions/signals/sig-1/confirm",
    );
    const url = post.mock.calls[0][0] as string;
    expect(url).toMatch(/^\/marketplace\/subscriptions\/signals\/sig-1\/confirm$/);
    expect(post.mock.calls[0][1]).toBeUndefined(); // no request body
    // …and never a raw money-moving path.
    for (const bad of FORBIDDEN_PATHS) expect(url).not.toContain(bad);

    // PAPER-clear success toast.
    await waitFor(() =>
      expect(success).toHaveBeenCalledWith(
        "Paper confirmation ✓ — no real order placed",
        { description: confirmResult.note },
      ),
    );
    // No stray direct fetch, and nothing routed through another api method.
    expect(fetchSpy).not.toHaveBeenCalled();
    expectNoOtherApiCalls();
  });

  it("SAFETY: never claims 'no real order' when the server says placed_real=true", async () => {
    // Unreachable in this build (endpoint hardcodes placed_real=false), but the
    // UI's safety claim must track the SERVER's answer — not a hardcoded string.
    // This is the regression that would otherwise leave a real order reassured
    // as "paper".
    post.mockResolvedValueOnce({ ...confirmResult, placed_real: true });
    const sig = makeSignal();

    render(<OneClickConfirmButton signal={sig} />);
    fireEvent.click(screen.getByTestId(`confirm-${sig.id}`));
    fireEvent.click(await screen.findByTestId(`confirm-yes-${sig.id}`));

    await waitFor(() => expect(warning).toHaveBeenCalledTimes(1));
    // The paper reassurance must NOT be shown.
    expect(success).not.toHaveBeenCalled();
    expect(warning.mock.calls[0][0]).toMatch(/REAL order placed/i);
  });

  it("opening the dialog alone posts nothing (deliberate two-step)", async () => {
    const sig = makeSignal();
    render(<OneClickConfirmButton signal={sig} />);
    fireEvent.click(screen.getByTestId(`confirm-${sig.id}`)); // open only
    await screen.findByTestId(`confirm-yes-${sig.id}`);

    expect(post).not.toHaveBeenCalled();
    expect(success).not.toHaveBeenCalled();
  });

  it("already_confirmed → info toast (idempotent), still only the confirm endpoint", async () => {
    post.mockResolvedValueOnce({ ...confirmResult, status: "already_confirmed" });
    const sig = makeSignal();

    render(<OneClickConfirmButton signal={sig} />);
    fireEvent.click(screen.getByTestId(`confirm-${sig.id}`));
    fireEvent.click(await screen.findByTestId(`confirm-yes-${sig.id}`));

    await waitFor(() => expect(info).toHaveBeenCalledTimes(1));
    expect(success).not.toHaveBeenCalled();
    expect(post).toHaveBeenCalledWith(
      "/marketplace/subscriptions/signals/sig-1/confirm",
    );
  });

  it("409 lapsed → error toast, no retry elsewhere, no confirmed side effects", async () => {
    post.mockRejectedValueOnce(new ApiError(409, "Signal validity lapsed"));
    const onConfirmed = vi.fn();
    const sig = makeSignal();

    render(<OneClickConfirmButton signal={sig} onConfirmed={onConfirmed} />);
    fireEvent.click(screen.getByTestId(`confirm-${sig.id}`));
    fireEvent.click(await screen.findByTestId(`confirm-yes-${sig.id}`));

    await waitFor(() =>
      expect(error).toHaveBeenCalledWith("Signal window lapsed — cannot confirm"),
    );
    expect(success).not.toHaveBeenCalled();
    // A rejected confirm must not fall back to any other path or claim success.
    expect(post).toHaveBeenCalledTimes(1);
    expect(post).toHaveBeenCalledWith(
      "/marketplace/subscriptions/signals/sig-1/confirm",
    );
    expectNoOtherApiCalls();
    expect(onConfirmed).not.toHaveBeenCalled();
  });

  it("calls onConfirmed after a successful confirm (feed refetch)", async () => {
    post.mockResolvedValueOnce(confirmResult);
    const onConfirmed = vi.fn();
    const sig = makeSignal();

    render(<OneClickConfirmButton signal={sig} onConfirmed={onConfirmed} />);
    fireEvent.click(screen.getByTestId(`confirm-${sig.id}`));
    fireEvent.click(await screen.findByTestId(`confirm-yes-${sig.id}`));

    await waitFor(() => expect(onConfirmed).toHaveBeenCalledTimes(1));
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 2 + 3. Feed render + server-driven validity (via the page + mocked useApi)
// ═══════════════════════════════════════════════════════════════════════
describe("SignalsPage — feed render + validity", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders the real-shape signals (listing_title, action, entry/SL/target) — no mock badge", () => {
    setFeed([
      makeSignal(),
      makeSignal({
        id: "sig-2",
        listing_title: "Strategy S1",
        action: "EXIT",
        entry: null,
        stop_loss: null,
        target: null,
        validity: {
          window: "exit",
          valid: true,
          expires_at: "2026-08-23T10:00:00Z",
          seconds_remaining: 30000,
        },
      }),
      makeSignal({
        id: "sig-3",
        action: "ENTRY",
        validity: {
          window: "entry",
          valid: false,
          expires_at: "2026-08-23T06:35:00Z",
          seconds_remaining: 0,
        },
      }),
    ]);

    const { container } = render(<SignalsPage />);
    const text = container.textContent ?? "";

    expect(text).not.toContain("Mock data"); // the mock is gone
    expect(text).toContain("Strategy S1"); // listing_title (not strategy id)
    expect(text).toContain("BSE-JUL2026-FUT");
    expect(text).toContain("ENTRY");
    expect(text).toContain("EXIT");
    expect(text).toContain("2437.50"); // entry
    expect(text).toContain("2402.00"); // stop_loss
    expect(text).toContain("2510.00"); // target
    // an active (valid) signal shows the confirm button; a lapsed one does not
    expect(screen.getByTestId("confirm-sig-1")).toBeInTheDocument();
    expect(screen.queryByTestId("confirm-sig-3")).toBeNull();
  });

  it("shows server validity: entry countdown, EOD exit note, Expired — no client clock", () => {
    setFeed([
      makeSignal({ id: "sig-1", validity: { window: "entry", valid: true, expires_at: "x", seconds_remaining: 240 } }),
      makeSignal({ id: "sig-2", action: "EXIT", validity: { window: "exit", valid: true, expires_at: "x", seconds_remaining: 30000 } }),
      makeSignal({ id: "sig-3", validity: { window: "entry", valid: false, expires_at: "x", seconds_remaining: 0 } }),
    ]);
    const { container } = render(<SignalsPage />);
    const text = container.textContent ?? "";

    expect(text).toContain("4:00 left"); // 240s server snapshot, formatted
    expect(text).toContain("Valid till EOD"); // exit window
    expect(text).toContain("Expired"); // invalid validity
  });

  it("empty feed → clear empty-state (covers no-signals AND no-subscription)", () => {
    setFeed([]);
    const { container } = render(<SignalsPage />);
    const text = container.textContent ?? "";
    expect(text).toContain("No pending signals");
    expect(text).toContain("Marketplace");
  });

  it("error + no data → error card with Retry", () => {
    apiState.current = {
      ...apiState.current,
      data: null,
      isLoading: false,
      error: "Boom",
      paywalled: false,
    };
    const { container } = render(<SignalsPage />);
    const text = container.textContent ?? "";
    expect(text).toContain("Could not load signals");
    expect(text).toContain("Retry");
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 4. Premium gate — paywalled → UpgradeWall, per-row Premium chip (no button)
// ═══════════════════════════════════════════════════════════════════════
describe("SignalsPage — premium gate", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows the UpgradeWall (not the confirm button) when paywalled", () => {
    apiState.current = {
      ...apiState.current,
      data: { signals: [makeSignal()], count: 1 },
      isLoading: false,
      error: null,
      paywalled: true,
    };
    const { container } = render(<SignalsPage />);
    const text = container.textContent ?? "";

    expect(text).toMatch(/premium feature/i); // B3 UpgradeWall copy
    expect(screen.queryByTestId("confirm-sig-1")).toBeNull(); // no active button
    expect(text).toContain("Premium"); // locked chip
  });

  it("shows the active confirm button when NOT paywalled", () => {
    setFeed([makeSignal()]);
    render(<SignalsPage />);
    expect(screen.getByTestId("confirm-sig-1")).toBeInTheDocument();
  });
});
