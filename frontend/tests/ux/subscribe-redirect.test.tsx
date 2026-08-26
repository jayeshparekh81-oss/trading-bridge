/**
 * STEP 2 — subscribe must not end in a toast (audit finding #1).
 *
 * The dead end was the single biggest reason the journey felt unfindable:
 * you paid, got a toast, and were left on the listing page with no next step.
 * Both success paths (free/unconfigured-gateway and paid-after-polling) must
 * route to My Strategies, carrying the new subscription id so the row can be
 * highlighted.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));
vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    status: number; detail: string;
    constructor(s: number, d: string) { super(d); this.status = s; this.detail = d; }
  }
  return { api: { post: vi.fn(), get: vi.fn(), patch: vi.fn() }, ApiError };
});
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: { id: "u1", role: "user" } }) }));
vi.mock("@/lib/analytics", () => ({ trackEventSync: vi.fn() }));
vi.mock("@/lib/billing/razorpay", () => ({ openSubscriptionCheckout: vi.fn() }));

import { api } from "@/lib/api";
import { SubscribeButton } from "@/components/marketplace/subscribe-button";

const post = api.post as ReturnType<typeof vi.fn>;

beforeEach(() => { vi.clearAllMocks(); });

function renderBtn() {
  return render(
    <SubscribeButton
      listingId="listing-1"
      priceInr={0}
      isCreator={false}
      subscriptionStatus={null}
      onChange={vi.fn()}
    />,
  );
}

describe("free subscribe (doFreeSubscribe — the genuine Rs 0 path)", () => {
  it("redirects to My Strategies with the new subscription id", async () => {
    post.mockResolvedValueOnce({ id: "sub-42", requires_payment: false });
    renderBtn();
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(push).toHaveBeenCalledTimes(1));
    expect(push).toHaveBeenCalledWith("/marketplace/me?sub=sub-42");
  });

  it("does NOT leave the user on the listing page", async () => {
    post.mockResolvedValueOnce({ id: "sub-9", requires_payment: false });
    renderBtn();
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(push).toHaveBeenCalled());
    const target = push.mock.calls[0][0] as string;
    expect(target).toContain("/marketplace/me");
    expect(target).not.toContain("/marketplace/listing-1");
  });
});

describe("the redirect target", () => {
  it("carries ?sub= so the row can be highlighted", async () => {
    post.mockResolvedValueOnce({ id: "sub-77", requires_payment: false });
    renderBtn();
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(push).toHaveBeenCalled());
    expect(push.mock.calls[0][0]).toMatch(/\?sub=sub-77$/);
  });
});
