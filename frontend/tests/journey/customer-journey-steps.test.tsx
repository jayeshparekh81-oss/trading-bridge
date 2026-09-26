/**
 * The customer journey (Track C item 6): pay → strategy → direction → even-lot
 * quantity → broker → daily one-tap → 09:07 readiness → trade. ONE next step, never a
 * guessed state, the 4-question walk, the flag OFF by default.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  FRESH_ACCOUNT_INPUTS,
  JOURNEY_FLAG,
  JOURNEY_STEPS,
  STEP_COPY,
  customerJourneyEnabled,
  measured,
  notMeasured,
  resolveJourney,
  type JourneyInputs,
} from "@/lib/customer-journey";

const read = (p: string) => readFileSync(join(process.cwd(), p), "utf8");

// ── the resolver (pure) ───────────────────────────────────────────────────

describe("resolveJourney — one next step, never a guess", () => {
  it("a FRESH account with charging off lands on STRATEGY, PAY is honestly done", () => {
    const r = resolveJourney(FRESH_ACCOUNT_INPUTS);
    expect(r.next).toBe("STRATEGY");
    const pay = r.steps.find((s) => s.step === "PAY")!;
    expect(pay.state).toBe("DONE");
    expect(pay.line).toMatch(/charging switch band/);
    expect(r.steps.filter((s) => s.state === "LATER").map((s) => s.step)).toEqual(
      ["DIRECTION", "QUANTITY", "BROKER", "DAILY_CONNECT", "READINESS", "TRADE"],
    );
  });

  const existing: JourneyInputs = {
    billing: measured({ plan_status: "active", is_active: true }),
    charging_enabled: false,
    subscriptions: measured([{ id: "s1", status: "active", direction_filter: "both", lots: 2, is_paper: false, listing_title: "BSE Futures S1",
      open_position: { symbol: "BSE-OCT2026-FUT", quantity: 400, side: "short" } }]),
    brokers: measured([{ name: "Dhan", status: "connected" }]),
    lane: measured({ connected: true, reason: "ok", eligibility: "FULL_DAY", message: "" }),
    truth: measured({ verdict: "PROTECTED", line: "Stop broker par RAKHA HAI", next_step_hi: "" }),
  };

  it("an EXISTING account with real data walks through to TRADE", () => {
    const r = resolveJourney(existing);
    expect(r.next).toBe("TRADE");
    expect(r.steps.slice(0, 7).every((s) => s.state === "DONE")).toBe(true);
    expect(r.steps[7].line).toMatch(/short 400 BSE-OCT2026-FUT/);
  });

  it("an odd lot count is the NEXT step and says what even means", () => {
    const r = resolveJourney({ ...existing, subscriptions: measured([{ ...existing.subscriptions.value![0], lots: 3 }]) });
    expect(r.next).toBe("QUANTITY");
    // Flipped forward 26 Sep (founder's rule, point 3: plain words). Original: expect(r.steps.find((s) => s.step === "QUANTITY")!.line).toMatch(/even chahiye/);
    expect(r.steps.find((s) => s.step === "QUANTITY")!.line).toMatch(/jodi me chahiye \(2, 4, 6/);
  });

  it("a missing direction is NEXT before quantity", () => {
    const r = resolveJourney({ ...existing, subscriptions: measured([{ ...existing.subscriptions.value![0], direction_filter: null }]) });
    expect(r.next).toBe("DIRECTION");
  });

  it("an expired broker token is still the one-time setup DONE; the daily tap is what is next", () => {
    const r = resolveJourney({ ...existing, brokers: measured([{ name: "Dhan", status: "expired" }]),
      lane: measured({ connected: false, reason: "token_expired", eligibility: "NOT_TODAY", message: "Aaj connect nahi hua — 09:15 se pehle tap karo." }) });
    expect(r.steps.find((s) => s.step === "BROKER")!.state).toBe("DONE");
    expect(r.next).toBe("DAILY_CONNECT");
    expect(r.steps.find((s) => s.step === "DAILY_CONNECT")!.line).toMatch(/09:15/);
  });

  it("an UNPROTECTED stop makes READINESS the next step with the broker-verified line", () => {
    const r = resolveJourney({ ...existing, truth: measured({ verdict: "UNPROTECTED", line: "DHYAN: koi stop NAHI mila", next_step_hi: "" }) });
    expect(r.next).toBe("READINESS");
    expect(r.steps.find((s) => s.step === "READINESS")!.line).toMatch(/NAHI mila/);
  });

  it("a NOT MEASURED surface becomes UNKNOWN, never DONE, and blocks with its reason", () => {
    const r = resolveJourney({ ...existing, lane: notMeasured("customer-lane status surface not mounted (flag OFF)") });
    const d = r.steps.find((s) => s.step === "DAILY_CONNECT")!;
    expect(d.state).toBe("UNKNOWN");
    expect(d.line).toMatch(/^NOT MEASURED: customer-lane status surface not mounted/);
    expect(r.next).toBe("DAILY_CONNECT");
    expect(r.headline).toMatch(/NOT MEASURED/);
  });

  it("charging ON with no active plan makes PAY the next step", () => {
    const r = resolveJourney({ ...existing, charging_enabled: true, billing: measured({ plan_status: "pending", is_active: false }) });
    expect(r.next).toBe("PAY");
  });

  it("every step has a title, a what and a cta in plain words, and every state has an href", () => {
    for (const s of JOURNEY_STEPS) {
      expect(STEP_COPY[s].title.length).toBeGreaterThan(3);
      expect(STEP_COPY[s].what.length).toBeGreaterThan(10);
      expect(STEP_COPY[s].cta.length).toBeGreaterThan(3);
    }
    for (const s of resolveJourney(existing).steps) expect(s.href.startsWith("/")).toBe(true);
  });
});

// ── the flag ──────────────────────────────────────────────────────────────

describe("the flag", () => {
  const saved = process.env[JOURNEY_FLAG];
  afterEach(() => { if (saved === undefined) delete process.env[JOURNEY_FLAG]; else process.env[JOURNEY_FLAG] = saved; });
  it("is OFF unless exactly '1'", () => {
    delete process.env[JOURNEY_FLAG];
    expect(customerJourneyEnabled()).toBe(false);
    process.env[JOURNEY_FLAG] = "true";
    expect(customerJourneyEnabled()).toBe(false);
    process.env[JOURNEY_FLAG] = "1";
    expect(customerJourneyEnabled()).toBe(true);
  });
});

// ── the screen: three states, one tap back, one CTA, mobile-first ─────────

const apiMock = vi.hoisted(() => ({ impl: ((): unknown => ({ data: null, isLoading: true, error: null })) as (url: string | null) => unknown }));
vi.mock("@/shared/api/use-api", () => ({ useApi: (url: string | null) => apiMock.impl(url) }));
vi.mock("next/navigation", () => ({ usePathname: () => "/journey", useSearchParams: () => new URLSearchParams() }));

describe("JourneyStepper", () => {
  beforeEach(() => { process.env[JOURNEY_FLAG] = "1"; });
  afterEach(() => { delete process.env[JOURNEY_FLAG]; delete process.env.NEXT_PUBLIC_CUSTOMER_DASHBOARD; });

  it("loading: says it is checking; back is one tap; the CTA exists", async () => {
    const { JourneyStepper } = await import("@/components/journey/journey-stepper");
    apiMock.impl = () => ({ data: null, isLoading: true, error: null });
    render(<JourneyStepper />);
    expect(screen.getByTestId("journey-loading")).toBeTruthy();
    // while loading nothing is read: PAY is honestly DONE (charging OFF) and STRATEGY is
    // already the next step, so "back" is ONE tap to the previous step, never a dead end
    expect(screen.getByTestId("journey-back").getAttribute("href")).toBe("/journey?step=PAY");
    expect(screen.getByTestId("journey").getAttribute("data-step")).toBe("STRATEGY");
    expect(screen.getByTestId("journey-cta")).toBeTruthy();
  });

  it("fresh account: STRATEGY is the step, the CTA goes to the marketplace, unmounted lane surfaces read NOT MEASURED (never 'done')", async () => {
    const { JourneyStepper } = await import("@/components/journey/journey-stepper");
    apiMock.impl = (url) => {
      if (url === "/marketplace/subscriptions/me") return { data: { subscriptions: [], count: 0 }, isLoading: false, error: null };
      if (url === "/brokers") return { data: [], isLoading: false, error: null };
      if (url === "/billing/me") return { data: { plan_status: "none", is_active: false }, isLoading: false, error: null };
      return { data: null, isLoading: false, error: null };           // lane surfaces: url null (flag OFF)
    };
    render(<JourneyStepper />);
    const root = screen.getByTestId("journey");
    expect(root.getAttribute("data-step")).toBe("STRATEGY");
    expect(screen.getByTestId("journey-cta").querySelector("a")!.getAttribute("href")).toBe("/marketplace");
    expect(screen.getByTestId("journey-step-DAILY_CONNECT").getAttribute("data-state")).toBe("LATER");
    expect(screen.queryByTestId("journey-error")).toBeNull();
  });

  it("error: a failed surface shows the error line and NOT MEASURED, never a green tick", async () => {
    const { JourneyStepper } = await import("@/components/journey/journey-stepper");
    apiMock.impl = (url) => {
      if (url === "/marketplace/subscriptions/me") return { data: null, isLoading: false, error: "HTTP 500" };
      return { data: null, isLoading: false, error: null };
    };
    render(<JourneyStepper />);
    expect(screen.getByTestId("journey-error")).toBeTruthy();
    expect(screen.getByTestId("journey-step-STRATEGY").getAttribute("data-state")).toBe("UNKNOWN");
    expect(screen.getByTestId("journey-line").textContent).toMatch(/NOT MEASURED/);
  });

  it("existing account with real data: lands on TRADE with the open position; back goes to the previous step", async () => {
    process.env.NEXT_PUBLIC_CUSTOMER_DASHBOARD = "1";
    const { JourneyStepper } = await import("@/components/journey/journey-stepper");
    apiMock.impl = (url) => {
      switch (url) {
        case "/marketplace/subscriptions/me": return { data: { subscriptions: [{ id: "s1", status: "active", direction_filter: "both", lots_override: 2, is_paper: false, listing_title: "S1", open_position: { symbol: "BSE-OCT2026-FUT", quantity: 400, side: "short" } }], count: 1 }, isLoading: false, error: null };
        case "/brokers": return { data: [{ name: "Dhan", status: "connected" }], isLoading: false, error: null };
        case "/billing/me": return { data: { plan_status: "active", is_active: true }, isLoading: false, error: null };
        case "/customer-lane/me/status": return { data: { connected: true, reason: "ok", eligibility: "FULL_DAY", message: "" }, isLoading: false, error: null };
        case "/customer-lane/dashboard/truth": return { data: { verdict: "PROTECTED", line: "Stop broker par RAKHA HAI", next_step_hi: "" }, isLoading: false, error: null };
        default: return { data: null, isLoading: false, error: null };
      }
    };
    render(<JourneyStepper />);
    expect(screen.getByTestId("journey").getAttribute("data-step")).toBe("TRADE");
    expect(screen.getByTestId("journey-line").textContent).toMatch(/short 400 BSE-OCT2026-FUT/);
    expect(screen.getByTestId("journey-back").getAttribute("href")).toBe("/journey?step=READINESS");
    expect(screen.getByTestId("journey-step-READINESS").getAttribute("data-state")).toBe("DONE");
  });
});

// ── the house rules on the files themselves ───────────────────────────────

describe("house rules", () => {
  it("the page is behind the flag and uses ProPage; the stepper uses tokens only", () => {
    const page = read("src/app/(dashboard)/journey/page.tsx");
    expect(page).toMatch(/customerJourneyEnabled\(\)/);
    expect(page).toMatch(/<ProPage/);
    const comp = read("src/components/journey/journey-stepper.tsx");
    expect(comp).not.toMatch(/#[0-9a-fA-F]{3,6}\b/);
    expect(comp).not.toMatch(/\[\d+px\]/);
    expect(comp).toMatch(/min-h-1[12]/);                       // thumb-reachable targets
  });

  it("the resolver holds no fact of its own: no rupee number, no price, no expiry day", () => {
    const lib = read("src/lib/customer-journey.ts").replace(/\/\*[\s\S]*?\*\//g, "");
    expect(lib).not.toMatch(/₹\s?\d/);
    expect(lib).not.toMatch(/\b(Thursday|Tuesday|Monday)\b/);
  });
});
