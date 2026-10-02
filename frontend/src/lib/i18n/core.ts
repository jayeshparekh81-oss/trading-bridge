/**
 * ONE LANGUAGE PER SCREEN — the customer copy layer (founder, 2 Oct 2026, the language ruling):
 *
 *   1. DEFAULT = ENGLISH for everyone (new and existing accounts that never chose).
 *   2. Hinglish stays available and obvious from the first screen (the switch in every header).
 *   3. Four options: English · Hinglish · हिन्दी · ગુજરાતી.
 *   4. The choice is remembered per account, across logout/login (components/site/language-account-sync).
 *   5. Every Hinglish string has a proper English twin — no half-translated screen, no mixed sentence.
 *   6. The honest lines (practice banner, NOT MEASURED, risk and basis lines) stay as honest in English.
 *
 * HOW A SCREEN GETS ITS WORDS: a `defineCopy()` dictionary per screen with an `en` block and a `hinglish`
 * block that share ONE key set (and `hi` / `gu` where they exist). A screen calls `useCopy(dict)` and
 * reads `c.key`. There is NO per-key fallback: `pick(lang)` resolves the WHOLE dictionary to one
 * language — the requested one when the dictionary has it, else English — so a screen can never show
 * two languages at once. Where हिन्दी / ગુજરાતી do not exist for a screen yet, that whole screen reads
 * in English (stated on the switch's screen list in LIVE_WALK_PROOF), never half in Hinglish.
 *
 * THE TRACE (`i18nTrace`) is a test-only recorder: every `pick()` reports which language it resolved
 * to, and the guard test (tests/i18n/one-language-per-screen.test.tsx) fails a render whose picks
 * resolved to different languages, or that fell back per key. Off in production (zero cost).
 */

import { DEFAULT_LANG, type Lang, useLanguageOptional } from "@/contexts/LanguageContext";

export type { Lang };
export { DEFAULT_LANG };

/** The four options, in the order every switch shows them (English first — it is the default). */
export const LANGS: readonly Lang[] = ["en", "hinglish", "hi", "gu"];

export interface TraceEvent {
  dict: string;
  requested: Lang;
  resolved: Lang;
  /** "pick" = a whole-dictionary resolve · "fallback" = a per-key fallback (never allowed on a screen). */
  kind: "pick" | "fallback";
  key?: string;
}

export const i18nTrace: { enabled: boolean; events: TraceEvent[]; reset(): void } = {
  enabled: false,
  events: [],
  reset() {
    this.events = [];
  },
};

export type Dicts<K extends string> = {
  en: Record<K, string>;
  hinglish: Record<K, string>;
  hi?: Record<K, string>;
  gu?: Record<K, string>;
};

export interface Copy<K extends string> {
  readonly name: string;
  readonly dicts: Dicts<K>;
  /** The languages this dictionary carries in full. */
  readonly langs: readonly Lang[];
  /** The language the WHOLE screen renders in for a requested language (never per key). */
  resolve(lang: Lang): Lang;
  pick(lang: Lang): Record<K, string>;
  text(lang: Lang, key: K, vars?: Record<string, string | number>): string;
}

/** `{name}` placeholders. A missing var is left visible as `{name}` so a test can see it. */
export function fill(s: string, vars?: Record<string, string | number>): string {
  if (!vars) return s;
  return s.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m));
}

export function defineCopy<K extends string>(name: string, dicts: Dicts<K>): Copy<K> {
  const langs = (Object.keys(dicts) as Lang[]).filter((l) => dicts[l]);
  function resolve(lang: Lang): Lang {
    return dicts[lang] ? lang : "en";
  }
  function pick(lang: Lang): Record<K, string> {
    const resolved = resolve(lang);
    if (i18nTrace.enabled) i18nTrace.events.push({ dict: name, requested: lang, resolved, kind: "pick" });
    return dicts[resolved] as Record<K, string>;
  }
  function text(lang: Lang, key: K, vars?: Record<string, string | number>): string {
    return fill(pick(lang)[key], vars);
  }
  return { name, dicts, langs, resolve, pick, text };
}

/** The screen's words in the customer's language. Safe outside a LanguageProvider (English). */
export function useCopy<K extends string>(copy: Copy<K>): { c: Record<K, string>; lang: Lang } {
  const ctx = useLanguageOptional();
  // Provider-less (tests, isolated components): the device's explicit choice, else English.
  const lang = ctx?.lang ?? currentLang();
  return { c: copy.pick(lang), lang };
}

const STORAGE_KEY = "tradetri_language";
const CHOSEN_KEY = "tradetri_language_chosen";

function isLang(v: unknown): v is Lang {
  return v === "hi" || v === "gu" || v === "en" || v === "hinglish";
}

/**
 * The customer's language OUTSIDE React (error lines built in a plain function, a toast from the auth
 * provider). Reads the same two keys the provider writes; on the server, or with no explicit choice
 * on this device, it is the default — English.
 */
export function currentLang(): Lang {
  try {
    if (typeof window === "undefined") return DEFAULT_LANG;
    if (window.localStorage.getItem(CHOSEN_KEY) !== "1") return DEFAULT_LANG;
    const v = window.localStorage.getItem(STORAGE_KEY);
    return isLang(v) ? v : DEFAULT_LANG;
  } catch {
    return DEFAULT_LANG;
  }
}
