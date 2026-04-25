/**
 * AlgoMitra Live Reaction templates — Phase 1C-Lite.
 *
 * Pure functions: given (delta P&L, previous delta, language, time of
 * day), pick a reaction trigger and render its message. No side
 * effects, no state — caller in the hook owns rate-limiting via
 * ``pnl-tracker``.
 *
 * 7 P&L-delta triggers in this iteration (Plan A):
 *   profit-small / profit-big / profit-huge
 *   loss-small / loss-medium / loss-big
 *   recovery (sign flip from negative to non-negative)
 *
 * Trade-event triggers (exit-with-profit, exit-with-loss, winning
 * streak) are deferred — they need trade-list diff logic.
 */

import type { Language } from "./language-detector";
import type { TimeOfDay } from "./algomitra-personality";

// ─── Trigger taxonomy ────────────────────────────────────────────────────

export type ReactionTriggerId =
  | "profit-small"
  | "profit-big"
  | "profit-huge"
  | "loss-small"
  | "loss-medium"
  | "loss-big"
  | "recovery";

export interface ReactionTriggerMeta {
  id: ReactionTriggerId;
  /** Important reactions bypass cooldown + daily cap; show even in "important only" mode. */
  important: boolean;
}

const TRIGGER_META: Record<ReactionTriggerId, ReactionTriggerMeta> = {
  "profit-small": { id: "profit-small", important: false },
  "profit-big": { id: "profit-big", important: true },
  "profit-huge": { id: "profit-huge", important: true },
  "loss-small": { id: "loss-small", important: false },
  "loss-medium": { id: "loss-medium", important: false },
  "loss-big": { id: "loss-big", important: true },
  recovery: { id: "recovery", important: true },
};

export function isImportantTrigger(id: ReactionTriggerId): boolean {
  return TRIGGER_META[id].important;
}

// ─── Threshold-based selection (ordered: most-extreme first) ───────────

/**
 * Decide which trigger fires for the given delta P&L (today's running
 * P&L approximation), considering whether it's a sign-flip from a
 * previous loss.
 *
 * Returns ``null`` when no trigger applies — most polls will land here.
 */
export function selectTrigger(
  deltaPnl: number,
  prevDeltaPnl: number | null,
): ReactionTriggerId | null {
  // Recovery wins if it applies — sign flip from loss to profit (or breakeven).
  if (prevDeltaPnl !== null && prevDeltaPnl < 0 && deltaPnl >= 0) {
    return "recovery";
  }
  if (deltaPnl >= 10000) return "profit-huge";
  if (deltaPnl >= 3000) return "profit-big";
  if (deltaPnl >= 500) return "profit-small";
  if (deltaPnl <= -5000) return "loss-big";
  if (deltaPnl <= -1000) return "loss-medium";
  if (deltaPnl <= -100) return "loss-small";
  return null;
}

// ─── Message templates ──────────────────────────────────────────────────

export interface RenderedReaction {
  emoji: string;
  message: string;
  triggerId: ReactionTriggerId;
}

type TemplateFn = (amount: number, tod: TimeOfDay) => RenderedReaction;

/** Format a positive integer as "₹1,234". Negative → "-₹1,234". */
function inr(n: number): string {
  const abs = Math.abs(Math.round(n));
  const grouped = abs.toLocaleString("en-IN");
  return n < 0 ? `-₹${grouped}` : `₹${grouped}`;
}

