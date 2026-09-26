/**
 * SIGNUP CUTS 1+2 (26 Sep 2026 night) on the /start screens. The server payloads are the SERVER's
 * real output: tests/guided/fixtures/states_cuts.json was dumped by
 * backend/scripts/guided_fixture_dump.py on itmgr/20260926-guided-cuts (the SIZE and CONFIRM
 * entries) — never a hand-made copy. The older server's payloads (states.json) must still render
 * exactly as before, because the frontend and the backend are published separately.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const OLD = JSON.parse(readFileSync(join(process.cwd(), "tests/guided/fixtures/states.json"), "utf8"));
const CUT = JSON.parse(readFileSync(join(process.cwd(), "tests/guided/fixtures/states_cuts.json"), "utf8"));

const guidedApi = vi.hoisted(() => ({
  publicStart: vi.fn(), state: vi.fn(), choose: vi.fn(), back: vi.fn(), broker: vi.fn(), ask: vi.fn(),
  confirm: vi.fn(), running: vi.fn(), stopPreview: vi.fn(), stop: vi.fn(), signup: vi.fn(), restart: vi.fn(),
}));
vi.mock("@/lib/guided-path", async (orig) => {
  const real = await orig<typeof import("@/lib/guided-path")>();
  return { ...real, guidedApi, guidedPathLive: vi.fn(async () => true) };
});
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), refresh: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/start",
  useSearchParams: () => new URLSearchParams(),
}));

import { GuidedPath } from "@/components/guided/guided-path";

beforeEach(() => {
  Object.values(guidedApi).forEach((f) => f.mockReset());
  localStorage.setItem("tb_access_token", "t");
});

describe("signup cut 2 — the summary lives on the confirm screen", () => {
  it("a merged server: CONFIRM shows the whole summary once, and the tick still guards the button", async () => {
    expect(CUT.CONFIRM.progress.map((p: { step: string }) => p.step)).not.toContain("SUMMARY");
    guidedApi.state.mockResolvedValue(CUT.CONFIRM);
    render(<GuidedPath />);
    await screen.findByTestId("screen-CONFIRM");
    expect(screen.getByTestId("summary")).toBeTruthy();
    expect(screen.getByTestId("summary-never")).toBeTruthy();
    expect(screen.queryByTestId("confirm-short")).toBeNull();          // not said twice
    const next = screen.getByTestId("guided-next") as HTMLButtonElement;
    expect(next.disabled).toBe(true);
    await act(async () => { fireEvent.click(screen.getByTestId("confirm-ack")); });
    expect(next.disabled).toBe(false);
    expect(screen.getAllByTestId(/^guided-next$/)).toHaveLength(1);    // ONE primary
  });

  it("an older server: CONFIRM is unchanged (the summary had its own screen)", async () => {
    guidedApi.state.mockResolvedValue(OLD.CONFIRM);
    render(<GuidedPath />);
    await screen.findByTestId("screen-CONFIRM");
    expect(screen.queryByTestId("summary")).toBeNull();
    expect(screen.getByTestId("confirm-short")).toBeTruthy();
  });
});

describe("signup cut 1 — no vehicle screen while only FUTURES is open", () => {
  it("SIZE's Back goes to the strategy screen the customer saw", async () => {
    expect(CUT.SIZE.back).toBe("STRATEGY");
    const bar = Object.fromEntries(CUT.SIZE.progress.map((p: { step: string; state: string }) => [p.step, p.state]));
    expect(bar.VEHICLE).toBe("NOT_NEEDED");
    guidedApi.state.mockResolvedValue(CUT.SIZE);
    guidedApi.back.mockResolvedValue(OLD.STRATEGY);
    render(<GuidedPath />);
    await screen.findByTestId("screen-SIZE");
    await act(async () => { fireEvent.click(screen.getByTestId("guided-back")); });
    expect(guidedApi.back).toHaveBeenCalledWith("SIZE");
  });
});
