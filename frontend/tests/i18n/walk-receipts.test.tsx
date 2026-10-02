/**
 * WALK RECEIPTS — the re-walk of every customer screen in English AND Hinglish (founder, 2 Oct 2026:
 * "re-walk every screen in both languages and show before/after").
 *
 * Renders the real components with stubbed data (no browser on the box) and writes the rendered TEXT of
 * each screen to `$WALK_OUT/<nn>-<screen>.<lang>.txt`. Runs only when WALK_OUT is set; otherwise skipped.
 * The same file is run on the BEFORE tree (61a3c4c5) and on this tree, so the receipts are comparable.
 * It imports only pages/components that exist in both trees; the language is set the way the app stores
 * it (localStorage `tradetri_language` + the explicit-choice marker, which the old tree simply ignores).
 *
 * Optional env: GUIDED_STATES_EN (server states already re-worded by the backend's English layer — the
 * AFTER tree's /start in English), RUNNING_FIXTURE ({hinglish, en} RUNNING payloads).
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { ReactNode } from "react";

const OUT = process.env.WALK_OUT ?? "";
const LANGS = ["en", "hinglish"] as const;
type L = (typeof LANGS)[number];

// ── stubs ────────────────────────────────────────────────────────────────────
const authState = vi.hoisted(() => ({ user: null as null | Record<string, unknown> }));
const requested = vi.hoisted(() => ({ urls: [] as string[] }));
const apiData = vi.hoisted(() => ({ current: {} as Record<string, unknown> }));
const guidedApi = vi.hoisted(() => ({
  publicStart: vi.fn(), state: vi.fn(), choose: vi.fn(), back: vi.fn(), broker: vi.fn(), ask: vi.fn(),
  confirm: vi.fn(), running: vi.fn(), stopPreview: vi.fn(), stop: vi.fn(), signup: vi.fn(), restart: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn(), prefetch: vi.fn(), back: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/lib/auth", () => {
  const v = () => ({ user: authState.user, isLoading: false, isAuthenticated: !!authState.user, login: vi.fn(), register: vi.fn(), logout: vi.fn(), refreshUser: vi.fn(async () => undefined) });
  return { useAuth: v, useAuthOptional: () => (authState.user ? v() : null), AuthProvider: ({ children }: { children: ReactNode }) => children };
});
vi.mock("@/hooks/useSignupOpen", () => ({ useSignupOpen: () => "closed" }));
vi.mock("@/hooks/useGuidedPathLive", () => ({ useGuidedPathLive: () => "off" }));
vi.mock("@/components/auth/return-path-probe", () => ({ ReturnPathProbe: () => null }));
vi.mock("@/components/mantras-modal", () => ({ MantrasModal: () => null }));
vi.mock("@/shared/api/client", () => ({
  api: { get: vi.fn(async () => ({})), post: vi.fn(async () => ({})), put: vi.fn(async () => ({})), patch: vi.fn(async () => ({})) },
  ApiError: class extends Error { status = 0; detail = ""; },
  setTokens: vi.fn(), clearTokens: vi.fn(),
}));
vi.mock("@/shared/api/use-api", () => ({
  useApi: (url: string | null) => {
    if (url) requested.urls.push(url);
    const key = url === null ? "__null__"
      : Object.keys(apiData.current).sort((a, b) => b.length - a.length).find((k) => url === k || url.startsWith(k)) ?? "__miss__";
    return { data: apiData.current[key] ?? null, isLoading: false, error: null, paywalled: false, paywallUrl: null, refetch: vi.fn() };
  },
}));
vi.mock("@/hooks/useSystemMode", () => ({ useSystemMode: () => ({ paper_mode: false, kill_switch_check_enabled: true, circuit_breaker_enabled: true }) }));
vi.mock("@/hooks/useLadder", () => {
  const v = { level: 4, choice: "pro", earned: 4, setChoice: vi.fn(async () => undefined), markSimpleOnboardingDone: vi.fn(), markProNudgeSeen: vi.fn(),
    proNudgeSeen: true, state: null, isLoading: false, refresh: vi.fn(async () => undefined) };
  return { useLadder: () => v, useLadderOptional: () => v, LadderProvider: ({ children }: { children: ReactNode }) => children };
});
vi.mock("@/lib/guided-path", async (orig) => ({ ...(await orig<typeof import("@/lib/guided-path")>()), guidedApi, guidedPathLive: async () => true }));
vi.mock("sonner", () => ({ toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() }) }));
vi.mock("framer-motion", () => ({
  motion: new Proxy({}, { get: () => (props: Record<string, unknown> & { children?: ReactNode }) => {
    const { children, ...rest } = props;
    const dom = Object.fromEntries(Object.entries(rest).filter(([k]) => /^(data-|aria-|className|href|onClick|role|id|type|lang)/.test(k)));
    return <div {...dom}>{children}</div>;
  } }),
  AnimatePresence: ({ children }: { children?: ReactNode }) => <>{children}</>,
  useReducedMotion: () => true,
  useInView: () => true,
}));

if (!("IntersectionObserver" in globalThis)) {
  class IO { observe() {} unobserve() {} disconnect() {} takeRecords() { return []; } root = null; rootMargin = ""; thresholds = []; }
  (globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = IO;
}

import { LanguageProvider } from "@/contexts/LanguageContext";
import PublicLayout from "@/app/(public)/layout";
import HomePage from "@/app/(public)/home/page";
import PricingPage from "@/app/(public)/pricing/page";
import AboutPage from "@/app/(public)/about/page";
import ContactPage from "@/app/(public)/contact/page";
import ShowcasePage from "@/app/(public)/showcase/page";
import LoginPage from "@/app/(auth)/login/page";
import RegisterPage from "@/app/(auth)/register/page";
import StartLayout from "@/app/start/layout";
import { GuidedPath } from "@/components/guided/guided-path";
import { RunningDashboard } from "@/components/guided/guided-running";
import { SimpleHomeView } from "@/components/simple/simple-home-view";
import { LEARN_TILES, MAIN_TILES } from "@/lib/simple/level";
import PositionsPage from "@/app/(dashboard)/positions/page";
import TradesPage from "@/app/(dashboard)/trades/page";
import SignalsPage from "@/app/(dashboard)/signals/page";
import SettingsPage from "@/app/(dashboard)/settings/page";

// ── fixtures ─────────────────────────────────────────────────────────────────
const STATES = JSON.parse(readFileSync(join(process.cwd(), "tests/guided/fixtures/states.json"), "utf8"));
const STATES_EN = process.env.GUIDED_STATES_EN && existsSync(process.env.GUIDED_STATES_EN)
  ? JSON.parse(readFileSync(process.env.GUIDED_STATES_EN, "utf8")) : null;
const RUNNING_FX = process.env.RUNNING_FIXTURE && existsSync(process.env.RUNNING_FIXTURE)
  ? JSON.parse(readFileSync(process.env.RUNNING_FIXTURE, "utf8")) : null;

const LIVE_STRATEGY = "89423ecc-c76e-432c-b107-0791508542f0";
const POSITION = {
  id: "844b8037-0000-0000-0000-000000000001", strategy_id: LIVE_STRATEGY, symbol: "BSE-SEP2026-FUT", side: "buy",
  total_quantity: 800, remaining_quantity: 0, avg_entry_price: "3470.15", target_price: null, stop_loss_price: null,
  highest_price_seen: null, status: "closed", opened_at: "2026-09-07T09:34:06Z", closed_at: "2026-09-08T09:59:07Z",
  final_pnl: "-12500.25", pnl_attribution: "billed", legs_balanced: true, verification: "verified", verified_on: "2026-09-08",
  legs: [{ id: "exec-1", leg_number: 1, leg_role: "entry", side: "BUY", quantity: 800, price: "3470.15", price_display: "3470.15",
           filled_at_ist: "07/09/26, 03:04 pm", broker_order_id: "322260907150406", broker_status: "TRADED" }],
};
const LEG = { id: "exec-1", signal_id: "sig-1", leg_number: 1, leg_role: "entry", symbol: "BSE-SEP2026-FUT", side: "BUY", quantity: 200,
  order_type: "MARKET", price: "3470.15", broker_order_id: "322260907150406", broker_status: null, error_code: null, error_message: null,
  placed_at: "2026-09-07T09:34:06Z", completed_at: null };
const SIGNAL = { id: "sig-1", listing_id: "list-1", listing_title: "Strategy S1", symbol: "BSE-JUL2026-FUT", action: "ENTRY", side: "buy",
  entry: "2437.50", stop_loss: "2402.00", target: "2510.00", received_at: "2026-08-23T06:30:00Z", status: "received",
  validity: { window: "entry", valid: true, expires_at: "2026-08-23T06:35:00Z", seconds_remaining: 240 } };
const USER = { id: "u1", email: "walk4a@example.com", full_name: "Ravi Practice", phone: null, is_active: true, is_admin: false,
  telegram_chat_id: null, notification_prefs: { email: true, telegram: false }, created_at: "2026-09-06T08:00:00Z", onboarding_step: 6 };

function setLang(lang: L) {
  localStorage.clear();
  localStorage.setItem("tradetri_language", lang);
  localStorage.setItem("tradetri_language_chosen", "1");
}

/** innerText is not in jsdom: a walker that breaks lines at block elements and lists <option>s. */
const BLOCK = new Set(["DIV", "P", "H1", "H2", "H3", "H4", "H5", "H6", "LI", "TR", "SECTION", "HEADER", "FOOTER", "NAV", "BUTTON", "LABEL", "OPTION", "TD", "TH", "ARTICLE", "ASIDE", "DD", "DT", "FIELDSET", "LEGEND", "SUMMARY", "DETAILS", "OL", "UL", "TABLE", "FORM", "MAIN"]);
function textOf(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) return (node.textContent ?? "").replace(/\s+/g, " ");
  if (node.nodeType !== Node.ELEMENT_NODE) return "";
  const el = node as HTMLElement;
  if (el.tagName === "SCRIPT" || el.tagName === "STYLE") return "";
  let s = "";
  for (const c of Array.from(el.childNodes)) s += textOf(c);
  if (el.tagName === "INPUT") s += `[input${(el as HTMLInputElement).placeholder ? ` "${(el as HTMLInputElement).placeholder}"` : ""}]`;
  if (el.tagName === "SELECT") s = `[switch: ${s.trim()}]`;
  return BLOCK.has(el.tagName) ? `\n${s}\n` : s;
}
function dump(container: HTMLElement): string {
  return textOf(container).split("\n").map((l) => l.trim()).filter(Boolean).join("\n");
}

