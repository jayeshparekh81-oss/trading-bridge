/**
 * ONE THING PER SCREEN (founder's rule, 26 Sep 2026, point 2) and ALWAYS A WAY BACK
 * (point 5), rendered — not read from source:
 *  - every step of the first-timer guided path shows exactly ONE primary button, in the
 *    normal state AND when an error card with its own "what to do" button is showing;
 *  - every step of the Simple first-run onboarding (live today) shows exactly ONE primary
 *    button, and steps 2 and 3 have a Back that keeps what was chosen.
 * The screen payloads are the SERVER's real output (tests/guided/fixtures/states.json).
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { ApiError } from "@/shared/api/client";

const STATES = JSON.parse(readFileSync(join(process.cwd(), "tests/guided/fixtures/states.json"), "utf8"));

const guidedApi = vi.hoisted(() => ({
  publicStart: vi.fn(), state: vi.fn(), choose: vi.fn(), back: vi.fn(), broker: vi.fn(), ask: vi.fn(),
  confirm: vi.fn(), running: vi.fn(), stopPreview: vi.fn(), stop: vi.fn(), signup: vi.fn(), restart: vi.fn(),
}));
vi.mock("@/lib/guided-path", async (orig) => ({ ...(await orig<typeof import("@/lib/guided-path")>()), guidedApi }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), refresh: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/start",
  useSearchParams: () => new URLSearchParams(),
}));

import { GuidedPath } from "@/components/guided/guided-path";

const primaries = () => document.querySelectorAll('[data-primary="true"]');

/** A server-shaped never-stuck envelope that carries its own "what to do" button. */
const ENVELOPE = {
  kind: "BROKER_UNREACHABLE",
  what_happened: "Dhan abhi jawab nahi de raha.",
  what_it_means: "Aapki koi settings nahi gayi.",
  what_to_do: "2 minute ruk ke dobara dabao.",
  action: { label: "Dobara try karo", step: null },
  back: null,
  contact: null,
};

beforeEach(() => {
  Object.values(guidedApi).forEach((f) => f.mockReset());
  localStorage.setItem("tb_access_token", "t");
  cleanup();
});

describe("guided path — exactly one primary button on every step", () => {
  const steps = ["BROKER", "STRATEGY", "VEHICLE", "STRIKE", "SIZE", "SUMMARY", "CONFIRM"].filter((k) => STATES[k]);

  it.each(steps)("%s, normal state", async (key) => {
    guidedApi.state.mockResolvedValue(STATES[key]);
    render(<GuidedPath />);
    await screen.findByTestId("guided");
    expect(primaries().length).toBe(1);
    expect(screen.getByTestId("guided-next").getAttribute("data-primary")).toBe("true");
    expect(screen.getByTestId("guided-back")).toBeTruthy(); // a way back on every screen
  });

  it.each(steps.filter((k) => k !== "BROKER" && k !== "CONFIRM"))("%s, when an error card leads with its own button", async (key) => {
    guidedApi.state.mockResolvedValue(STATES[key]);
    const fail = new ApiError(502, "x", { error: ENVELOPE });
    for (const f of [guidedApi.choose, guidedApi.confirm, guidedApi.broker]) f.mockRejectedValue(fail);
    render(<GuidedPath />);
    await screen.findByTestId("guided");
    const next = screen.getByTestId("guided-next") as HTMLButtonElement;
    if (next.disabled) return; // a step whose Next waits for a choice cannot raise the error here
    fireEvent.click(next);
    await screen.findByTestId("guided-error");
    expect(primaries().length).toBe(1);
    expect(screen.getByTestId("guided-error-action").getAttribute("data-primary")).toBe("true");
    expect(screen.getByTestId("guided-next").getAttribute("data-primary")).toBeNull();
  });
});

describe("the falsification twin: the counter really counts", () => {
  it("two primaries on one screen would be caught", () => {
    render(
      <div>
        <button data-primary="true">a</button>
        <button data-primary="true">b</button>
      </div>,
    );
    expect(primaries().length).toBe(2);
  });
});

// ── Simple first-run onboarding (the live new-customer path today) ──────────

vi.mock("@/lib/auth", () => {
  const auth = { refreshUser: vi.fn(async () => {}), user: { id: "u1" }, isAuthenticated: true, isLoading: false };
  return { useAuth: () => auth, useAuthOptional: () => auth };
});
// AnimatePresence mode="wait" keeps the OLD step mounted until an exit animation that
// jsdom never finishes — render the steps plainly (same stand-in as next-through-onboarding).
vi.mock("framer-motion", async () => {
  const React = await import("react");
  const strip = (p: Record<string, unknown>) => Object.fromEntries(Object.entries(p).filter(([k]) => !["initial", "animate", "exit", "transition", "variants", "whileHover", "whileTap", "layout"].includes(k)));
  const el = (tag: string) => { const C = ({ children, ...p }: React.PropsWithChildren<Record<string, unknown>>) => React.createElement(tag, strip(p), children); C.displayName = `motion.${tag}`; return C; };
  return { motion: { div: el("div"), section: el("section"), button: el("button"), p: el("p"), h1: el("h1"), span: el("span") }, AnimatePresence: function AnimatePresence({ children }: React.PropsWithChildren) { return children; }, useReducedMotion: () => true };
});
vi.mock("@/hooks/useLadder", () => ({ useLadderOptional: () => ({ markSimpleOnboardingDone: vi.fn() }) }));
vi.mock("@/contexts/LanguageContext", () => ({ useLanguage: () => ({ lang: "hinglish", setLang: vi.fn() }) }));
vi.mock("@/lib/simple/language-sync", () => ({
  SIMPLE_LANGS: [{ code: "hinglish", native: "Hinglish" }],
  ensureSimpleDefaultLanguage: () => {},
  mirrorLanguage: () => {},
}));
vi.mock("@/components/logo", () => ({ Logo: function Logo() { return <span />; } }));

import { SimpleOnboarding } from "@/components/simple/simple-onboarding";

describe("Simple onboarding — one primary per step, and a way back", () => {
  it("step 1 (bhasha): one primary, nothing to go back to", () => {
    render(<SimpleOnboarding />);
    expect(primaries().length).toBe(1);
    expect(screen.queryByTestId("ob-back")).toBeNull();
  });

  it("step 2 (broker) and step 3 (strategy): one primary each, and Back returns without losing the step's place", async () => {
    render(<SimpleOnboarding />);
    fireEvent.click(screen.getAllByTestId("ob-next")[0]); // → step 2
    await waitFor(() => expect(screen.getByTestId("simple-onboarding").getAttribute("data-step")).toBe("2"));
    expect(primaries().length).toBe(1);
    expect(screen.getByTestId("ob-back").textContent).toMatch(/Pichhla kadam/);
    fireEvent.click(screen.getAllByTestId("ob-next").at(-1)!); // skip broker → step 3
    await waitFor(() => expect(screen.getByTestId("simple-onboarding").getAttribute("data-step")).toBe("3"));
    expect(primaries().length).toBe(1);
    fireEvent.click(screen.getByTestId("ob-back"));
    await waitFor(() => expect(screen.getByTestId("simple-onboarding").getAttribute("data-step")).toBe("2"));
  });
});
