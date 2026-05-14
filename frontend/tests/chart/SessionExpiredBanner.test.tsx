/**
 * SessionExpiredBanner — B9 unit tests.
 *
 * The banner is a pure render component: copy + a single primary
 * CTA that routes to /login. Coverage focuses on the click path
 * (default uses next/navigation router; ``onLogin`` prop overrides)
 * and the Hinglish copy assertion so a future copy change is a
 * deliberate diff.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

// eslint-disable-next-line import/first
import { SessionExpiredBanner } from "@/components/chart/SessionExpiredBanner";

describe("SessionExpiredBanner", () => {
  it("renders the Hinglish title + description + login CTA", () => {
    render(<SessionExpiredBanner />);

    expect(
      screen.getByTestId("chart-session-expired-banner"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Session expire ho gaya/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Live data ke liye wapas login karna padega/i),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("chart-session-expired-login"),
    ).toBeInTheDocument();
  });

  it("clicking 'Log in again' calls router.push('/login') by default", () => {
    mockPush.mockClear();
    render(<SessionExpiredBanner />);

    fireEvent.click(screen.getByTestId("chart-session-expired-login"));

    expect(mockPush).toHaveBeenCalledWith("/login");
  });

  it("onLogin prop overrides the router push", () => {
    mockPush.mockClear();
    const onLogin = vi.fn();
    render(<SessionExpiredBanner onLogin={onLogin} />);

    fireEvent.click(screen.getByTestId("chart-session-expired-login"));

    expect(onLogin).toHaveBeenCalledOnce();
    expect(mockPush).not.toHaveBeenCalled();
  });
});
