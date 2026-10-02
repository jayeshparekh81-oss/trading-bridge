/**
 * The app has three language stores (found in the C2 audit):
 *   - contexts/LanguageContext        key `tradetri_language`   en|hinglish|hi|gu  (THE choice)
 *   - components/help/LangToggle      key `tradetri_lang`       en|hi              (help, indicators, compliance)
 *   - hooks/use-algomitra-context     key `algomitra_language`  english|hinglish|hindi|gujarati|…
 *
 * The global one is the source of truth; `LanguageProvider.setLang` mirrors every choice into the
 * other two (contexts/LanguageContext `mirrorLanguage`), so one switch changes the help pages and
 * AlgoMitra as well. This module keeps the ONE list of options every switch renders.
 *
 * 2 Oct 2026 (founder, the language ruling): English is the DEFAULT and is listed first; Hinglish,
 * हिन्दी and ગુજરાતી stay as choices. The old `ensureSimpleDefaultLanguage` (which forced Hinglish on
 * anyone who had not chosen) is gone — a default is the provider's job, not a side effect of a screen.
 */

import type { Lang } from "@/contexts/LanguageContext";

export { mirrorLanguage } from "@/contexts/LanguageContext";

export const SIMPLE_LANGS: Array<{ code: Lang; label: string; native: string }> = [
  { code: "en", label: "English", native: "English" },
  { code: "hinglish", label: "Hinglish", native: "Hinglish" },
  { code: "hi", label: "Hindi", native: "हिन्दी" },
  { code: "gu", label: "Gujarati", native: "ગુજરાતી" },
];
