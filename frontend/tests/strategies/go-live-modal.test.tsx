/**
 * Go-Live modal — safety-fix #3 paper-mode gate tests.
 *
 * The modal uses ``useSystemMode`` to read the platform's master
 * paper-mode flag. When ``paper_mode=true``:
 *
 *   - the yellow "paper-mode locked" banner inside the modal renders,
 *   - the dry-run toggle is disabled (``aria-disabled=true``,
 *     ``disabled=true``) with a Hinglish/English tooltip,
 *   - ``dryRun`` is force-reset to ``true`` so the Confirm button
 *     stays on the "Test Order" branch and cannot submit a live
 *     order.
 *
 * Regression branch — when ``paper_mode=false`` the modal behaves
 * exactly as before: no banner, toggle interactive.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { GoLiveModal } from "@/components/strategies/go-live-modal";

// ── Mocks ─────────────────────────────────────────────────────────────

vi.mock("sonner", () => ({
  toast: { info: vi.fn(), error: vi.fn(), success: vi.fn() },
}));

vi.mock("@/lib/api", () => ({
  api: { post: vi.fn() },
  ApiError: class ApiError extends Error {
    status = 0;
    detail = "";
    data = undefined as unknown;
  },
}));

const mockSystemMode = vi.hoisted(() => vi.fn());
vi.mock("@/hooks/useSystemMode", () => ({
  useSystemMode: mockSystemMode,
}));

// ── Common props ──────────────────────────────────────────────────────

const baseProps = {
  open: true,
  onOpenChange: vi.fn(),
  strategyId: "00000000-0000-0000-0000-000000000001",
  strategyName: "Test Strategy",
  preflight: null,
  onResult: vi.fn(),
};

beforeEach(() => {
  vi.clearAllMocks();
});

// ── Tests ─────────────────────────────────────────────────────────────

describe("GoLiveModal paper-mode gate", () => {
  it("shows the paper-mode banner and disables the dry-run toggle when paper_mode=true", () => {
    mockSystemMode.mockReturnValue({
      paper_mode: true,
      kill_switch_check_enabled: true,
      circuit_breaker_enabled: true,
    });

    render(<GoLiveModal {...baseProps} />);

    // Banner is rendered.
    const banner = screen.getByTestId("paper-mode-locked-banner");
    expect(banner).toBeInTheDocument();
    expect(banner.textContent ?? "").toMatch(/paper mode active/i);
    expect(banner.textContent ?? "").toMatch(/july 2026/i);

    // Dry-run toggle is disabled. Its semantic switch role carries
    // ``aria-disabled=true`` and a Hinglish tooltip.
    const toggle = screen.getByTestId("dry-run-toggle");
    expect(toggle).toBeDisabled();
    expect(toggle).toHaveAttribute("aria-disabled", "true");
    expect(toggle.getAttribute("title") ?? "").toMatch(/paper mode/i);
    expect(toggle.getAttribute("title") ?? "").toMatch(/july 2026/i);

    // Toggle reflects dry-run = true (paper mode forces test path).
    expect(toggle).toHaveAttribute("aria-checked", "true");
  });

  it("hides the banner and enables the toggle when paper_mode=false (regression)", () => {
    mockSystemMode.mockReturnValue({
      paper_mode: false,
      kill_switch_check_enabled: true,
      circuit_breaker_enabled: true,
    });

    render(<GoLiveModal {...baseProps} />);

    expect(
      screen.queryByTestId("paper-mode-locked-banner"),
    ).not.toBeInTheDocument();

    const toggle = screen.getByTestId("dry-run-toggle");
    expect(toggle).not.toBeDisabled();
    expect(toggle).toHaveAttribute("aria-disabled", "false");
  });

  it("treats null system-mode (loading / fetch failed) as paper mode (defensive default)", () => {
    mockSystemMode.mockReturnValue(null);

    render(<GoLiveModal {...baseProps} />);

    expect(
      screen.getByTestId("paper-mode-locked-banner"),
    ).toBeInTheDocument();
    const toggle = screen.getByTestId("dry-run-toggle");
    expect(toggle).toBeDisabled();
  });
});