const REACTIONS: Record<Language, Record<ReactionTriggerId, TemplateFn>> = {
  // ─── Hinglish ──────────────────────────────────────────────────────────
  hinglish: {
    "profit-small": (a, tod) => ({
      emoji: "🎉",
      triggerId: "profit-small",
      message:
        tod === "morning"
          ? `🌅🎉 Suprabhat! ${inr(a)} se shuruaat — superb!`
          : `🎉 Wah bhai! ${inr(a)} profit aaj!`,
    }),
    "profit-big": (a, tod) => ({
      emoji: "🔥",
      triggerId: "profit-big",
      message:
        tod === "evening"
          ? `🌙🔥 Aaj ki final tally: +${inr(a)}. Discipline jeeti!`
          : `🔥 ${inr(a)}! Aaj ka din BAHUT badhiya!`,
    }),
    "profit-huge": (a) => ({
      emoji: "🚀",
      triggerId: "profit-huge",
      message: `🚀 ${inr(a)}! KILLER day bhai!`,
    }),
    "loss-small": (a) => ({
      emoji: "💚",
      triggerId: "loss-small",
      message: `💚 Chhote loss (${inr(Math.abs(a))}) me tension nahi. Bounce back!`,
    }),
    "loss-medium": (a) => ({
      emoji: "💚",
      triggerId: "loss-medium",
      message: `💚 ${inr(Math.abs(a))} down — sambhal lo bhai. Kal naya din.`,
    }),
    "loss-big": (a, tod) => ({
      emoji: "🛑",
      triggerId: "loss-big",
      message:
        tod === "night"
          ? `🌙💚 Tough day bhai (${inr(Math.abs(a))}). Rest karo, kal fresh.`
          : `🛑 Ruko bhai. ${inr(Math.abs(a))} down — naya trade mat lo abhi.`,
    }),
    recovery: (a) => ({
      emoji: "🌅",
      triggerId: "recovery",
      message: `🌅 Comeback bhai! Storm pass ho gayi — ${inr(a)} positive.`,
    }),
  },
  // ─── English ───────────────────────────────────────────────────────────
  en: {
    "profit-small": (a, tod) => ({
      emoji: "🎉",
      triggerId: "profit-small",
      message:
        tod === "morning"
          ? `🌅🎉 Good morning! Off to a +${inr(a)} start — superb.`
          : `🎉 Nice — ${inr(a)} profit today!`,
    }),
    "profit-big": (a, tod) => ({
      emoji: "🔥",
      triggerId: "profit-big",
      message:
        tod === "evening"
          ? `🌙🔥 Final tally: +${inr(a)}. Discipline pays.`
          : `🔥 ${inr(a)}! Great day so far.`,
    }),
    "profit-huge": (a) => ({
      emoji: "🚀",
      triggerId: "profit-huge",
      message: `🚀 ${inr(a)}! Killer day.`,
    }),
    "loss-small": (a) => ({
      emoji: "💚",
      triggerId: "loss-small",
      message: `💚 Small setback (${inr(Math.abs(a))}). You'll bounce back.`,
    }),
    "loss-medium": (a) => ({
      emoji: "💚",
      triggerId: "loss-medium",
      message: `💚 ${inr(Math.abs(a))} down — steady on. Tomorrow's a new day.`,
    }),
    "loss-big": (a, tod) => ({
      emoji: "🛑",
      triggerId: "loss-big",
      message:
        tod === "night"
          ? `🌙💚 Tough day (${inr(Math.abs(a))}). Rest now, fresh tomorrow.`
          : `🛑 Stop. ${inr(Math.abs(a))} down — no new trades right now.`,
    }),
    recovery: (a) => ({
      emoji: "🌅",
      triggerId: "recovery",
      message: `🌅 Comeback. Storm passed — back to +${inr(a)}.`,
    }),
  },
  // ─── Hindi (Devanagari) ────────────────────────────────────────────────
  hi: {
    "profit-small": (a, tod) => ({
      emoji: "🎉",
      triggerId: "profit-small",
      message:
        tod === "morning"
          ? `🌅🎉 सुप्रभात! ${inr(a)} se शुरुआत — superb!`
          : `🎉 वाह भाई! ${inr(a)} profit आज!`,
    }),
    "profit-big": (a, tod) => ({
      emoji: "🔥",
      triggerId: "profit-big",
      message:
        tod === "evening"
          ? `🌙🔥 आज की final tally: +${inr(a)}. Discipline जीती!`
          : `🔥 ${inr(a)}! आज का दिन बहुत badhiya!`,
    }),
    "profit-huge": (a) => ({
      emoji: "🚀",
      triggerId: "profit-huge",
      message: `🚀 ${inr(a)}! KILLER day भाई!`,
    }),
    "loss-small": (a) => ({
      emoji: "💚",
      triggerId: "loss-small",
      message: `💚 छोटे loss (${inr(Math.abs(a))}) में tension नहीं। Bounce back!`,
    }),
    "loss-medium": (a) => ({
      emoji: "💚",
      triggerId: "loss-medium",
      message: `💚 ${inr(Math.abs(a))} down — सम्भाल लो भाई। कल नया दिन।`,
    }),
    "loss-big": (a, tod) => ({
      emoji: "🛑",
      triggerId: "loss-big",
      message:
        tod === "night"
          ? `🌙💚 Tough day भाई (${inr(Math.abs(a))})। Rest करो, कल fresh।`
          : `🛑 रुको भाई। ${inr(Math.abs(a))} down — नया trade मत लो अभी।`,
    }),
    recovery: (a) => ({
      emoji: "🌅",
      triggerId: "recovery",
      message: `🌅 Comeback भाई! Storm pass हो गयी — ${inr(a)} positive।`,
    }),
  },
  // ─── Gujarati (Gujarati script) ────────────────────────────────────────
  gu: {
    "profit-small": (a, tod) => ({
      emoji: "🎉",
      triggerId: "profit-small",
      message:
        tod === "morning"
          ? `🌅🎉 સુપ્રભાત! ${inr(a)} થી શરૂઆત — superb!`
          : `🎉 વાહ ભાઈ! ${inr(a)} નો profit આજે!`,
    }),
    "profit-big": (a, tod) => ({
      emoji: "🔥",
      triggerId: "profit-big",
      message:
        tod === "evening"
          ? `🌙🔥 આજની final tally: +${inr(a)}. Discipline જીતી!`
          : `🔥 ${inr(a)}! આજનો દિવસ ખૂબ સરસ!`,
    }),
    "profit-huge": (a) => ({
      emoji: "🚀",
      triggerId: "profit-huge",
      message: `🚀 ${inr(a)}! KILLER day ભાઈ!`,
    }),
    "loss-small": (a) => ({
      emoji: "💚",
      triggerId: "loss-small",
      message: `💚 નાનો loss (${inr(Math.abs(a))}) — tension નહીં. Bounce back!`,
    }),
    "loss-medium": (a) => ({
      emoji: "💚",
      triggerId: "loss-medium",
      message: `💚 ${inr(Math.abs(a))} down — સંભાળી લો ભાઈ. કાલે નવો દિવસ.`,
    }),
    "loss-big": (a, tod) => ({
      emoji: "🛑",
      triggerId: "loss-big",
      message:
        tod === "night"
          ? `🌙💚 Tough day ભાઈ (${inr(Math.abs(a))}). Rest કરો, કાલે fresh.`
          : `🛑 રોકો ભાઈ. ${inr(Math.abs(a))} down — નવો trade હમણાં ન લો.`,
    }),
    recovery: (a) => ({
      emoji: "🌅",
      triggerId: "recovery",
      message: `🌅 Comeback ભાઈ! Storm pass થઈ ગઈ — ${inr(a)} positive.`,
    }),
  },
};

/** Render a reaction for the given trigger / language / time of day. */
export function renderReaction(
  trigger: ReactionTriggerId,
  amount: number,
  lang: Language,
  tod: TimeOfDay,
): RenderedReaction {
  return REACTIONS[lang][trigger](amount, tod);
}
