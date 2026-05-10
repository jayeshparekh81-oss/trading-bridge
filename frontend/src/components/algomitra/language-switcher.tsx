"use client";

/**
 * Compact language switcher rendered in the AlgoMitra panel header.
 * Native dropdown — no custom popover library — so the choice is
 * keyboard-accessible and screen-reader-friendly without extra
 * a11y plumbing. The persisted value lives behind
 * :func:`useAlgoMitraLanguage` so a switch in one tab propagates
 * to every other open panel via the ``storage`` event.
 */

import { Languages } from "lucide-react";
import {
  LANGUAGE_LABELS,
  LANGUAGES,
  type Language,
} from "@/components/algomitra/coaching-tips-data";
import { useAlgoMitraLanguage } from "@/hooks/use-algomitra-context";
import { trackEventSync } from "@/lib/analytics";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

export function AlgoMitraLanguageSwitcher() {
  const { language, setLanguage } = useAlgoMitraLanguage();
  const { user } = useAuth();

  function handleChange(next: Language) {
    setLanguage(next);
    // Analytics — additive, safe-to-fail.
    if (user?.id) {
      trackEventSync(user.id, "algomitra_language_changed", {
        previous_language: language,
        new_language: next,
      });
    }
  }

  return (
    <label
      className={cn(
        "inline-flex items-center gap-1 rounded-md border border-white/[0.06]",
        "bg-white/[0.02] hover:bg-white/[0.04] transition-colors",
        "pl-2 pr-1 py-1 text-[10px] font-medium text-foreground/90",
      )}
      aria-label="AlgoMitra coaching language"
      title="Coaching language"
    >
      <Languages className="h-3 w-3 text-muted-foreground" aria-hidden />
      <select
        value={language}
        onChange={(e) => handleChange(e.target.value as Language)}
        className={cn(
          "appearance-none bg-transparent border-0 outline-none",
          "text-[10px] font-medium text-foreground cursor-pointer",
          "focus:outline-none focus:ring-0",
        )}
      >
        {LANGUAGES.map((lang) => (
          <option key={lang} value={lang} className="bg-popover">
            {LANGUAGE_LABELS[lang]}
          </option>
        ))}
      </select>
    </label>
  );
}
