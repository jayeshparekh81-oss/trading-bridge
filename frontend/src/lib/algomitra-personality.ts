/**
 * AlgoMitra — persona, voice, and escalation links.
 *
 * Phase 1A: pre-defined static text, no LLM yet. Phase 1B will plug into
 * the Claude API and use these phrases as system-prompt seeds.
 *
 * Voice: warm Hinglish friend with 15 years' experience. Mix Hindi-English
 * naturally — never forced. Empathetic, solution-oriented, never preachy.
 */

import type { Language } from "./language-detector";

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

// ─── Time-of-day greetings (IST, browser-tz-independent) ────────────────

/**
 * IST hour — independent of browser timezone.
 *
 * Previous implementation used `getTimezoneOffset()` arithmetic which
 * double-shifted on browsers already set to IST (e.g., 13:41 IST read
 * as 00:41 → "late raat" greeting). This version stays in absolute
 * UTC milliseconds the whole way: shift forward by 5.5h, then read
 * `getUTCHours()`. Asia/Kolkata is UTC+5:30 with no DST so a fixed
 * offset is correct.
 */
function getIstHour(date: Date = new Date()): number {
  const istMs = date.getTime() + 5.5 * 60 * 60_000;
  return new Date(istMs).getUTCHours();
}

export type TimeOfDay = "morning" | "afternoon" | "evening" | "night";

export function getTimeOfDay(date: Date = new Date()): TimeOfDay {
  const h = getIstHour(date);
  if (h >= 5 && h < 12) return "morning"; // 05:00 – 11:59 IST
  if (h >= 12 && h < 17) return "afternoon"; // 12:00 – 16:59 IST
  if (h >= 17 && h < 21) return "evening"; // 17:00 – 20:59 IST
  return "night"; // 21:00 – 04:59 IST (wraps midnight)
}

/**
 * Per-language, per-time-of-day greeting templates. Hindi uses
 * Devanagari; Gujarati uses Gujarati script — consistent with the
 * language detector. English and Hinglish stay in Roman.
 *
 * Each template takes the user's first name. Caller is responsible
 * for falling back to "bhai" when the user object has no name.
 */
const TIME_GREETINGS: Record<
  Language,
  Record<TimeOfDay, (name: string) => string>
> = {
  hinglish: {
    morning: (n) => `Suprabhat ${n}! Markets ke liye ready ho? 🌅`,
    afternoon: (n) => `Namaste ${n}! Trading kaisi chal rahi? 🌤`,
    evening: (n) => `Hi ${n}! Market closed — recap? 🌆`,
    night: (n) => `Bhai ${n}! Late raat tak jaag rahe ho? 🌙`,
  },
  en: {
    morning: (n) => `Good morning ${n}! Ready for the markets? 🌅`,
    afternoon: (n) => `Good afternoon ${n}! How's trading going? 🌤`,
    evening: (n) => `Good evening ${n}! Market closed — recap? 🌆`,
    night: (n) => `Hi ${n}! Burning the midnight oil? 🌙`,
  },
  hi: {
    morning: (n) => `सुप्रभात ${n}! Markets के लिए ready हो? 🌅`,
    afternoon: (n) => `नमस्ते ${n}! Trading कैसी चल रही है? 🌤`,
    evening: (n) => `शुभ संध्या ${n}! Market बंद — recap? 🌆`,
    night: (n) => `Hi ${n}! देर रात तक jaag रहे ho? 🌙`,
  },
  gu: {
    morning: (n) => `સુપ્રભાત ${n}! Markets માટે ready છો? 🌅`,
    afternoon: (n) => `કેમ છો ${n}! Trading કેવી રીતે ચાલે? 🌤`,
    evening: (n) => `શુભ સંધ્યા ${n}! Market બંધ — recap? 🌆`,
    night: (n) => `Hi ${n}! મોડ સુધી જાગતા છો? 🌙`,
  },
};

/**
 * Time-of-day greeting in the user's language.
 *
 * @param lang     Detected language for this user — defaults to
 *                 hinglish (the universal fallback) when no signal
 *                 is yet available.
 * @param userName First-name fallback to "bhai" if missing.
 * @param date     Override for testing — defaults to ``new Date()``.
 */
export function timeGreeting(
  lang: Language = "hinglish",
  userName: string = "bhai",
  date: Date = new Date(),
): string {
  return TIME_GREETINGS[lang][getTimeOfDay(date)](userName);
}

