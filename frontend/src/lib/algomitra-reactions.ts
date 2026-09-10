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
 *
 * ⚠️ WHY THE POLARITY GUARD EXISTS — READ BEFORE EDITING THE TABLE
 * ───────────────────────────────────────────────────────────────
 * On 2026-09-09 this module printed "🚀 ₹1,95,831! Killer day." over a
 * LOSS. The bug was upstream (the caller handed it a garbage amount), but
 * the module HAPPILY RENDERED IT: ``renderReaction`` was a total function
 * over the wrong domain — it accepted any (trigger, amount) pair and
 * interpolated whatever number it was given into whatever copy the trigger
 * named. Handed -50000 with "profit-huge" it produced "🚀 -₹50,000! Killer
 * day.", and with "profit-big"/evening "+-₹50,000".
 *
 * So the pairing is now checked HERE, at the only place the copy is
 * produced, and a mismatched pairing RENDERS NOTHING (``null``) rather than
 * a cheerful sentence about a loss:
 *
 *   every trigger declares a polarity (``TRIGGER_POLARITY``)
 *   a "gain" trigger refuses a negative amount
 *   a "loss" trigger refuses a positive amount
 *   a non-finite amount is refused by both
 *
 * The guard is applied by WRAPPING the template table at construction time
 * (see ``REACTIONS`` below), not by asking each of the 28 templates to
 * remember — a fifth language or an eighth trigger is guarded the moment it
 * is added, with no new discipline required of the author.
 *
 * ``inr`` is magnitude-only for the same reason: after the guard there is no
 * legitimate call site with a negative number, and a formatter that cannot
 * emit "-₹" cannot be talked into "+-₹".
 */

import type { Language } from "./language-detector";
import type { TimeOfDay } from "./algomitra-personality";

// ─── Exhaustive axis lists ───────────────────────────────────────────────

/**
 * A compile-time check that a literal list names EVERY member of a union.
 *
 * The tests enumerate (language × trigger × time-of-day) from the arrays
 * below, so an axis that silently loses a member would silently lose its
 * test coverage — exactly the failure mode a fifth language would create.
 * When a member is missing, the intersection collapses the element type to
 * ``never`` and ``tsc --noEmit`` fails on the list itself. (Proven by
 * deleting "gu" from REACTION_LANGUAGES: 3 errors on the literal.)
 */
type Complete<T extends string, L extends readonly T[]> = [T] extends [L[number]]
  ? unknown
  : ["exhaustive list is missing", Exclude<T, L[number]>];

function exhaustive<T extends string>() {
  return <L extends readonly T[]>(members: L & Complete<T, L>): L => members;
}

// ─── Trigger taxonomy ────────────────────────────────────────────────────

export type ReactionTriggerId =
  | "profit-small"
  | "profit-big"
  | "profit-huge"
  | "loss-small"
  | "loss-medium"
  | "loss-big"
  | "recovery";

/** Every trigger, exhaustively. The tests cross this with the other axes. */
export const REACTION_TRIGGERS = exhaustive<ReactionTriggerId>()([
  "profit-small",
  "profit-big",
  "profit-huge",
  "loss-small",
  "loss-medium",
  "loss-big",
  "recovery",
] as const);

/** Every language the table speaks, exhaustively. */
export const REACTION_LANGUAGES = exhaustive<Language>()([
  "hinglish",
  "en",
  "hi",
  "gu",
] as const);

/** Every time-of-day branch the templates switch on, exhaustively. */
export const REACTION_TIMES_OF_DAY = exhaustive<TimeOfDay>()([
  "morning",
  "afternoon",
  "evening",
  "night",
] as const);

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

// ─── Polarity: which sign of money each trigger is allowed to talk about ─

/**
 * ``gain`` copy celebrates or reassures upward; ``loss`` copy consoles or
 * halts. A trigger may only ever be rendered with an amount of its own
 * polarity — see the header note.
 *
 * ``recovery`` is a GAIN: ``selectTrigger`` only reaches it on a flip from
 * negative to non-negative, so its amount is the post-flip (≥ 0) number.
 */
