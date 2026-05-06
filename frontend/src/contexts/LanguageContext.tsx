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
  setLang: (lang: Lang) => void;
}

const STORAGE_KEY = "tradetri_language";
const DEFAULT_LANG: Lang = "en";

function detectFromNavigator(): Lang {
  if (typeof navigator === "undefined") return DEFAULT_LANG;
  const nav = navigator.language?.toLowerCase() ?? "";
  if (nav.startsWith("gu")) return "gu";
  if (nav.startsWith("hi")) return "hi";
  return "en";
}

function isLang(v: unknown): v is Lang {
  return v === "hi" || v === "gu" || v === "en" || v === "hinglish";
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  // SSR-safe: start with default, hydrate real value on mount.
  const [lang, setLangState] = useState<Lang>(DEFAULT_LANG);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (isLang(stored)) {
        setLangState(stored);
        return;
      }
      setLangState(detectFromNavigator());
    } catch {
      setLangState(detectFromNavigator());
    }
  }, []);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // localStorage unavailable (private mode, quota) — keep in-memory state.
    }
  }, []);

  return (
    <LanguageContext.Provider value={{ lang, setLang }}>
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
