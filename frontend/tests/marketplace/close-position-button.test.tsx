/**
 * Emergency-exit control.
 *
 * Two properties matter most:
 *  1. Two-step confirm — opening the dialog must place/close nothing.
 *  2. PAPER vs REAL wording is DERIVED FROM THE SERVER (`placed_real`), never
 *     hardcoded. This is the exact catch from the take-trade toast: a
 *     hardcoded "no real order" line keeps reassuring after the real path is
 *     switched on.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

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
  return { api: { post: vi.fn(), get: vi.fn(), patch: vi.fn() }, ApiError };
});

import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { ClosePositionButton } from "@/components/marketplace/close-position-button";

const post = api.post as ReturnType<typeof vi.fn>;
const success = toast.success as ReturnType<typeof vi.fn>;
const error = toast.error as ReturnType<typeof vi.fn>;
const info = toast.info as ReturnType<typeof vi.fn>;

const SUB = "sub-1";
const POS = "pos-1";

const ok = {
  subscription_id: SUB,
  status: "closed",
  placed_real: false,
  positions: [
    { position_id: POS, symbol: "BSE-AUG2026-FUT", outcome: "closed", quantity_closed: 2 },
  ],
  errors: [],
  note: "PAPER close — no real broker order was placed.",
};

function renderBtn(props = {}) {
  return render(
    <ClosePositionButton
      subscriptionId={SUB}
      positionId={POS}
      symbol="BSE-AUG2026-FUT"
      {...props}
    />,
  );
}

async function clickThrough() {
  fireEvent.click(screen.getByTestId(`close-position-${POS}`));
  fireEvent.click(await screen.findByTestId(`close-position-yes-${POS}`));
}

beforeEach(() => vi.clearAllMocks());

describe("two-step confirm", () => {
  it("opening the dialog alone closes nothing", async () => {
    renderBtn();
    fireEvent.click(screen.getByTestId(`close-position-${POS}`));
    await screen.findByTestId(`close-position-yes-${POS}`);
    expect(post).not.toHaveBeenCalled();
  });

  it("posts exactly the close endpoint with the position id", async () => {
    post.mockResolvedValueOnce(ok);
    renderBtn();
    await clickThrough();

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(post).toHaveBeenCalledWith(
      `/marketplace/subscriptions/${SUB}/close-position`,
      { position_id: POS },
    );
    const url = post.mock.calls[0][0] as string;
    for (const bad of ["/orders", "/execute", "/square-off", "/kill"]) {
      expect(url).not.toContain(bad);
    }
  });
});

describe("PAPER vs REAL wording comes from the server", () => {
  it("paper close says PAPER and no real order", async () => {
    post.mockResolvedValueOnce({ ...ok, placed_real: false });
    renderBtn();
    await clickThrough();

    await waitFor(() => expect(success).toHaveBeenCalledTimes(1));
    expect(success.mock.calls[0][0]).toMatch(/PAPER/);
    expect(success.mock.calls[0][0]).toMatch(/koi real order nahi/i);
  });

  it("REAL close must NOT claim it was paper", async () => {
    // The regression that matters: server says a real order went out.
    post.mockResolvedValueOnce({ ...ok, placed_real: true });
    renderBtn();
    await clickThrough();

    await waitFor(() => expect(success).toHaveBeenCalledTimes(1));
    const title = success.mock.calls[0][0] as string;
    expect(title).toMatch(/REAL/);
    expect(title).not.toMatch(/PAPER/);
    expect(title).not.toMatch(/koi real order nahi/i);
  });
});

describe("partial + failure are never dressed as success", () => {
  it.each(["partial", "failed"])("%s → error toast naming the broker", async (st) => {
    post.mockResolvedValueOnce({
      ...ok, status: st, placed_real: false,
      positions: [{ ...ok.positions[0], outcome: "not_closed", quantity_closed: 0 }],
      errors: ["broker rejected close"],
    });
    renderBtn();
    await clickThrough();

    await waitFor(() => expect(error).toHaveBeenCalledTimes(1));
    expect(success).not.toHaveBeenCalled();
    expect(error.mock.calls[0][0]).toMatch(/broker check karo/i);
    expect(error.mock.calls[0][1].description).toContain("broker rejected close");
  });
});

describe("benign + guard states", () => {
  it("dormant → info, not success", async () => {
    post.mockResolvedValueOnce({ ...ok, status: "dormant" });
    renderBtn();
    await clickThrough();
    await waitFor(() => expect(info).toHaveBeenCalledTimes(1));
    expect(success).not.toHaveBeenCalled();
  });

  it("already_flat → info, not success", async () => {
    post.mockResolvedValueOnce({ ...ok, status: "already_flat" });
    renderBtn();
    await clickThrough();
    await waitFor(() => expect(info).toHaveBeenCalledTimes(1));
    expect(success).not.toHaveBeenCalled();
  });

  it("409 (close already in progress) → error, no success", async () => {
    post.mockRejectedValueOnce(new ApiError(409, "in progress"));
    renderBtn();
    await clickThrough();
    await waitFor(() => expect(error).toHaveBeenCalledTimes(1));
    expect(error.mock.calls[0][0]).toMatch(/pehle se chal raha/i);
    expect(success).not.toHaveBeenCalled();
  });

  it("503 (fail-closed) says nothing was closed", async () => {
    post.mockRejectedValueOnce(new ApiError(503, "no redis"));
    renderBtn();
    await clickThrough();
    await waitFor(() => expect(error).toHaveBeenCalledTimes(1));
    expect(error.mock.calls[0][1].description).toMatch(/kuch band nahi hua/i);
  });

  it("calls onClosed after a successful close", async () => {
    post.mockResolvedValueOnce(ok);
    const onClosed = vi.fn();
    renderBtn({ onClosed });
    await clickThrough();
    await waitFor(() => expect(onClosed).toHaveBeenCalledTimes(1));
  });

  it("does NOT call onClosed when the request fails", async () => {
    post.mockRejectedValueOnce(new ApiError(500, "boom"));
    const onClosed = vi.fn();
    renderBtn({ onClosed });
    await clickThrough();
    await waitFor(() => expect(error).toHaveBeenCalled());
    expect(onClosed).not.toHaveBeenCalled();
  });
});
