/**
 * STEP 4 — the StrykeX rule, made operable: PAUSE first, THEN close.
 *
 * A customer who closes by hand without pausing leaves the system free to act
 * on the next exit signal. StrykeX tells users this plainly; we had the
 * machinery (execution_mode) and never surfaced it.
 *
 * Also pinned here: Close renders ONLY when there is an open position — never
 * a disabled one — and the PAPER-vs-REAL wording stays server-derived.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
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
  return { api: { patch: vi.fn(), post: vi.fn(), get: vi.fn() }, ApiError };
});

import { toast } from "sonner";
import { api } from "@/lib/api";
import {
  PauseDeploymentButton,
  PAUSED_MODE,
  RUNNING_MODE,
} from "@/components/marketplace/pause-deployment-button";

const patch = api.patch as ReturnType<typeof vi.fn>;
const success = toast.success as ReturnType<typeof vi.fn>;
const ME_PAGE = readFileSync(
  join(process.cwd(), "src/app/(dashboard)/marketplace/me/page.tsx"), "utf8");

beforeEach(() => vi.clearAllMocks());

// ═══════════════════════════════════════════════════════════════════
// Pause uses the EXISTING execution_mode column — no invented field
// ═══════════════════════════════════════════════════════════════════
describe("Pause", () => {
  it("pausing PATCHes execution_mode to offline", async () => {
    patch.mockResolvedValueOnce({ execution_mode: PAUSED_MODE, applied: true });
    render(<PauseDeploymentButton subscriptionId="s1" mode={RUNNING_MODE} />);

    fireEvent.click(screen.getByTestId("pause-s1"));
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));

    expect(patch).toHaveBeenCalledWith(
      "/marketplace/subscriptions/s1/settings",
      { execution_mode: "offline" },
    );
  });

  it("resuming PATCHes back to auto", async () => {
    patch.mockResolvedValueOnce({ execution_mode: RUNNING_MODE, applied: true });
    render(<PauseDeploymentButton subscriptionId="s1" mode={PAUSED_MODE} />);
    fireEvent.click(screen.getByTestId("pause-s1"));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch.mock.calls[0][1]).toEqual({ execution_mode: "auto" });
  });

  it("shows Pause when running and Resume when paused", () => {
    const { unmount } = render(
      <PauseDeploymentButton subscriptionId="s1" mode={RUNNING_MODE} />);
    expect(screen.getByTestId("pause-s1").textContent).toContain("Pause");
    unmount();
    render(<PauseDeploymentButton subscriptionId="s2" mode={PAUSED_MODE} />);
    expect(screen.getByTestId("pause-s2").textContent).toContain("Resume");
  });

  it("treats any non-auto mode as paused", () => {
    render(<PauseDeploymentButton subscriptionId="s3" mode="one_click" />);
    expect(screen.getByTestId("pause-s3").textContent).toContain("Resume");
  });

  it("reports the SERVER's mode, not the one we asked for", async () => {
    // Server refuses the pause and answers 'auto' — we must not claim paused.
    patch.mockResolvedValueOnce({ execution_mode: "auto", applied: true });
    render(<PauseDeploymentButton subscriptionId="s1" mode={RUNNING_MODE} />);
    fireEvent.click(screen.getByTestId("pause-s1"));
    await waitFor(() => expect(success).toHaveBeenCalled());
    expect(success.mock.calls[0][0]).toMatch(/Resumed/);
    expect(success.mock.calls[0][0]).not.toMatch(/Paused/);
  });

  it("tells the customer nothing auto-executes while paused", async () => {
    patch.mockResolvedValueOnce({ execution_mode: PAUSED_MODE });
    render(<PauseDeploymentButton subscriptionId="s1" mode={RUNNING_MODE} />);
    fireEvent.click(screen.getByTestId("pause-s1"));
    await waitFor(() => expect(success).toHaveBeenCalled());
    expect(success.mock.calls[0][0]).toMatch(/koi order apne aap nahi/i);
  });
});

// ═══════════════════════════════════════════════════════════════════
// ⚠️ ORDER + GATING on the row
// ═══════════════════════════════════════════════════════════════════
describe("the row wires Pause BEFORE Close", () => {
  it("renders Pause earlier in the markup than Close", () => {
    const pauseAt = ME_PAGE.indexOf("<PauseDeploymentButton");
    const closeAt = ME_PAGE.indexOf("<ClosePositionButton");
    expect(pauseAt).toBeGreaterThan(-1);
    expect(closeAt).toBeGreaterThan(-1);
    expect(pauseAt).toBeLessThan(closeAt);
  });

  it("Close renders ONLY when there is an open position", () => {
    expect(ME_PAGE).toContain("configurable && sub.open_position ? (");
  });

  it("passes the real position id, not the subscription id", () => {
    expect(ME_PAGE).toContain("positionId={sub.open_position.id}");
  });

  it("no disabled Close is ever rendered", () => {
    // The null branch must render nothing at all.
    const seg = ME_PAGE.slice(ME_PAGE.indexOf("<ClosePositionButton"));
    expect(seg.slice(0, 400)).not.toContain("disabled");
  });
});

// ═══════════════════════════════════════════════════════════════════
// PAPER vs REAL stays server-derived (unchanged from step 4's build)
// ═══════════════════════════════════════════════════════════════════
describe("close copy stays server-derived", () => {
  it("reads placed_real from the response", () => {
    const src = readFileSync(
      join(process.cwd(), "src/components/marketplace/close-position-button.tsx"),
      "utf8");
    expect(src).toContain("res.placed_real");
  });
});
