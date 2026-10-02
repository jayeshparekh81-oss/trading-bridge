/**
 * THE WRONG HOPE (founder, 2 Oct 2026, after walking the live site as the test customer):
 * the Simple home said "Naya signal aaya · 15:2x" while NO trade had been created for the
 * customer. With the marketplace fan-out OFF (config.py:439, gate strategy_webhook.py:702) a
 * signal row IS written for every subscribed strategy and NO customer execution is — and the
 * home read only the signal feed (useSimpleStatus.ts). Rule: never show a signal line that has
 * no trade behind it. The hero now gates on an execution row of the customer's OWN subscription
 * (GET /marketplace/subscriptions/{id}/executions, marketplace.py:2145).
 *
 * This renders the REAL SimpleHome container + view over an in-memory API.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mkdirSync, writeFileSync } from "node:fs";
import type { ReactNode } from "react";

/** HERO_SNAP_DIR=<dir>: write the rendered hero HTML of each case (the box has no browser — this is the receipt). */
function snap(name: string, el: HTMLElement) {
  const dir = process.env.HERO_SNAP_DIR;
  if (!dir) return;
  mkdirSync(dir, { recursive: true });
  writeFileSync(`${dir}/${name}.html`, el.outerHTML + "\n");
}

vi.mock("framer-motion", () => ({
  motion: new Proxy({}, { get: () => (props: Record<string, unknown> & { children?: ReactNode }) => {
    const { children, ...rest } = props;
    const dom = Object.fromEntries(Object.entries(rest).filter(([k]) => /^(data-|aria-|className|href|onClick|role|id)/.test(k)));
    return <div {...dom}>{children}</div>;
  } }),
  AnimatePresence: ({ children }: { children?: ReactNode }) => <>{children}</>,
  useReducedMotion: () => true,
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), refresh: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("sonner", () => ({ toast: { info: vi.fn(), success: vi.fn(), error: vi.fn() } }));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { id: "u1", email: "walk@x.com", full_name: "Ramesh Test", is_admin: false } }),
}));
vi.mock("@/contexts/LanguageContext", async (orig) => ({ ...(await orig<typeof import("@/contexts/LanguageContext")>()), useLanguage: () => ({ lang: "hinglish", setLang: vi.fn() }), useLanguageOptional: () => ({ lang: "hinglish", setLang: vi.fn() }) }));
vi.mock("@/hooks/useGuidedPathLive", () => ({ useGuidedPathLive: () => "off" }));
vi.mock("@/hooks/useLadder", () => ({
  useLadder: () => ({
    ready: true, earned: 2, choice: "auto", level: 2,
    state: { earned: 2, choice: "auto", facts: {}, tipsShown: [], homeNudgeSeen: true },
    observe: vi.fn(), setChoice: vi.fn(), markProNudgeSeen: vi.fn(), markSimpleOnboardingDone: vi.fn(),
    markHomeNudgeSeen: vi.fn(), markTipShown: vi.fn(),
  }),
}));

// ── the in-memory server ─────────────────────────────────────────────────────
const SIGNAL_AT = new Date(Date.now() - 10 * 60_000).toISOString(); // today, 10 min ago
const LISTING = "lst-1";
const SUB = "sub-1";
const S = {
  signals: [] as unknown[],
  subs: [] as unknown[],
  execs: null as null | unknown[] | "FAIL",
  urls: [] as string[],
};
const signal = (over: Record<string, unknown> = {}) => ({
  id: "sig-1", listing_id: LISTING, listing_title: "BSE Ltd Momentum", symbol: "BSE", action: "ENTRY", side: "buy",
  entry: "3240.50", stop_loss: null, target: null, received_at: SIGNAL_AT, status: "received",
  validity: { window: "entry", valid: false, expires_at: SIGNAL_AT, seconds_remaining: 0 }, ...over,
});
const activeSub = (over: Record<string, unknown> = {}) => ({
  id: SUB, status: "active", execution_mode: "auto", is_paper: true, listing_id: LISTING, listing_title: "BSE Ltd Momentum", ...over,
});
const execution = (over: Record<string, unknown> = {}) => ({
  id: "ex-1", symbol: "BSE", side: "buy", quantity: 2, leg_role: "entry", order_type: "MARKET", price: "3240.50",
  broker_order_id: "PAPER-1", broker_status: "complete", error_code: null, error_message: null,
  placed_at: new Date(Date.parse(SIGNAL_AT) + 2_000).toISOString(), completed_at: null, paper_mode: true, ...over,
});

