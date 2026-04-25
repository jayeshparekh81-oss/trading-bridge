/**
 * Free-tier language detection for AlgoMitra.
 *
 * Detects four buckets — English, Hindi (Devanagari), Gujarati
 * (Gujarati script), Hinglish (Roman + Hindi markers). Anything else
 * (Tamil, Bengali, Telugu, Kannada, Malayalam, Punjabi, Odia, …)
 * falls back to Hinglish, the closest pan-Indian middle ground we
 * have static content for. Pro tier (Phase 1B activation) replaces
 * this with full Sonnet 4.6 multi-language detection.
 */

export type Language = "en" | "hi" | "gu" | "hinglish";

/** Devanagari block — Hindi, Marathi, Sanskrit, etc. */
const DEVANAGARI = /[ऀ-ॿ]/g;

/** Gujarati block. */
const GUJARATI = /[઀-૿]/g;

/**
 * Hinglish marker words — Roman-letter Hindi tokens that almost never
 * appear in pure English. Conservative on purpose: false-positives on
 * English are worse UX than the reverse (English speakers reading
 * Hinglish get a warm but accented reply; vice versa is jarring).
 */
const HINGLISH_MARKERS = new Set<string>([
  // Verbs / particles
  "hai", "hain", "ho", "hota", "hoga", "tha", "thi", "the", "thay",
  "kar", "karo", "karen", "karein", "karta", "karna", "karunga",
  "raha", "rahe", "rahi",
  // Question words
  "kya", "kaise", "kahan", "kab", "kaun", "kyun", "kyu",
  // Pronouns / adjectives
  "mera", "meri", "mere", "mujhe", "main", "hum", "tum", "tu",
  "yeh", "ye", "woh", "wo", "jo", "kuch",
  // Common words
  "nahi", "nahin", "haan", "haa", "thoda", "bahut", "bahot", "sab",
  "chahiye", "chahta", "milega", "milta", "samjha", "samjho",
  "matlab", "phir", "fir", "abhi", "kal", "aaj",
  // Address
  "bhai", "dada", "ji", "yaar",
]);

const HINGLISH_THRESHOLD = 1; // ≥1 marker → Hinglish (text is short, be lenient)
const SCRIPT_THRESHOLD = 0.25; // ≥25% chars in script → that language

function countMatches(text: string, regex: RegExp): number {
  return (text.match(regex) ?? []).length;
}

function letterCount(text: string): number {
  return (text.match(/\p{L}/gu) ?? []).length;
}

function hinglishMarkerCount(text: string): number {
  const tokens = text.toLowerCase().split(/[^a-z]+/).filter(Boolean);
  let n = 0;
  for (const t of tokens) {
    if (HINGLISH_MARKERS.has(t)) n++;
  }
  return n;
}

/**
 * Detect the user's language bucket. Empty / whitespace / pure-numeric
 * inputs default to ``"hinglish"`` — that's our universal fallback.
 */
export function detectLanguage(text: string): Language {
  const total = letterCount(text);
  if (total === 0) return "hinglish";

  const dev = countMatches(text, DEVANAGARI);
  const guj = countMatches(text, GUJARATI);

  if (dev / total >= SCRIPT_THRESHOLD) return "hi";
  if (guj / total >= SCRIPT_THRESHOLD) return "gu";

  // ASCII-dominant text — distinguish English vs Hinglish.
  const markers = hinglishMarkerCount(text);
  if (markers >= HINGLISH_THRESHOLD) return "hinglish";

  // Pure ASCII letters with no Hinglish markers → English.
  // (Pure Tamil / Bengali / etc. land here too in their native scripts;
  // we route them to "hinglish" since we have no static content for
  // them at the free tier.)
  const asciiLetters = (text.match(/[a-zA-Z]/g) ?? []).length;
  return asciiLetters / total >= 0.8 ? "en" : "hinglish";
}

/** Display label for a language code — used in toasts and debug logs. */
export const LANGUAGE_LABELS: Record<Language, string> = {
  en: "English",
  hi: "हिंदी",
  gu: "ગુજરાતી",
  hinglish: "Hinglish",
};
