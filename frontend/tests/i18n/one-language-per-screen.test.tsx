/**
 * ONE LANGUAGE PER SCREEN (founder, 2 Oct 2026, the language ruling, item 5):
 *   "Every string that exists in Hinglish must have a proper English twin — no half-translated
 *    screen, no mixed sentence. Extend the guard test: fail if any screen has both languages at
 *    once, or a missing translation falls back to the other language mid-screen."
 *
 * Three layers, all measured, none argued:
 *   A. SOURCE  — no customer screen carries an inline Hinglish string: every word a customer reads
 *               comes from a dictionary (src/lib/i18n/copy/* or lib/simple/copy.ts), where the English
 *               twin is enforced. (This is the layer that was RED on the unconverted source.)
 *   B. DICTS   — every dictionary: `en` and `hinglish` share ONE key set (and `hi`/`gu` where present),
 *               no Hinglish word in the English block, no English sentence frame in the Hinglish block,
 *               no empty value, and the honest lines keep their exact words in every language.
 *   C. RENDER  — every screen with a harness is rendered in each of the four languages: every
 *               dictionary pick resolved to ONE language (no per-key fallback), the English render has
 *               no Hinglish marker, the Hinglish render has no English sentence frame and none of the
 *               English CTA vocabulary.
 *
 * Twins (proven 2 Oct): an inline Hinglish literal in a listed screen → A RED · a key present in
 * `hinglish` but missing in `en` → B RED · a `t()` per-key fallback → C RED.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { ReactNode } from "react";

import { CUSTOMER_SCREENS } from "../copy/customer-screens";
import { ENGLISH_CTA_WORDS } from "../copy/english-cta-words";
import { customerStrings } from "./source-strings";
import { englishLeaks, hinglishLeaks } from "./markers";

import { LanguageProvider, CHOSEN_KEY, STORAGE_KEY, type Lang } from "@/contexts/LanguageContext";
import { LANGS, i18nTrace } from "@/lib/i18n/core";
import { ALL_COPIES } from "@/lib/i18n/copy";
import { allSimpleStrings, t as simpleT } from "@/lib/simple/copy";

const ROOT = process.cwd();

/** The screens the founder named for the bilingual walk (2 Oct 2026) — THE ONE list's rows. */
export const BILINGUAL_SCREENS = [
  "S01 Login", "S02 Register", "S03 Home (public)", "S04 Pricing", "S05 Proof / Track Record", "S06 About", "S07 Contact",
  "S10 First-run onboarding (Simple)", "S11 Ghar (Simple home)", "S17 Positions", "S18 Orders / trades", "S23 Settings",
  "S25 /start — first-timer guided path", "S26 /journey — kahan tak pahunche", "S27 Aaj ke signals (signal feed)",
];
/** Dictionaries are where Hinglish is ALLOWED to live (beside its English twin). */
const DICTIONARY_FILES = /src\/lib\/(i18n\/copy\/|simple\/copy\.ts)/;

// ── A. SOURCE ─────────────────────────────────────────────────────────────────

describe("A. no customer screen carries an inline Hinglish string (all copy comes from a dictionary)", () => {
  const files = [...new Set(BILINGUAL_SCREENS.flatMap((s) => CUSTOMER_SCREENS[s] ?? []))].filter((f) => !DICTIONARY_FILES.test(f));

  it("the walk list resolves to real files", () => {
    expect(files.length).toBeGreaterThan(25);
    for (const f of files) expect(() => readFileSync(join(ROOT, f))).not.toThrow();
  });

  for (const f of files) {
    it(`${f}`, () => {
      const hits = customerStrings(readFileSync(join(ROOT, f), "utf8"))
        .map((s) => ({ ...s, words: hinglishLeaks(s.text) }))
        .filter((s) => s.words.length > 0)
        .map((s) => `L${s.line} [${s.words.join(",")}] ${s.text.slice(0, 70)}`);
      expect(hits, `${hits.length} inline Hinglish string(s)`).toEqual([]);
    });
  }
});

// ── B. DICTIONARIES ───────────────────────────────────────────────────────────