/**
 * Context-aware opening question shown after the time greeting on
 * chat open. First-time visitors get the original "what kind of
 * trader are you?" framing. Returning visitors (detected via
 * ``localStorage[SEEN_INTRO_KEY]``) get a how-was-today framing.
 *
 * Both variants keep the welcome flow's chip options intact — the
 * only thing that changes is the question text.
 */
export const OPENING_QUESTIONS: Record<
  Language,
  { firstTime: string; returning: string }
> = {
  hinglish: {
    firstTime: "Bata bhai, tu trader kaisa hai?",
    returning: "Aaj trading kaisa raha bhai? Kuch help chahiye?",
  },
  en: {
    firstTime: "Tell me — what kind of trader are you?",
    returning: "How was today's trading? Need help with anything?",
  },
  hi: {
    firstTime: "बताओ भाई, तुम कैसे trader हो?",
    returning: "आज trading कैसी रही भाई? कुछ help चाहिए?",
  },
  gu: {
    firstTime: "કહો ભાઈ, તમે કેવા trader છો?",
    returning: "આજે trading કેવી રહી ભાઈ? કંઈ help જોઈએ?",
  },
};

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

// ─── Free-text intent detection ─────────────────────────────────────────

/**
 * Loss / stress signals — when any of these appear in a user message we
 * route them to the support flow's loss-intake step instead of running
 * the FAQ scorer. Empathy first, problem-solving second.
 */
export const EMOTIONAL_KEYWORDS: readonly string[] = [
  // English / Hinglish
  "loss",
  "lost",
  "lose",
  "losing",
  "down",
  "tension",
  "stressed",
  "stress",
  "depressed",
  "depress",
  "frustrated",
  "frustration",
  "sad",
  "upset",
  "angry",
  "ruined",
  "blow up",
  "blown up",
  "haar",
  "nuksaan",
  "nuksan",
  "ghaata",
  "ghata",
  "tang",
  "pareshan",
  "dukhi",
  // Hindi (Devanagari)
  "नुकसान",
  "हार",
  "तनाव",
  "परेशान",
  "दुखी",
  "घाटा",
  // Gujarati
  "નુકસાન",
  "હાર",
  "તાણ",
  "પરેશાન",
  "દુખી",
  "ઘાટો",
];

/**
 * Broad intent buckets — used when no FAQ scores high enough but the
 * user's wording still points at one of these themes. Each bucket
 * carries a chip label, an emoji, and a destination flow + step.
 */
export type Intent =
  | "beginner"
  | "strategy"
  | "risk"
  | "setup"
  | "specific";

export const INTENT_KEYWORDS: Record<Intent, readonly string[]> = {
  beginner: [
    "beginner",
    "new",
    "naya",
    "newbie",
    "start",
    "starting",
    "shuru",
    "guide me",
    "guide",
    "kaise start",
    "first time",
    "learning",
    "seekh",
  ],
  strategy: [
    "strategy",
    "strategies",
    "scalping",
    "scalper",
    "swing",
    "intraday",
    "options",
    "futures",
    "trade idea",
    "system",
  ],
  risk: [
    "risk",
    "risk management",
    "stop loss",
    "money management",
    "discipline",
    "blowup",
    "drawdown",
    "position size",
  ],
  setup: [
    "setup",
    "connect",
    "broker",
    "fyers",
    "dhan",
    "zerodha",
    "configure",
    "install",
    "webhook",
    "tradingview",
  ],
  specific: [],
};

export function detectEmotionalDistress(text: string): boolean {
  const q = text.toLowerCase();
  return EMOTIONAL_KEYWORDS.some((kw) => q.includes(kw));
}

export function detectIntents(text: string): Intent[] {
  const q = text.toLowerCase();
  const hits: Intent[] = [];
  for (const intent of Object.keys(INTENT_KEYWORDS) as Intent[]) {
    if (intent === "specific") continue;
    if (INTENT_KEYWORDS[intent].some((kw) => q.includes(kw))) {
      hits.push(intent);
    }
  }
  return hits;
}

// ─── Persona intro (sent on the user's first free-text message) ─────────

/**
 * Warm 4-area introduction. Sent as a one-shot assistant message the
 * first time a user types free text — separate from the welcome flow's
 * chip-driven greeting which always runs on chat open.
 */
