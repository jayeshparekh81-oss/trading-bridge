/**
 * C8/C11/C12: the ladder persists itself through the EXISTING prefs endpoint
 * (read-merge-write), learns facts from action-site events, and starts
 * existing accounts at Pro without a single write.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";

const auth = { user: null as Record<string, unknown> | null, refreshUser: vi.fn(async () => {}) };
vi.mock("@/lib/auth", () => ({ useAuth: () => auth }));
const put = vi.fn<(url: string, body: { notification_prefs: Record<string, unknown> }) => Promise<unknown>>(async () => ({}));
vi.mock("@/lib/api", () => ({ api: { put: (url: string, body: { notification_prefs: Record<string, unknown> }) => put(url, body) } }));

import { LadderProvider, useLadder } from "@/hooks/useLadder";

function Probe() {
  const l = useLadder();
  return (
    <div>
      <span data-testid="ready">{String(l.ready)}</span>
      <span data-testid="level">{l.level}</span>
      <span data-testid="earned">{l.earned}</span>
      <span data-testid="tips">{(l.state?.tipsShown ?? []).join(",")}</span>
      <button data-testid="simple" onClick={() => void l.setChoice("simple")} />
      <button data-testid="pro" onClick={() => void l.setChoice("pro")} />
      <button data-testid="tip" onClick={() => l.markTipShown("templates")} />
    </div>
  );
}

beforeEach(() => {
  put.mockClear();
  auth.refreshUser.mockClear();
});

describe("LadderProvider", () => {
  it("a NEW signup starts at Level 1 and is persisted once, keeping other prefs", async () => {
    auth.user = { id: "u1", is_admin: false, created_at: "2026-09-06T08:00:00Z", notification_prefs: { email: true } };
    render(
      <LadderProvider>
        <Probe />
      </LadderProvider>,
    );
    expect(screen.getByTestId("ready").textContent).toBe("true");
    expect(screen.getByTestId("level").textContent).toBe("1");
    await waitFor(() => expect(put).toHaveBeenCalledTimes(1));
    const body = put.mock.calls[0][1];
    expect(body.notification_prefs.email).toBe(true); // read-merge-write
    expect(body.notification_prefs._ui_ladder).toMatchObject({ earned: 1, choice: "auto" });
    expect(put.mock.calls[0][0]).toBe("/users/me");
  });

  it("learns facts from action-site events; the journey step follows, nothing is gated", async () => {
    auth.user = { id: "u2", is_admin: false, created_at: "2026-09-06T08:00:00Z", notification_prefs: {} };
    render(
      <LadderProvider>
        <Probe />
      </LadderProvider>,
    );
    await waitFor(() => expect(put).toHaveBeenCalledTimes(1));
    act(() => {
      window.dispatchEvent(new CustomEvent("tradetri:ladder", { detail: { brokerConnected: true, hasSubscription: true } }));
    });
    expect(screen.getByTestId("level").textContent).toBe("1"); // two of three facts
    act(() => {
      window.dispatchEvent(new CustomEvent("tradetri:ladder", { detail: { firstSignalSeen: true } }));
    });
    expect(screen.getByTestId("level").textContent).toBe("2");
    await waitFor(() => expect(put).toHaveBeenCalledTimes(3));
    const last = put.mock.calls[2][1];
    const saved = last.notification_prefs._ui_ladder as { facts: Record<string, string> };
    expect(Object.keys(saved.facts).sort()).toEqual(["brokerConnected", "firstSignalSeen", "hasSubscription"]);
    // "Aur seekhein" tips are remembered per account (once per tile)
    act(() => screen.getByTestId("tip").click());
    expect(screen.getByTestId("tips").textContent).toBe("templates");
    act(() => screen.getByTestId("tip").click());
    expect(screen.getByTestId("tips").textContent).toBe("templates");
  });

  it("an EXISTING account is Pro and nothing is written until it changes something", async () => {
    auth.user = { id: "u3", is_admin: false, created_at: "2026-03-01T00:00:00Z", notification_prefs: {} };
    render(
      <LadderProvider>
        <Probe />
      </LadderProvider>,
    );
    expect(screen.getByTestId("level").textContent).toBe("4");
    // The initial Pro state is persisted once so it is stable across devices…
    await waitFor(() => expect(put).toHaveBeenCalledTimes(1));
    // …and Simple is one toggle away. With NO facts yet it is Level 1 — the
    // tiles must reflect what this account has really done, not the Pro default.
    act(() => screen.getByTestId("simple").click());
    expect(screen.getByTestId("level").textContent).toBe("1");
    await waitFor(() => expect(put).toHaveBeenCalledTimes(2));
    // Real state arrives (broker + subscription + a signal seen) → Level 2 in Simple.
    act(() => {
      window.dispatchEvent(new CustomEvent("tradetri:ladder", { detail: { brokerConnected: true, hasSubscription: true, firstSignalSeen: true } }));
    });
    expect(screen.getByTestId("level").textContent).toBe("2");
    // Simple never shows the Pro chrome, even for an account that has done everything.
    act(() => {
      window.dispatchEvent(new CustomEvent("tradetri:ladder", { detail: { templateCloned: true, backtestRun: true, strategyBuilt: true } }));
    });
    expect(screen.getByTestId("level").textContent).toBe("3");
    act(() => screen.getByTestId("pro").click());
    expect(screen.getByTestId("level").textContent).toBe("4");
  });

  it("a stored ladder is read back without any write (fresh login)", async () => {
    auth.user = {
      id: "u4",
      is_admin: false,
      created_at: "2026-09-06T08:00:00Z",
      notification_prefs: { _ui_ladder: { earned: 1, choice: "auto", facts: { brokerConnected: "2026-09-06T09:00:00Z", hasSubscription: "2026-09-06T09:00:00Z", firstSignalSeen: "2026-09-06T09:00:00Z", templateCloned: "2026-09-06T09:00:00Z", backtestRun: "2026-09-06T09:00:00Z" }, proNudgeSeen: false, simpleOnboardingDone: true, tipsShown: [] } },
    };
    render(
      <LadderProvider>
        <Probe />
      </LadderProvider>,
    );
    expect(screen.getByTestId("level").textContent).toBe("3");
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    expect(put).not.toHaveBeenCalled();
  });

  it("founder / admin accounts are Pro regardless of signup date", () => {
    auth.user = { id: "u5", is_admin: true, created_at: "2026-09-06T08:00:00Z", notification_prefs: {} };
    render(
      <LadderProvider>
        <Probe />
      </LadderProvider>,
    );
    expect(screen.getByTestId("level").textContent).toBe("4");
  });
});
