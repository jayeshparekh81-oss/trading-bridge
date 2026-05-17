/**
 * Help-page language toggle. Same pattern as the WelcomeModal's inline
 * LangToggle but exposed as a standalone component so the help page
 * can mount it in the header without duplicating layout logic.
 *
 * Reads/writes `tradetri_lang` localStorage key so the choice persists
 * across visits and stays in sync with the onboarding tour's language.
 */

"use client";

export type Lang = "en" | "hi";

export const LS_KEY_LANG = "tradetri_lang";
const DEFAULT_LANG: Lang = "hi";

function safeRead(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeWrite(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* quota / private mode — silently drop */
  }
}

export function readLang(): Lang {
  const raw = safeRead(LS_KEY_LANG);
  return raw === "en" || raw === "hi" ? raw : DEFAULT_LANG;
}

export function writeLang(lang: Lang): void {
  safeWrite(LS_KEY_LANG, lang);
}

export interface LangToggleProps {
  lang: Lang;
  onChange: (next: Lang) => void;
}

export function LangToggle({ lang, onChange }: LangToggleProps) {
  return (
    <div
      role="group"
      aria-label="Language"
      data-testid="help-lang-toggle"
      className="inline-flex rounded-md border border-white/10 bg-black/30 p-0.5 text-xs"
    >
      <button
        type="button"
        onClick={() => onChange("en")}
        data-testid="help-lang-en"
        aria-pressed={lang === "en"}
        className={`rounded-sm px-2 py-1 transition-colors ${
          lang === "en"
            ? "bg-white/10 text-white"
            : "text-neutral-400 hover:text-neutral-200"
        }`}
      >
        English
      </button>
      <button
        type="button"
        onClick={() => onChange("hi")}
        data-testid="help-lang-hi"
        aria-pressed={lang === "hi"}
        className={`rounded-sm px-2 py-1 transition-colors ${
          lang === "hi"
            ? "bg-white/10 text-white"
            : "text-neutral-400 hover:text-neutral-200"
        }`}
      >
        हिंदी
      </button>
    </div>
  );
}
