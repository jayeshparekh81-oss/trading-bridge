import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SubscribeButton } from "@/components/marketplace/subscribe-button";

// ── Module mocks ─────────────────────────────────────────────────────
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
  return { api: { post: vi.fn(), get: vi.fn(), delete: vi.fn() }, ApiError };
});

vi.mock("@/lib/billing/razorpay", () => ({
  openSubscriptionCheckout: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { id: "u1", email: "trader@x.com" } }),
}));

vi.mock("@/lib/analytics", () => ({ trackEventSync: vi.fn() }));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

import { api } from "@/lib/api";
import { openSubscriptionCheckout } from "@/lib/billing/razorpay";

const post = api.post as ReturnType<typeof vi.fn>;
const openCheckout = openSubscriptionCheckout as ReturnType<typeof vi.fn>;

describe("SubscribeButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("hides itself for the listing creator", () => {
    const { container } = render(
      <SubscribeButton
        listingId="l1"
        priceInr={499}
        isCreator
        subscriptionStatus={null}
        onChange={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("free listing subscribes directly (no checkout)", async () => {
    post.mockResolvedValueOnce({});
    const onChange = vi.fn();
    render(
      <SubscribeButton
        listingId="l1"
        priceInr={0}
        isCreator={false}
        subscriptionStatus={null}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Subscribe — FREE/i }));
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(post).toHaveBeenCalledWith("/marketplace/listings/l1/subscribe", {});
    expect(openCheckout).not.toHaveBeenCalled();
    await waitFor(() => expect(onChange).toHaveBeenCalled());
  });

  it("paid listing opens Razorpay checkout with the PUBLIC key + sub id", async () => {
    post.mockResolvedValueOnce({
      id: "sub-row",
      requires_payment: true,
      razorpay_subscription_id: "sub_TEST",
      razorpay_key_id: "rzp_test_PUBLIC",
      razorpay_short_url: "https://rzp.test/x",
      status: "pending",
    });
    render(
      <SubscribeButton
        listingId="l9"
        priceInr={499}
        isCreator={false}
        subscriptionStatus={null}
        onChange={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Subscribe — ₹499/i }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/marketplace/listings/l9/subscribe", {}));
    await waitFor(() => expect(openCheckout).toHaveBeenCalledTimes(1));
    const arg = openCheckout.mock.calls[0][0];
    expect(arg.keyId).toBe("rzp_test_PUBLIC");
    expect(arg.subscriptionId).toBe("sub_TEST");
  });

  it("paid listing with gateway unconfigured (requires_payment=false) skips checkout", async () => {
    post.mockResolvedValueOnce({
      id: "sub-row",
      requires_payment: false,
      razorpay_subscription_id: null,
      razorpay_key_id: null,
      razorpay_short_url: null,
      status: "active",
    });
    const onChange = vi.fn();
    render(
      <SubscribeButton
        listingId="l9"
        priceInr={499}
        isCreator={false}
        subscriptionStatus={null}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Subscribe — ₹499/i }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(openCheckout).not.toHaveBeenCalled();
    await waitFor(() => expect(onChange).toHaveBeenCalled());
  });

  it("pending status shows a payment-processing state with Resume", () => {
    render(
      <SubscribeButton
        listingId="l1"
        priceInr={499}
        isCreator={false}
        subscriptionStatus="pending"
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText(/Payment processing/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Resume payment/i })).toBeInTheDocument();
  });

  it("active status shows the manage/cancel button", () => {
    render(
      <SubscribeButton
        listingId="l1"
        priceInr={499}
        isCreator={false}
        subscriptionStatus="active"
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /Subscribed — Cancel/i })).toBeInTheDocument();
  });
});
