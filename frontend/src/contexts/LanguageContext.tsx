"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type Lang = "hi" | "gu" | "en" | "hinglish";

interface LanguageContextValue {
  lang: Lang;
  /**
   * `explicit` (default true) = the customer chose it on a switch: remembered on this device AND,
   * when logged in, on the account (components/site/language-account-sync). `explicit: false` is the
   * account's stored choice being applied to this device — remembered here, never written back.
   */
  setLang: (lang: Lang, opts?: { explicit?: boolean }) => void;
  /** true once a choice (device or account) is in force; false = the default is showing. */
  chosen: boolean;
  /** true once the device storage has been read (the SSR default is never "the choice"). */
  hydrated: boolean;
  /** bumps on every EXPLICIT choice — the account sync persists on it. */
  choiceSeq: number;
}

export const STORAGE_KEY = "tradetri_language";
/**
 * 2 Oct 2026 (founder, the language ruling): DEFAULT = ENGLISH for everyone, and an EXPLICIT stored
 * choice wins. The marker below separates a choice a customer MADE from a value an earlier build wrote
 * on its own (the 2 Oct morning build forced "hinglish" into storage for everyone who had not chosen);
 * a stored language WITHOUT the marker is not a choice and the default shows — one tap away on every
 * header. Navigator language is NOT consulted any more: "for everyone" means for everyone.
 */
export const CHOSEN_KEY = "tradetri_language_chosen";
export const DEFAULT_LANG: Lang = "en";

export function isLang(v: unknown): v is Lang {
  return v === "hi" || v === "gu" || v === "en" || v === "hinglish";
}

/**
 * The LEGACY two-value language of the older screens (help pages, indicators, compliance copy,
 * the onboarding tour): their `"hi"` has always meant the HINGLISH copy (`disclaimer-text.ts`
 * header: "Hinglish (conversational), not formal Devanagari"), never Devanagari. So the ONE choice
 * maps: hinglish → "hi" (the Hinglish copy) · everything else → "en". हिन्दी / ગુજરાતી have no twin
 * in those files, so by the 2 Oct rule they render WHOLE in English there (never a mixed line).
 *
 * 2 Oct 2026 (the live defect after the publish): the footer defaulted to "hi" and read its own key,
 * so a first visitor got an English page with a Hinglish footer, and `mirrorLanguage` wrote "hi" for
 * हिन्दी (→ a Hinglish footer under a Hindi screen) and "en" for Hinglish — inverted. Every legacy
 * consumer now derives from the context through `useLegacyLang()`; the key is only mirrored OUT.
 */
export type LegacyLang = "en" | "hi";
export function legacyLang(lang: Lang | null | undefined): LegacyLang {
  return lang === "hinglish" ? "hi" : "en";
}
/** The reverse, for the older toggles that still offer only English / Hinglish. */
export function fromLegacyLang(lang: LegacyLang): Lang {
  return lang === "hi" ? "hinglish" : "en";
}

/** The other two language stores (help pages · AlgoMitra) follow the one choice. Best-effort. */
export function mirrorLanguage(lang: Lang): void {
  try {
    window.localStorage.setItem("tradetri_lang", legacyLang(lang));
    const algo = lang === "hi" ? "hindi" : lang === "gu" ? "gujarati" : lang === "en" ? "english" : "hinglish";
    window.localStorage.setItem("algomitra_language", algo);
  } catch {
    // private mode / quota — in-memory state still applies for this session
  }
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  // SSR-safe: start with the default, read the device's explicit choice on mount.
  const [lang, setLangState] = useState<Lang>(DEFAULT_LANG);
  const [chosen, setChosen] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [choiceSeq, setChoiceSeq] = useState(0);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (localStorage.getItem(CHOSEN_KEY) === "1" && isLang(stored)) {
        setLangState(stored);
        setChosen(true);
      }
    } catch {
      // storage unavailable — the default stands
    }
    setHydrated(true);
  }, []);

  const setLang = useCallback((next: Lang, opts?: { explicit?: boolean }) => {
    const explicit = opts?.explicit ?? true;
    setLangState(next);
    setChosen(true);
    try {
      localStorage.setItem(STORAGE_KEY, next);
      localStorage.setItem(CHOSEN_KEY, "1");
    } catch {
      // localStorage unavailable (private mode, quota) — keep in-memory state.
    }
    mirrorLanguage(next);
    if (explicit) setChoiceSeq((n) => n + 1);
  }, []);

  return (
    <LanguageContext.Provider value={{ lang, setLang, chosen, hydrated, choiceSeq }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext);
  if (!ctx) {
    throw new Error("useLanguage must be used within a LanguageProvider");
  }
  return ctx;
}

/** For components that may render without the provider (tests, isolated mounts): null → English. */
export function useLanguageOptional(): LanguageContextValue | null {
  return useContext(LanguageContext);
}

/**
 * The legacy two-value language, derived from THE choice: English on SSR, English with no stored
 * choice, English without a provider; "hi" (the Hinglish copy) only when the customer chose
 * Hinglish. Never reads `tradetri_lang` — that key is written by the choice, not read by screens.
 */
export function useLegacyLang(): LegacyLang {
  return legacyLang(useLanguageOptional()?.lang);
}

/**
 * The legacy toggle pair (English / Hinglish) wired to THE choice: reading follows the provider,
 * writing is an explicit choice on the provider (remembered on the device and the account). Without
 * a provider (isolated mounts) it is a local English-default state.
 */
export function useLegacyLangState(): [LegacyLang, (next: LegacyLang) => void] {
  const ctx = useLanguageOptional();
  const [local, setLocal] = useState<LegacyLang>("en");
  const set = useCallback(
    (next: LegacyLang) => {
      if (ctx) ctx.setLang(fromLegacyLang(next), { explicit: true });
      else setLocal(next);
    },
    [ctx],
  );
  return [ctx ? legacyLang(ctx.lang) : local, set];
}
