/**
 * "Sab band" (kill switch) never shows a zero it did not read (founder's rule,
 * 26 Sep 2026, point 10). Before: a switch with no limit and no P&L read printed
 * "+₹0 / ₹0" and "0% of daily loss budget used" — three confident zeros about the
 * customer's safety net. Now: words for what is missing, and the confirm word is BAND.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

const status = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }));
vi.mock("@/shared/api/use-api", () => ({
  useApi: (url: string | null) => ({
    data: url === "/kill-switch/status" ? status.current : url === "/kill-switch/history" ? [] : null,
    isLoading: false, error: null, paywalled: false, paywallUrl: null, refetch: vi.fn(),
  }),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/kill-switch",
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

import KillSwitchPage from "@/app/(dashboard)/kill-switch/page";

afterEach(cleanup);

describe("Sab band — no fake zeros", () => {
  it("no limit + no P&L read → words, never '₹0 / ₹0' or '0% used'", () => {
    status.current = { state: "ACTIVE", enabled: true, daily_pnl: null, max_daily_loss_inr: "0", trades_today: 0, max_daily_trades: 0, tripped_at: null, trip_reason: null };
    render(<KillSwitchPage />);
    const body = document.body.textContent ?? "";
    expect(body).toContain("NOT MEASURED");
    expect(body).toContain("limit set nahi");
    expect(body).not.toMatch(/₹0\s*\/\s*₹0/);
    expect(body).not.toMatch(/0% of daily/);
    expect(screen.getByText(/Sab band karo/)).toBeTruthy();
  });

  it("a real read with a real limit shows the real numbers (falsification twin)", () => {
    status.current = { state: "ACTIVE", enabled: true, daily_pnl: "-5000", max_daily_loss_inr: "20000", trades_today: 3, max_daily_trades: 10, tripped_at: null, trip_reason: null };
    render(<KillSwitchPage />);
    const body = document.body.textContent ?? "";
    expect(body).toMatch(/25%/);
    expect(body).not.toContain("NOT MEASURED");
  });
});
