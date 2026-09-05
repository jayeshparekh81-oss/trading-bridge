/**
 * "Aaj ka sabak" — one learning card a day, from content that already exists.
 *
 * Pool: `src/data/glossary.json` (30 plain-words trading terms, each with a
 * Hinglish / हिन्दी / ગુજરાતી / English explanation and an everyday example —
 * written for exactly this audience and never shipped). The card for a day is
 * deterministic (day-of-year modulo pool size) so every customer sees the same
 * lesson on the same day and a reload never changes it.
 */

import glossary from "@/data/glossary.json";
import type { Lang } from "@/contexts/LanguageContext";
import type { SimpleLesson } from "@/components/simple/simple-home-view";

interface GlossaryLangEntry {
  term?: string;
  label?: string;
  explanation?: string;
  example?: string;
}

interface GlossaryWord {
  id: string;
  category?: string;
  en?: GlossaryLangEntry;
  hi?: GlossaryLangEntry;
  gu?: GlossaryLangEntry;
  hinglish?: GlossaryLangEntry;
}

const WORDS: GlossaryWord[] = ((glossary as { words?: GlossaryWord[] }).words ?? []).filter(
  (w) => w && typeof w.id === "string",
);

export const LESSON_COUNT = WORDS.length;

function dayOfYear(d: Date): number {
  const start = Date.UTC(d.getUTCFullYear(), 0, 0);
  return Math.floor((d.getTime() - start) / 86_400_000);
}

/** The glossary entry for a language, falling back Hinglish → English. */
function pick(w: GlossaryWord, lang: Lang): GlossaryLangEntry | undefined {
  const order: Array<GlossaryLangEntry | undefined> =
    lang === "hi"
      ? [w.hi, w.hinglish, w.en]
      : lang === "gu"
        ? [w.gu, w.hinglish, w.en]
        : lang === "en"
          ? [w.en, w.hinglish]
          : [w.hinglish, w.en];
  return order.find((e) => e && e.explanation);
}

/** English entries in the glossary carry only term/label; borrow the Hinglish
 *  explanation so English readers still get a real lesson, never a blank. */
function english(w: GlossaryWord): GlossaryLangEntry | undefined {
  const en = w.en;
  const src = w.hinglish ?? w.hi;
  if (!src?.explanation) return undefined;
  return { label: en?.label ?? en?.term ?? src.label, explanation: src.explanation, example: src.example };
}

export function lessonForDay(date: Date, lang: Lang): SimpleLesson | null {
  if (WORDS.length === 0) return null;
  const idx = dayOfYear(date) % WORDS.length;
  const w = WORDS[idx];
  const e = lang === "en" ? english(w) : pick(w, lang);
  if (!e?.explanation) return null;
  const title = e.label ?? e.term ?? w.id;
  const body = e.example ? `${e.explanation} ${e.example}` : e.explanation;
  return { title, body, href: "/help" };
}

/** Every lesson in every language — for the no-jargon lint. */
export function allLessons(): Array<{ lang: Lang; id: string; text: string }> {
  const out: Array<{ lang: Lang; id: string; text: string }> = [];
  for (const w of WORDS) {
    for (const lang of ["hinglish", "hi", "gu", "en"] as Lang[]) {
      const e = lang === "en" ? english(w) : pick(w, lang);
      if (e?.explanation) out.push({ lang, id: w.id, text: `${e.label ?? ""} ${e.explanation} ${e.example ?? ""}` });
    }
  }
  return out;
}
