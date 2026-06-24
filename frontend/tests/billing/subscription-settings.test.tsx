import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import {
  validateLotsOverride,
  EXECUTION_MODES,
} from "@/lib/billing/subscription-settings";
import { SubscriptionSettings } from "@/components/marketplace/subscription-settings";

// ── Pure validation (the even / min-2 sizing rule) ───────────────────
describe("validateLotsOverride", () => {
  it("accepts blank (use listing default)", () => {
    expect(validateLotsOverride(null)).toBeNull();
    expect(validateLotsOverride(undefined)).toBeNull();
  });
  it("rejects below the minimum of 2", () => {
    expect(validateLotsOverride(1)).toMatch(/Minimum/i);
  });
  it("rejects odd numbers (must be even)", () => {
    expect(validateLotsOverride(3)).toMatch(/even/i);
    expect(validateLotsOverride(5)).toMatch(/even/i);
  });
  it("rejects above the maximum of 20", () => {
    expect(validateLotsOverride(22)).toMatch(/Maximum/i);
  });
  it("accepts valid even values 2..20", () => {
    for (const n of [2, 4, 6, 8, 10, 20]) {
      expect(validateLotsOverride(n)).toBeNull();
    }
  });
  it("defaults paper first in the execution-mode list", () => {
    expect(EXECUTION_MODES[0]).toBe("paper");
  });
});

// ── Component: validation + PATCH + preview state ────────────────────
vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    status: number;
    detail: string;
    constructor(status: number, detail: string) {
      super(detail);
      this.status = status;
      this.detail = detail;
    }
  }
  return { api: { get: vi.fn(), patch: vi.fn() }, ApiError };
});

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

import { api } from "@/lib/api";
import { toast } from "sonner";

const get = api.get as ReturnType<typeof vi.fn>;
const patch = api.patch as ReturnType<typeof vi.fn>;

const PREVIEW_SETTINGS = {
  subscription_id: "s1",
  lots_override: null,
  execution_mode: "paper",
  is_paper: true,
  applied: false,
  pending_fanout_merge: true,
};

describe("SubscriptionSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    get.mockResolvedValue(PREVIEW_SETTINGS);
  });

  it("renders the paper-only preview banner when not yet persisted", async () => {
    render(<SubscriptionSettings subscriptionId="s1" />);
    await waitFor(() =>
      expect(screen.getByTestId("subscription-settings")).toBeInTheDocument(),
    );
    expect(screen.getByText(/Preview/i)).toBeInTheDocument();
  });

  it("blocks save on an odd lots value and shows the even-number error", async () => {
    render(<SubscriptionSettings subscriptionId="s1" />);
    await waitFor(() => screen.getByTestId("lots-override-input"));

    fireEvent.change(screen.getByTestId("lots-override-input"), {
      target: { value: "3" },
    });
    expect(screen.getByTestId("lots-error")).toHaveTextContent(/even/i);
    expect(screen.getByTestId("save-settings")).toBeDisabled();
    expect(patch).not.toHaveBeenCalled();
  });

  it("PATCHes valid even lots + execution mode and toasts the preview note", async () => {
    patch.mockResolvedValueOnce({ ...PREVIEW_SETTINGS, lots_override: 4 });
    render(<SubscriptionSettings subscriptionId="s1" />);
    await waitFor(() => screen.getByTestId("lots-override-input"));

    fireEvent.change(screen.getByTestId("lots-override-input"), {
      target: { value: "4" },
    });
    expect(screen.queryByTestId("lots-error")).toBeNull();

    fireEvent.click(screen.getByTestId("save-settings"));
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    const [url, body] = patch.mock.calls[0];
    expect(url).toBe("/marketplace/subscriptions/s1/settings");
    expect(body).toMatchObject({ lots_override: 4, execution_mode: "paper", is_paper: true });
    // applied=false → preview/info toast, not the "saved" success.
    await waitFor(() => expect(toast.info).toHaveBeenCalled());
  });
});