describe("B. every dictionary: one key set, pure blocks, honest lines in both voices", () => {
  it("the registry is not empty", () => {
    expect(ALL_COPIES.length).toBeGreaterThan(0);
  });

  for (const copy of ALL_COPIES) {
    describe(copy.name, () => {
      const en = copy.dicts.en as Record<string, string>;
      const hg = copy.dicts.hinglish as Record<string, string>;

      it("en and hinglish share ONE key set (and hi/gu, where present)", () => {
        const enKeys = Object.keys(en).sort();
        expect(Object.keys(hg).sort()).toEqual(enKeys);
        for (const l of ["hi", "gu"] as const) {
          const d = copy.dicts[l];
          if (d) expect(Object.keys(d).sort(), l).toEqual(enKeys);
        }
      });

      it("no empty value in any language", () => {
        for (const l of copy.langs) {
          const d = copy.dicts[l] as Record<string, string>;
          const empty = Object.entries(d).filter(([, v]) => !v || !v.trim()).map(([k]) => `${l}:${k}`);
          expect(empty).toEqual([]);
        }
      });

      it("the English block has no Hinglish word", () => {
        const bad = Object.entries(en).map(([k, v]) => [k, hinglishLeaks(v)] as const).filter(([, w]) => w.length).map(([k, w]) => `${k} [${w.join(",")}]`);
        expect(bad).toEqual([]);
      });

      it("the Hinglish block has no English sentence frame and none of the English CTA vocabulary", () => {
        const bad = Object.entries(hg)
          .map(([k, v]) => [k, [...englishLeaks(v), ...ENGLISH_CTA_WORDS.filter((re) => re.test(v)).map(String)]] as const)
          .filter(([, w]) => w.length)
          .map(([k, w]) => `${k} [${w.join(",")}]`);
        expect(bad).toEqual([]);
      });

      it("the honest words are identical in every language (NOT MEASURED · the practice line's facts)", () => {
        for (const [k, v] of Object.entries(hg)) {
          if (/NOT MEASURED/.test(v)) expect(en[k], k).toMatch(/NOT MEASURED/);
          if (/^Practice mode:/.test(v)) {
            // same facts, same weight: dummy orders · no real money · no order reaches a broker
            expect(en[k], k).toMatch(/^Practice mode:/);
            expect(en[k], k).toMatch(/dummy/);
            expect(en[k], k).toMatch(/no real money/);
            expect(en[k], k).toMatch(/no order reaches/);
          }
        }
      });
    });
  }

  it("lib/simple/copy.ts: four complete languages, and the English block has no Hinglish word", () => {
    const byLang = new Map<string, string[]>();
    for (const s of allSimpleStrings()) byLang.set(s.lang, [...(byLang.get(s.lang) ?? []), s.key]);
    expect([...byLang.keys()].sort()).toEqual(["en", "gu", "hi", "hinglish"]);
    const sizes = new Set([...byLang.values()].map((v) => v.length));
    expect(sizes.size).toBe(1);
    const bad = allSimpleStrings().filter((s) => s.lang === "en").map((s) => [s.key, hinglishLeaks(s.text)] as const).filter(([, w]) => w.length).map(([k, w]) => `${k} [${w.join(",")}]`);
    expect(bad).toEqual([]);
  });
});

// ── C. RENDER ─────────────────────────────────────────────────────────────────

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: null, isLoading: false, isAuthenticated: false, login: vi.fn(), register: vi.fn(), logout: vi.fn(), refreshUser: vi.fn() }),
  useAuthOptional: () => null,
}));
vi.mock("@/hooks/useSignupOpen", () => ({ useSignupOpen: () => "closed" }));
vi.mock("@/hooks/useGuidedPathLive", () => ({ useGuidedPathLive: () => "off" }));
vi.mock("@/components/auth/return-path-probe", () => ({ ReturnPathProbe: () => null }));
vi.mock("@/components/mantras-modal", () => ({ MantrasModal: () => null }));
vi.mock("@/shared/api/client", () => ({ api: { get: vi.fn(), post: vi.fn(), put: vi.fn() }, ApiError: class extends Error {} }));
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

import { PracticeBanner } from "@/components/site/practice-banner";
import { SimpleHomeView } from "@/components/simple/simple-home-view";
import { LEARN_TILES, MAIN_TILES } from "@/lib/simple/level";
import LoginPage from "@/app/(auth)/login/page";
import RegisterPage from "@/app/(auth)/register/page";
import StartLayout from "@/app/start/layout";

function forceLang(lang: Lang) {
  localStorage.setItem(STORAGE_KEY, lang);
  localStorage.setItem(CHOSEN_KEY, "1");
}