export function personaIntro(userName: string): string {
  return [
    `Namaste ${userName}! 🙏`,
    "",
    "Main AlgoMitra hoon — aap ka 24x7 trading companion. 15 saal experience hai mera in 4 areas:",
    "🏨 Hospitality (premium service)",
    "🖥️ IT mentorship",
    "📊 Trading expertise (NSE/BSE since 2010)",
    "🧠 Trading psychology",
    "",
    "Kya help chahiye bhai?",
  ].join("\n");
}

// ─── Multi-language fallback copy (Free Tier: en / hi / gu / hinglish) ──

/** Friendly topic labels for the "I see you're asking about X" line. */
export const FRIENDLY_INTENT_LABELS: Record<
  Language,
  Record<Exclude<Intent, "specific">, string>
> = {
  hinglish: {
    beginner: "trading basics",
    strategy: "strategy",
    risk: "risk management",
    setup: "platform setup",
  },
  en: {
    beginner: "trading basics",
    strategy: "strategy",
    risk: "risk management",
    setup: "platform setup",
  },
  hi: {
    beginner: "trading की basics",
    strategy: "strategy",
    risk: "risk management",
    setup: "platform setup",
  },
  gu: {
    beginner: "trading ની basics",
    strategy: "strategy",
    risk: "risk management",
    setup: "platform setup",
  },
};

/**
 * Free-text fallback messages — used by the hook's
 * ``fallbackToStaticFlow`` when no FAQ matched. Each language gets two
 * variants: one for "intents detected", one fully generic.
 */
export const FALLBACK_MESSAGES: Record<
  Language,
  {
    generic: (userName: string) => string;
    intentMatched: (topics: string) => string;
  }
> = {
  hinglish: {
    generic: (n) =>
      `Bhai ${n}, bilkul guide karunga! 15 saal trading me spend kiya hai. Konsa area mein help chahiye?\n\nNiche options se choose kar, ya specific sawaal puch — main detailed batata hoon. 🎯`,
    intentMatched: (t) =>
      `Bhai, ${t} ke baare mein puch raha hai — main detail mein guide kar deta hoon. Niche se ek pick kar, ya specific sawaal type kar. 🎯`,
  },
  en: {
    generic: (n) =>
      `${n}, happy to help! 15 years in trading — pick an area below or ask a specific question and I'll go deep. 🎯`,
    intentMatched: (t) =>
      `Looks like you're asking about ${t} — I can go deeper. Pick one below or type a specific question. 🎯`,
  },
  hi: {
    generic: (n) =>
      `${n} भाई, बिल्कुल guide करूँगा! 15 साल trading में बिताए हैं। कौनसे area में help चाहिए?\n\nनीचे से एक चुनो, या specific सवाल पूछो — main detailed बताऊँगा। 🎯`,
    intentMatched: (t) =>
      `${t} के बारे में पूछ रहे हो — main detail में guide कर देता हूँ। नीचे से एक pick करो, या specific सवाल type करो। 🎯`,
  },
  gu: {
    generic: (n) =>
      `${n} ભાઈ, બિલકુલ guide કરીશ! 15 વર્ષ trading માં વિતાવ્યા છે. કયા area માં help જોઈએ?\n\nનીચે થી એક choose કરો, કે specific સવાલ પૂછો — હું detailed કહીશ. 🎯`,
    intentMatched: (t) =>
      `${t} વિશે પૂછી રહ્યા છો — હું detail માં guide કરી દઉં. નીચે થી એક pick કરો, કે specific સવાલ type કરો. 🎯`,
  },
};

/**
 * "Image received, founder will check" acknowledgment, language-aware.
 * Used after a screenshot upload.
 */
export const IMAGE_ACK_MESSAGES: Record<Language, string> = {
  hinglish:
    "Bhai photo mil gayi. 🙏 Founder ko pass kar diya — wo dekhke jaldi reply karenge.\n\nAgar urgent hai toh WhatsApp pe ping bhi kar de — direct hi pakdo.",
  en: "Got the screenshot. 🙏 Forwarded to the founder — he'll get back soon.\n\nIf it's urgent, ping him on WhatsApp directly.",
  hi: "भाई photo मिल गई। 🙏 Founder को pass कर दिया — वो देखकर जल्दी reply करेंगे।\n\nUrgent हो तो WhatsApp पर ping कर दो — directly पकड़ो।",
  gu: "ભાઈ photo મળી ગઈ. 🙏 Founder ને pass કરી દીધી — એ જોઈ ને જલ્દી reply કરશે.\n\nUrgent હોય તો WhatsApp પર ping કરી દો — directly પકડો.",
};