vi.mock("@/shared/api/client", () => {
  class ApiError extends Error { status = 500; detail = "boom"; data: unknown = undefined; }
  return {
    ApiError,
    api: {
      get: vi.fn(async (url: string) => {
        S.urls.push(url);
        if (url.startsWith("/brokers/dhan/status")) return { connected: false };
        if (url.startsWith("/marketplace/subscriptions/me")) return { subscriptions: S.subs };
        if (url.startsWith("/marketplace/subscriptions/signals")) return { signals: S.signals, count: S.signals.length };
        if (url.startsWith("/strategies?")) return { strategies: [] };
        if (url.startsWith("/kill-switch/status")) return { state: "ARMED" };
        if (/^\/marketplace\/subscriptions\/[^/]+\/executions/.test(url)) {
          if (S.execs === "FAIL") throw new ApiError("boom");
          return { subscription_id: SUB, executions: S.execs ?? [], count: (S.execs ?? []).length };
        }
        throw new Error(`unmocked ${url}`);
      }),
      post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(),
    },
  };
});

import { SimpleHome } from "@/components/simple/simple-home";

const settled = async () => {
  await waitFor(() => expect(S.urls.some((u) => u.startsWith("/marketplace/subscriptions/signals"))).toBe(true));
  // let the follow-up executions read (if any) land too
  await new Promise((r) => setTimeout(r, 30));
};

beforeEach(() => {
  S.signals = []; S.subs = []; S.execs = null; S.urls = [];
  window.localStorage.clear();
});

describe("the Simple home hero never shows a signal with no trade behind it", () => {
  it("fan-out OFF today: a signal row, an active paper subscription, NO execution → no 'signal aaya'; the honest line instead", async () => {
    S.signals = [signal()]; S.subs = [activeSub()]; S.execs = [];
    render(<SimpleHome />);
    await settled();
    await waitFor(() => expect(S.urls.some((u) => u.includes(`/subscriptions/${SUB}/executions`))).toBe(true));
    const hero = await screen.findByTestId("hero-signal");
    await waitFor(() => expect(hero.textContent).toMatch(/koi practice trade nahi bana/i));
    expect(hero.textContent).not.toMatch(/signal aaya/i);
    expect(hero.textContent).not.toMatch(/BSE/);
    snap("after_signal_no_trade", hero);
    // the signal COUNT stays a fact about signals (the status strip labels it "Aaj ke signals")
    expect(screen.getAllByText("Aaj ke signals")[0].parentElement?.textContent).toMatch(/1/);
  });

  it("a paper trade exists on the customer's own subscription for that signal → the hero shows it", async () => {
    S.signals = [signal()]; S.subs = [activeSub()]; S.execs = [execution()];
    render(<SimpleHome />);
    await settled();
    const hero = screen.getByTestId("hero-signal");
    await waitFor(() => expect(hero.textContent).toMatch(/signal aaya/i));
    expect(hero.textContent).toMatch(/BSE/);
    expect(hero.textContent).toMatch(/3,240.5/);
    snap("after_signal_with_trade", hero);
  });

  it("an execution that FAILED (error_code) is not a trade; a trade for another symbol is not this signal's", async () => {
    S.signals = [signal()]; S.subs = [activeSub()];
    S.execs = [execution({ error_code: "REJECTED" }), execution({ id: "ex-2", symbol: "TCS" })];
    render(<SimpleHome />);
    await settled();
    const hero = screen.getByTestId("hero-signal");
    await waitFor(() => expect(hero.textContent).toMatch(/koi practice trade nahi bana/i));
    expect(hero.textContent).not.toMatch(/signal aaya/i);
  });

  it("the trade read FAILS → the hero asserts nothing (neither 'signal aaya' nor 'koi trade nahi')", async () => {
    S.signals = [signal()]; S.subs = [activeSub()]; S.execs = "FAIL";
    render(<SimpleHome />);
    await settled();
    await waitFor(() => expect(S.urls.some((u) => u.includes("/executions"))).toBe(true));
    await new Promise((r) => setTimeout(r, 30));
    const hero = screen.getByTestId("hero-signal");
    expect(hero.textContent).not.toMatch(/signal aaya/i);
    expect(hero.textContent).not.toMatch(/nahi bana/i);
    expect(screen.queryByTestId("hero-empty")).toBeNull();
    snap("after_trade_read_failed", hero);
  });

  it("a signal of a listing the customer is NOT actively subscribed to → no trade of theirs can exist → the honest line", async () => {
    S.signals = [signal()]; S.subs = [activeSub({ status: "cancelled" })];
    render(<SimpleHome />);
    await settled();
    expect(S.urls.some((u) => u.includes("/executions"))).toBe(false);
    const hero = screen.getByTestId("hero-signal");
    await waitFor(() => expect(hero.textContent).toMatch(/koi practice trade nahi bana/i));
    expect(hero.textContent).not.toMatch(/signal aaya/i);
  });

  it("no signal today → the old 'koi signal nahi' line, unchanged", async () => {
    S.subs = [activeSub()];
    render(<SimpleHome />);
    await settled();
    const hero = screen.getByTestId("hero-signal");
    await waitFor(() => expect(hero.textContent).toMatch(/koi signal nahi/i));
    expect(S.urls.some((u) => u.includes("/executions"))).toBe(false);
  });
});
