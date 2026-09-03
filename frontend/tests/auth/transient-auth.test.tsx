/**
 * A network blip must not log the customer out.
 *
 * Found during the cutover-22 recreate: for ~30 seconds `/auth/me` failed at
 * the network level (status 0). `fetchUser` treated ANY failure as "session
 * rejected", cleared BOTH tokens and set user=null — every open tab bounced
 * to /login, and because the refresh token was gone the customer could not
 * come back without re-typing their password. Only a real 401 (after the
 * client's own refresh attempt) may do that.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, waitFor } from "@testing-library/react";

const { apiGet, clearTokens } = vi.hoisted(() => ({ apiGet: vi.fn(), clearTokens: vi.fn() }));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { ...actual.api, get: apiGet, post: vi.fn() },
    clearTokens,
    setTokens: vi.fn(),
  };
});
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { AuthProvider, useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";

function Probe() {
  const { user, isLoading } = useAuth();
  return <div data-testid="probe">{isLoading ? "loading" : user ? `user:${user.email}` : "anon"}</div>;
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.setItem("tb_access_token", "a");
  localStorage.setItem("tb_refresh_token", "r");
});

describe("AuthProvider on /auth/me failure", () => {
  it("🔴 a NETWORK error (status 0) keeps the tokens", async () => {
    apiGet.mockRejectedValueOnce(new ApiError(0, "Network error — is the backend running?"));
    const { getByTestId } = render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(getByTestId("probe").textContent).not.toBe("loading"));
    expect(clearTokens).not.toHaveBeenCalled();
    expect(localStorage.getItem("tb_refresh_token")).toBe("r");
  });

  it("a 5xx from a restarting backend keeps the tokens too", async () => {
    apiGet.mockRejectedValueOnce(new ApiError(503, "Service Unavailable"));
    const { getByTestId } = render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(getByTestId("probe").textContent).not.toBe("loading"));
    expect(clearTokens).not.toHaveBeenCalled();
  });

  it("a real 401 still logs the customer out", async () => {
    apiGet.mockRejectedValueOnce(new ApiError(401, "Session expired. Please login again."));
    const { getByTestId } = render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(getByTestId("probe").textContent).toBe("anon"));
    expect(clearTokens).toHaveBeenCalledTimes(1);
  });

  it("a healthy /auth/me yields the user", async () => {
    apiGet.mockResolvedValueOnce({ id: "u1", email: "c@x.test", is_admin: false, notification_prefs: {} });
    const { getByTestId } = render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(getByTestId("probe").textContent).toBe("user:c@x.test"));
  });
});
