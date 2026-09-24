/**
 * AccountTruthCard — the honesty mechanics, each asserted:
 *   - the flag is OFF unless NEXT_PUBLIC_CUSTOMER_DASHBOARD is exactly "1";
 *   - PROTECTED / UNPROTECTED / FLAT / NOT MEASURED each render their own word,
 *     NOT MEASURED is never green and never a spinner;
 *   - "last verified" is the measured age or NOT MEASURED, never "just now";
 *   - the one-tap posts ONE declaration and shows the backend's own message;
 *     it never says the position is closed;
 *   - loading / error states render without fabricating data.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import {
  customerDashboardEnabled,
  oneTapAvailable,
  truthHeadline,
  truthTone,
  verifiedAgo,
  type TruthCard,
} from "@/lib/account-truth";

const responses: Record<string, unknown> = {};
let loading = false;
let failing = false;
const refetch = vi.fn();
const post = vi.fn();
const toastSuccess = vi.fn();
const toastError = vi.fn();

vi.mock("@/shared/api/use-api", () => ({
  useApi: (url: string | null) => ({
    data: url && !loading && !failing ? (responses[url] ?? null) : null,
    isLoading: loading,
    error: failing ? "boom" : null,
    paywalled: false,
    paywallUrl: null,
    refetch,
  }),
}));
vi.mock("@/shared/api/client", () => ({
  api: { post: (...a: unknown[]) => post(...a) },
  ApiError: class ApiError extends Error {
    detail: unknown;
    constructor(d: unknown) {
      super("api");
      this.detail = d;
    }
  },
}));
vi.mock("sonner", () => ({ toast: { success: (...a: unknown[]) => toastSuccess(...a), error: (...a: unknown[]) => toastError(...a) } }));

import { AccountTruthCard } from "@/components/marketplace/account-truth-card";

const base: TruthCard = {
  account_key: "acct-x",
  verdict: "PROTECTED",
  position: { symbol: "BSE-OCT2026-FUT", security_id: "48776", side: "short", quantity: 400 },
  stop: { exists: true, order_id: "23132609221238", side: "buy", quantity: 400, trigger_price: 3249.9, security_id: "48776" },
  verified_at: "2026-09-25T04:17:00+00:00",
  age_s: 90,
  source: "GET /v2/forever/orders",
  reason: "resting stop verified at the broker",
  line: "Position khuli …",
  next_step_hi: "Kuch karna nahi hai — stop broker par hai.",
};
const URL = "/customer-lane/dashboard/truth";

function mount() {
  return render(<AccountTruthCard subscriptionId="sub-1" symbol="BSE-OCT2026-FUT" storedQuantity={400} />);
}

beforeEach(() => {
  loading = false;
  failing = false;
  refetch.mockReset();
  post.mockReset();
  toastSuccess.mockReset();
  toastError.mockReset();
  for (const k of Object.keys(responses)) delete responses[k];
  responses[URL] = base;
});

describe("flag", () => {
  it("is OFF unless NEXT_PUBLIC_CUSTOMER_DASHBOARD is exactly 1", () => {
    const prev = process.env.NEXT_PUBLIC_CUSTOMER_DASHBOARD;
    delete process.env.NEXT_PUBLIC_CUSTOMER_DASHBOARD;
    expect(customerDashboardEnabled()).toBe(false);
    process.env.NEXT_PUBLIC_CUSTOMER_DASHBOARD = "true";
    expect(customerDashboardEnabled()).toBe(false);
    process.env.NEXT_PUBLIC_CUSTOMER_DASHBOARD = "1";
    expect(customerDashboardEnabled()).toBe(true);
    if (prev === undefined) delete process.env.NEXT_PUBLIC_CUSTOMER_DASHBOARD;
    else process.env.NEXT_PUBLIC_CUSTOMER_DASHBOARD = prev;
  });
});

describe("pure helpers", () => {
  it("NOT MEASURED is neither green nor red", () => {
    expect(truthTone("NOT MEASURED")).toBe("unknown");
    expect(truthTone("PROTECTED")).toBe("ok");
    expect(truthTone("UNPROTECTED")).toBe("danger");
    expect(truthTone("FLAT")).toBe("muted");
    expect(truthHeadline("NOT MEASURED")).toContain("NOT MEASURED");
  });
  it("verified age is measured or NOT MEASURED, never 'just now'", () => {
    expect(verifiedAgo(45)).toBe("45s pehle");
    expect(verifiedAgo(90)).toBe("2 min pehle");
    expect(verifiedAgo(600)).toBe("10 min pehle");
    expect(verifiedAgo(null)).toBe("NOT MEASURED");
    expect(verifiedAgo(-5)).toBe("NOT MEASURED");
  });
  it("one-tap only when there is a position to declare on", () => {
    expect(oneTapAvailable(base)).toBe(true);
    expect(oneTapAvailable({ ...base, verdict: "FLAT", position: null })).toBe(false);
    expect(oneTapAvailable(null)).toBe(false);
  });
});

describe("states", () => {
  it("renders PROTECTED with the position, the stop order and the measured age", () => {
    mount();
    const card = screen.getByTestId("truth-card");
    expect(card.getAttribute("data-verdict")).toBe("PROTECTED");
    expect(screen.getByTestId("truth-headline").textContent).toBe("Stop broker par hai");
    expect(screen.getByTestId("truth-position").textContent).toContain("short 400 BSE-OCT2026-FUT");
    expect(screen.getByTestId("truth-verified").textContent).toContain("2 min pehle");
    expect(screen.getByTestId("truth-verified").textContent).toContain("23132609221238");
  });
  it("renders UNPROTECTED as the only danger, with what to DO", () => {
    responses[URL] = { ...base, verdict: "UNPROTECTED", stop: { exists: false }, next_step_hi: "Abhi Dhan app kholo: stop lagao ya position band karo." };
    mount();
    expect(screen.getByTestId("truth-headline").textContent).toContain("NAHI mila");
    expect(screen.getByTestId("truth-next-step").textContent).toContain("Dhan app");
  });
  it("renders NOT MEASURED as its own state and hides nothing behind a spinner", () => {
    responses[URL] = { ...base, verdict: "NOT MEASURED", stop: null, age_s: null, next_step_hi: "Dhan app me khud dekh lo." };
    mount();
    expect(screen.getByTestId("truth-card").getAttribute("data-verdict")).toBe("NOT MEASURED");
    expect(screen.getByTestId("truth-verified").textContent).toContain("NOT MEASURED");
    expect(screen.queryByTestId("truth-loading")).toBeNull();
  });
  it("renders FLAT without the one-tap", () => {
    responses[URL] = { ...base, verdict: "FLAT", position: null, stop: null };
    mount();
    expect(screen.getByTestId("truth-headline").textContent).toContain("Koi position");
    expect(screen.queryByTestId("one-tap-manual-exit")).toBeNull();
  });
  it("loading and error each render their own state", () => {
    loading = true;
    mount();
    expect(screen.getByTestId("truth-loading")).toBeTruthy();
    loading = false;
    failing = true;
    mount();
    expect(screen.getByTestId("truth-error").textContent).toContain("Dhan app");
  });
});

describe("one-tap", () => {
  it("posts ONE declaration and shows the backend's message; never says closed", async () => {
    post.mockResolvedValue({ subscription_id: "sub-1", flipped: true, previous_mode: "auto", new_mode: "offline",
      message_hi: "Samajh gaye — strategy ab is position par koi order nahi bhejegi, sirf suchna.", audit_log_id: "a1" });
    mount();
    fireEvent.click(screen.getByTestId("one-tap-manual-exit"));
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(post.mock.calls[0][0]).toBe("/customer-lane/dashboard/manual-exit");
    expect(post.mock.calls[0][1]).toMatchObject({ subscription_id: "sub-1", symbol: "BSE-OCT2026-FUT", stored_quantity: 400 });
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledTimes(1));
    const msg = String(toastSuccess.mock.calls[0][0]);
    expect(msg).toContain("suchna");
    expect(msg.toLowerCase()).not.toContain("band ho gaya");
    expect(refetch).toHaveBeenCalled();
  });
  it("a failed post says what to do, not what failed", async () => {
    post.mockRejectedValue(new Error("network"));
    mount();
    fireEvent.click(screen.getByTestId("one-tap-manual-exit"));
    await waitFor(() => expect(toastError).toHaveBeenCalledTimes(1));
    expect(String(toastError.mock.calls[0][0])).toContain("phir dabao");
  });
});