export const TRIGGER_POLARITY = {
  "profit-small": "gain",
  "profit-big": "gain",
  "profit-huge": "gain",
  "loss-small": "loss",
  "loss-medium": "loss",
  "loss-big": "loss",
  recovery: "gain",
} as const satisfies Record<ReactionTriggerId, "gain" | "loss">;

/**
 * May this trigger be rendered with this amount?
 *
 * Zero fits both polarities (flat is neither a win nor a loss, and both
 * families read sensibly at zero). A non-finite amount fits NEITHER — there
 * is no honest sentence to build out of NaN.
 */
export function amountFitsTrigger(
  trigger: ReactionTriggerId,
  amount: number,
): boolean {
  if (!Number.isFinite(amount)) return false;
  return TRIGGER_POLARITY[trigger] === "gain" ? amount >= 0 : amount <= 0;
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

/** A raw template — only ever called with an amount that fits the trigger. */
type RawTemplateFn = (amount: number, tod: TimeOfDay) => RenderedReaction;

/** A guarded template: refuses a mismatched pairing by returning ``null``. */
export type TemplateFn = (
  amount: number,
  tod: TimeOfDay,
) => RenderedReaction | null;

/**
 * Format a rupee MAGNITUDE as "₹1,234".
 *
 * Magnitude-only on purpose: the polarity guard means no call site can hold
 * a number whose sign the surrounding copy has not already accounted for, so
 * a sign here could only ever contradict the sentence around it ("+-₹50,000"
 * was a real string this module produced). The sign lives in the words.
 */
function inr(n: number): string {
  return `₹${Math.abs(Math.round(n)).toLocaleString("en-IN")}`;
}

const RAW_REACTIONS: Record<Language, Record<ReactionTriggerId, RawTemplateFn>> = {
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

/** Wrap one raw template in the polarity guard. */
function guarded(trigger: ReactionTriggerId, raw: RawTemplateFn): TemplateFn {
  return (amount, tod) =>
    amountFitsTrigger(trigger, amount) ? raw(amount, tod) : null;
}

/**
 * THE template table, every entry wrapped in the polarity guard.
 *
 * Built by mapping over ``RAW_REACTIONS``'s OWN KEYS — not over
 * ``REACTION_LANGUAGES`` / ``REACTION_TRIGGERS`` — for two reasons:
 *
 *   the guard cannot be forgotten on a newly added entry, because nobody
 *   applies it by hand;
 *
 *   ``Object.keys(REACTIONS)`` therefore reports what the TABLE actually
 *   contains, so the test's both-directions assertion against the axis
 *   lists is a real check on drift rather than a tautology. Deriving the
 *   table from the axis lists would have made the two agree by
 *   construction and the assertion would have proved nothing.
 */
export const REACTIONS: Record<Language, Record<ReactionTriggerId, TemplateFn>> =
  Object.fromEntries(
    Object.entries(RAW_REACTIONS).map(([lang, byTrigger]) => [
      lang,
      Object.fromEntries(
        Object.entries(byTrigger).map(([trigger, raw]) => [
          trigger,
          guarded(trigger as ReactionTriggerId, raw),
        ]),
      ),
    ]),
  ) as Record<Language, Record<ReactionTriggerId, TemplateFn>>;

/**
 * Render a reaction for the given trigger / language / time of day.
 *
 * TOTAL over its whole input domain: every (trigger, amount, lang, tod) has
 * an answer, and for a pairing whose signs disagree that answer is ``null``
 * — nothing is rendered. Callers MUST treat ``null`` as "say nothing"; there
 * is no fallback sentence, because the only sentences available would be the
 * wrong ones.
 */
export function renderReaction(
  trigger: ReactionTriggerId,
  amount: number,
  lang: Language,
  tod: TimeOfDay,
): RenderedReaction | null {
  return REACTIONS[lang][trigger](amount, tod);
}