/** Render `ui` in every language; return per-language text + the resolved language of the picks. */
export function renderEveryLanguage(ui: (lang: Lang) => ReactNode): Record<Lang, { text: string; resolved: Set<Lang>; fallbacks: number }> {
  const out = {} as Record<Lang, { text: string; resolved: Set<Lang>; fallbacks: number }>;
  for (const lang of LANGS) {
    cleanup();
    forceLang(lang);
    i18nTrace.enabled = true;
    i18nTrace.reset();
    const r = render(<LanguageProvider>{ui(lang)}</LanguageProvider>);
    // the provider's FIRST paint is the SSR default (English) until its mount effect reads the device
    // storage — the same two paints a browser does. The screen a customer READS is the hydrated one,
    // so the trace is reset after hydration and the tree re-rendered once in the stable language.
    i18nTrace.reset();
    r.rerender(<LanguageProvider>{ui(lang)}</LanguageProvider>);
    const { container } = r;
    const picks = i18nTrace.events.filter((e) => e.kind === "pick");
    out[lang] = {
      text: container.textContent ?? "",
      resolved: new Set(picks.map((e) => e.resolved)),
      fallbacks: i18nTrace.events.filter((e) => e.kind === "fallback").length,
    };
    i18nTrace.enabled = false;
  }
  return out;
}

/** The founder's rule, as assertions, for one screen's four renders. */
export function expectOneLanguage(name: string, r: ReturnType<typeof renderEveryLanguage>) {
  for (const lang of LANGS) {
    const { text, resolved, fallbacks } = r[lang];
    expect(fallbacks, `${name} [${lang}]: per-key fallback`).toBe(0);
    expect(resolved.size, `${name} [${lang}]: picks resolved to ${[...resolved].join("+")}`).toBeLessThanOrEqual(1);
    const shown = resolved.size === 1 ? [...resolved][0] : lang;
    if (shown === "en") expect(hinglishLeaks(text), `${name} [${lang}→en]: Hinglish on an English screen`).toEqual([]);
    if (shown === "hinglish") {
      expect(englishLeaks(text), `${name} [hinglish]: an English sentence on a Hinglish screen`).toEqual([]);
      expect(ENGLISH_CTA_WORDS.filter((re) => re.test(text)).map(String), `${name} [hinglish]: English CTA words`).toEqual([]);
    }
  }
}

const simpleHome = (lang: Lang) => (
  <SimpleHomeView
    lang={lang}
    name="Ramesh"
    level={1}
    mainTiles={MAIN_TILES}
    learnTiles={LEARN_TILES}
    onLearnTap={() => {}}
    onOpenPro={() => {}}
    brokerConnected={false}
    strategyRunning={false}
    learningMode
    signalsToday={0}
    latestSignal={null}
    signalIsNew={false}
    lesson={{ title: simpleT(lang, "lesson_title"), body: "…", href: "/help" }}
    progress={{ done: 1, total: 4, next: simpleT(lang, "req_broker") }}
  />
);

beforeEach(() => {
  localStorage.clear();
});
afterEach(() => {
  cleanup();
  i18nTrace.enabled = false;
  localStorage.clear();
});

describe("C. rendered screens: one language at a time, in all four", () => {
  it("the practice banner", () => {
    expectOneLanguage("practice banner", renderEveryLanguage(() => <PracticeBanner />));
  });
  it("/start layout (banner + switch)", () => {
    expectOneLanguage("/start layout", renderEveryLanguage(() => <StartLayout><p>…</p></StartLayout>));
  });
  it("Simple home", () => {
    expectOneLanguage("Simple home", renderEveryLanguage(simpleHome));
  });
  it("/login", () => {
    expectOneLanguage("/login", renderEveryLanguage(() => <LoginPage />));
  });
  it("/register", () => {
    expectOneLanguage("/register", renderEveryLanguage(() => <RegisterPage />));
  });

  it("the trace catches a per-key fallback (self-check of layer C)", () => {
    i18nTrace.enabled = true;
    i18nTrace.reset();
    // a language we know is complete must produce ZERO fallbacks …
    simpleT("en", "tile_help");
    expect(i18nTrace.events.filter((e) => e.kind === "fallback")).toHaveLength(0);
    // … and a key that is absent in a language must be reported, not silently filled in
    simpleT("en", "__definitely_missing__" as never);
    expect(i18nTrace.events.filter((e) => e.kind === "fallback")).toHaveLength(1);
    i18nTrace.enabled = false;
  });
});
