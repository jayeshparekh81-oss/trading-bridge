"use client";

/**
 * THE language switch — one component, mounted in every header a first-timer can meet
 * (founder, 2 Oct 2026: "the language switch visible on the landing page, on /start and in the
 * header, not buried in settings. A first-timer must see it without hunting."):
 *   · the public site's top bar (desktop + the phone menu)      app/(public)/layout.tsx
 *   · the two auth doors                                         app/(auth)/layout.tsx
 *   · /start (the guided path)                                   app/start/layout.tsx
 *   · the Pro header                                             components/dashboard/top-bar.tsx
 *   · the Simple shell's header                                  components/simple/simple-shell.tsx
 *   · Settings (the mode card keeps its four buttons)            components/simple/mode-card.tsx
 *
 * Four options in native script, English first (the default). Choosing is an EXPLICIT choice:
 * remembered on this device and on the account (components/site/language-account-sync).
 */

import { Languages } from "lucide-react";

import { useLanguageOptional, type Lang } from "@/contexts/LanguageContext";
import { SIMPLE_LANGS } from "@/lib/simple/language-sync";
import { cn } from "@/shared/lib/utils";

/** The control's own label, in the language showing (a language NAME is never translated). */
export const SWITCH_LABEL: Record<Lang, string> = {
  en: "Language",
  hinglish: "Bhasha",
  hi: "भाषा",
  gu: "ભાષા",
};

export function LanguageSwitch({ className, id = "language-switch" }: { className?: string; id?: string }) {
  const ctx = useLanguageOptional();
  // Outside a LanguageProvider (isolated renders) there is nothing to switch — render nothing rather than crash.
  if (!ctx) return null;
  const { lang, setLang } = ctx;
  return (
    <label className={cn("inline-flex items-center gap-1.5", className)} htmlFor={id}>
      <Languages className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <span className="sr-only">{SWITCH_LABEL[lang]}</span>
      <select
        id={id}
        data-testid="language-switch"
        aria-label={SWITCH_LABEL[lang]}
        value={lang}
        onChange={(e) => setLang(e.target.value as Lang)}
        className="min-h-9 rounded-full border border-border bg-transparent px-2.5 py-1 text-sm font-medium text-foreground focus:outline-none focus-visible:border-profit"
      >
        {SIMPLE_LANGS.map((l) => (
          <option key={l.code} value={l.code} className="bg-surface-panel text-foreground">
            {l.native}
          </option>
        ))}
      </select>
    </label>
  );
}