type Screen = { name: string; user?: boolean; render: (lang: L) => Promise<HTMLElement> | HTMLElement };

const wrap = (ui: ReactNode) => <LanguageProvider>{ui}</LanguageProvider>;
const settle = async () => { await act(async () => { await new Promise((r) => setTimeout(r, 0)); }); };

async function guided(stateKey: string, lang: L): Promise<HTMLElement> {
  const st = (lang === "en" && STATES_EN ? STATES_EN : STATES)[stateKey];
  localStorage.setItem("tb_access_token", "t");
  guidedApi.state.mockResolvedValue(st);
  guidedApi.publicStart.mockResolvedValue(st);
  const { container } = render(wrap(<StartLayout><GuidedPath /></StartLayout>));
  await screen.findByTestId("guided");
  return container;
}

const SCREENS: Screen[] = [
  { name: "01-home", render: async () => { const { container } = render(wrap(<PublicLayout><HomePage /></PublicLayout>)); await settle(); return container; } },
  { name: "02-pricing", render: async () => { const { container } = render(wrap(<PublicLayout><PricingPage /></PublicLayout>)); await settle(); return container; } },
  { name: "03-about", render: async () => { const { container } = render(wrap(<PublicLayout><AboutPage /></PublicLayout>)); await settle(); return container; } },
  { name: "04-contact", render: async () => { const { container } = render(wrap(<PublicLayout><ContactPage /></PublicLayout>)); await settle(); return container; } },
  { name: "05-proof", render: async () => { const { container } = render(wrap(<PublicLayout><ShowcasePage /></PublicLayout>)); await settle(); return container; } },
  { name: "06-login", render: async () => { const { container } = render(wrap(<LoginPage />)); await settle(); return container; } },
  { name: "07-register", render: async () => { const { container } = render(wrap(<RegisterPage />)); await settle(); return container; } },
  { name: "08-start-broker", render: (lang) => guided("BROKER", lang) },
  { name: "09-start-size", render: (lang) => guided("SIZE", lang) },
  { name: "10-start-confirm", render: (lang) => guided("CONFIRM", lang) },
  { name: "11-start-running", user: true, render: async (lang) => {
      const fx = RUNNING_FX ? (RUNNING_FX[lang] ?? RUNNING_FX.hinglish) : null;
      if (!fx) throw new Error("RUNNING_FIXTURE not given");
      guidedApi.running.mockResolvedValue(fx);
      const { container } = render(wrap(<StartLayout><RunningDashboard onGoto={() => {}} /></StartLayout>));
      await screen.findByTestId("running");
      return container;
  } },
  { name: "12-simple-home", user: true, render: async (lang) => {
      const { container } = render(wrap(<SimpleHomeView lang={lang as never} name="Ravi" level={1} mainTiles={MAIN_TILES} learnTiles={LEARN_TILES} onLearnTap={() => {}} onOpenPro={() => {}}
        brokerConnected={false} strategyRunning={false} learningMode signalsToday={0} latestSignal={null} signalIsNew={false}
        lesson={{ title: "—", body: "—", href: "/help" }} progress={{ done: 1, total: 4, next: "—" }} />));
      await settle(); return container;
  } },
  { name: "13-positions", user: true, render: async () => {
      apiData.current = { "/strategies": { strategies: [{ id: LIVE_STRATEGY, name: "BSE LTD Futures", is_paper: false }], count: 1 },
        "/strategies/positions": { positions: [POSITION], count: 1 } };
      const { container } = render(wrap(<PositionsPage />)); await settle(); return container;
  } },
  { name: "14-orders", user: true, render: async () => {
      apiData.current = { "/strategies": { strategies: [{ id: LIVE_STRATEGY, name: "BSE LTD Futures", is_paper: false }], count: 1 },
        "/strategies/executions": { executions: [LEG], count: 1 } };
      const { container } = render(wrap(<TradesPage />)); await settle(); return container;
  } },
  { name: "15-signals", user: true, render: async () => {
      apiData.current = { "/marketplace/subscriptions/signals": { signals: [SIGNAL], count: 1 },
        "/marketplace/subscriptions/me": { subscriptions: [{ id: "sub-1", status: "active" }], count: 1 }, "/strategies": { strategies: [], count: 0 } };
      const { container } = render(wrap(<SignalsPage />)); await settle(); return container;
  } },
  { name: "16-settings", user: true, render: async () => {
      apiData.current = {};
      const { container } = render(wrap(<SettingsPage />)); await settle(); return container;
  } },
];

