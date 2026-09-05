/**
 * The app has three independent language stores (found in the C2 audit):
 *   - contexts/LanguageContext        key `tradetri_language`   hi|gu|en|hinglish  (global)
 *   - components/help/LangToggle      key `tradetri_lang`       en|hi              (help, indicators, compliance)
 *   - hooks/use-algomitra-context     key `algomitra_language`  hinglish|english|hindi|gujarati|…
 *
 * Simple mode treats the global one as the source of truth and mirrors every
 * choice into the other two, so "bhasha chuno" once changes the help pages
 * and AlgoMitra as well. Pure, best-effort (localStorage may throw).
 */

import type { Lang } from "@/contexts/LanguageContext";

export const SIMPLE_LANGS: Array<{ code: Lang; label: string; native: string }> = [
  { code: "hinglish", label: "Hinglish", native: "Hinglish" },
  { code: "hi", label: "Hindi", native: "हिन्दी" },
  { code: "gu", label: "Gujarati", native: "ગુજરાતી" },
  { code: "en", label: "English", native: "English" },
];

export function mirrorLanguage(lang: Lang): void {
  try {
    window.localStorage.setItem("tradetri_language", lang);
    window.localStorage.setItem("tradetri_lang", lang === "hi" ? "hi" : "en");
    const algo =
      lang === "hi" ? "hindi" : lang === "gu" ? "gujarati" : lang === "en" ? "english" : "hinglish";
    window.localStorage.setItem("algomitra_language", algo);
  } catch {
    // private mode / quota — in-memory state still applies for this session
  }
}

/**
 * Hinglish first (the design bar): a customer who has never chosen a language
 * starts in Hinglish. Only fires when NOTHING is stored, so a choice made in
 * any of the three switches is never overridden.
 */
export function ensureSimpleDefaultLanguage(setLang: (l: Lang) => void): void {
  try {
    if (typeof window === "undefined") return;
    if (window.localStorage.getItem("tradetri_language")) return;
    setLang("hinglish");
    mirrorLanguage("hinglish");
  } catch {
    // storage unavailable — leave the provider's default alone
  }
}
