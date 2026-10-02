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

/** The other two language stores (help pages · AlgoMitra) follow the one choice. Best-effort. */
export function mirrorLanguage(lang: Lang): void {
  try {
    window.localStorage.setItem("tradetri_lang", lang === "hi" ? "hi" : "en");
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