afterEach(() => { cleanup(); localStorage.clear(); apiData.current = {}; requested.urls = []; authState.user = null; });

describe.skipIf(!OUT)("walk receipts", () => {
  it("renders every screen of the walk list in English and in Hinglish and writes the text", async () => {
    mkdirSync(OUT, { recursive: true });
    const index: Record<string, Record<string, number | string>> = {};
    for (const s of SCREENS) {
      index[s.name] = {};
      for (const lang of LANGS) {
        setLang(lang);
        authState.user = s.user ? USER : null;
        let text: string;
        try {
          const container = await s.render(lang);
          // the first paint is the server default; the provider hydrates the stored choice after mount
          await settle();
          text = dump(container);
        } catch (e) {
          text = `RENDER FAILED: ${(e as Error).message?.split("\n")[0]}`;
        }
        const head = `# ${s.name} · ${lang} · ${process.env.WALK_TREE ?? "tree"} · urls: ${[...new Set(requested.urls)].join(" ") || "-"}\n`;
        writeFileSync(join(OUT, `${s.name}.${lang}.txt`), head + text + "\n");
        index[s.name][lang] = text.startsWith("RENDER FAILED") ? text : text.length;
        cleanup();
        requested.urls = [];
      }
    }
    writeFileSync(join(OUT, "INDEX.json"), JSON.stringify(index, null, 1) + "\n");
    expect(Object.keys(index).length).toBe(SCREENS.length);
  }, 120_000);
});
