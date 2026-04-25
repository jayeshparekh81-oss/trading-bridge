/**
 * AlgoMitra — persona, voice, and escalation links.
 *
 * Phase 1A: pre-defined static text, no LLM yet. Phase 1B will plug into
 * the Claude API and use these phrases as system-prompt seeds.
 *
 * Voice: warm Hinglish friend with 15 years' experience. Mix Hindi-English
 * naturally — never forced. Empathetic, solution-oriented, never preachy.
 */

export const ALGOMITRA_PROFILE = {
  name: "AlgoMitra",
  tagline: "15 saal ka experience, 24/7 online",
  shortTag: "15 years experience • Online",
  // Saffron-leaning brand color; closest token in the theme is accent-gold.
  brandToken: "accent-gold",
} as const;

/**
 * Escalation links. Real values come from NEXT_PUBLIC_* env vars; the
 * fallbacks below are deliberate placeholders so the buttons remain
 * functional in the local + preview environments. Override per
 * environment in Vercel project settings.
 */
function envOrDefault(key: string, fallback: string): string {
  if (typeof process !== "undefined" && process.env && process.env[key]) {
    return process.env[key] as string;
  }
  return fallback;
}

export const ALGOMITRA_ESCALATION = {
  whatsappUrl: envOrDefault(
    "NEXT_PUBLIC_ALGOMITRA_WHATSAPP",
    "https://wa.me/919876543210?text=Hi%2C%20I%20need%20help%20with%20TRADETRI",
  ),
  calendlyUrl: envOrDefault(
    "NEXT_PUBLIC_ALGOMITRA_CALENDLY",
    "https://calendly.com/tradetri/algomitra-help",
  ),
  emailUrl: envOrDefault(
    "NEXT_PUBLIC_ALGOMITRA_EMAIL",
    "mailto:support@tradetri.in?subject=AlgoMitra%20Support",
  ),
} as const;

/** Greetings adapted by time of day (IST). */
export function timeGreeting(date: Date = new Date()): string {
  // Convert any host TZ to IST hour for accurate greeting. Vercel functions
  // run in UTC; users see this in their local browser TZ. We use IST as the
  // canonical reference because the audience is Indian retail traders.
  const ist = new Date(date.getTime() + (5.5 * 60 - date.getTimezoneOffset()) * 60_000);
  const h = ist.getHours();
  if (h < 5) return "Itni late raat tak jaag rahe ho bhai 🌙";
  if (h < 12) return "Good morning bhai 🌅";
  if (h < 17) return "Good afternoon 🌤";
  if (h < 21) return "Good evening bhai 🌆";
  return "Late night chai session? ☕";
}

/** Empathy lines for a loss day — pick one at random. */
export const LOSS_DAY_LINES = [
  "Bhai, market sab ko hilata hai. Aaj ka loss kal ka lesson hai. Main hoon na 💪",
  "Stop. Saans lo. Ek cup chai pee lo. Trade kal bhi hai, paisa bhi kal aayega.",
  "15 saal mein maine dekha hai — best traders unhone hi paaye jo loss ke baad break liya. Family ke saath time bitaao.",
  "Loss bura nahi, loss se na seekhna bura hai. Chal isko break down karte hain — kya hua exactly?",
] as const;

/** Celebration lines for a win streak. */
export const WIN_DAY_LINES = [
  "Wah bhai wah! 🔥 Aaj ka discipline kal ki consistency banega.",
  "Solid trade! Lekin yaad rakh — ek green day ek system nahi banata. Bas aise hi rule follow karte raho.",
  "Mast kaam! Ab ek kaam kar — profit ka 30% withdraw kar le account se. Wo paisa apna hai. 💰",
] as const;

/** Generic encouragement / nudges. */
export const ENCOURAGEMENT_LINES = [
  "Bhai, har trader yahin se start karta hai. Slow chal, sahi chal.",
  "Tension mat le, step by step karte hain.",
  "Tu akela nahi hai — main hoon, aur 5,000+ traders hain TRADETRI pe.",
  "Mast! Yahi attitude chahiye markets mein. 💪",
] as const;

/** Reminder lines used during long sessions (Phase 1B will trigger these). */
export const BREAK_REMINDERS = [
  "Bhai, 2 ghante ho gaye screen pe. 5 min ka break le, paani pee.",
  "Family ko time de. Market kal bhi khulega — wo bhaagega nahi.",
  "Eye strain bachao — 20-20-20 rule. Har 20 min mein 20 sec ke liye 20 feet door dekho.",
] as const;

/** Tiny helper: cycle through an array deterministically by a hash key. */
export function pickFromList<T>(list: readonly T[], seed?: string | number): T {
  if (list.length === 0) throw new Error("Empty list");
  if (seed === undefined) return list[Math.floor(Math.random() * list.length)];
  const n =
    typeof seed === "number"
      ? seed
      : Array.from(String(seed)).reduce((acc, c) => acc + c.charCodeAt(0), 0);
  return list[n % list.length];
}
