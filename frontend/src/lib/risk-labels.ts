/**
 * Per-segment RISK LABELS — founder's editorial judgement, NOT computed risk.
 *
 * ⚠️ READ THIS BEFORE CHANGING ANY COPY HERE.
 *
 * These three labels (Cash = LOW, Futures = MEDIUM, Options = HIGH) are a
 * plain-language statement about what each SEGMENT is like by its nature. They
 * are NOT derived from a backtest, NOT a score, and NOT a rating of any
 * particular strategy. Two hard rules follow from that, and both are enforced
 * by tests in tests/risk/risk-labels.test.tsx:
 *
 *   1. The UI must never present these as measured. That is why `RiskChip`
 *      renders no number, no "/100", and no AnimatedNumber — it must look
 *      deliberately UNLIKE the certified stat tiles — and why EDITORIAL_NOTE
 *      is rendered as visible copy next to the chip, never tooltip-only.
 *
 *   2. Every certified performance number we publish (drawdown, win-rate,
 *      profit factor, P&L) is FUTURES-priced (NRML). A Cash or Options label
 *      must therefore never sit beside those numbers in a way that implies
 *      they belong to that segment. Hence FUTURES_BASIS_LABEL /
 *      CROSS_SEGMENT_METRICS_WARNING below, and the guard test asserting the
 *      chip never renders inside the certified-metrics container.
 *
 * Because the marketplace API does not expose a strategy's instrument_type
 * yet, the marketplace surface shows all three segments together as an
 * EDUCATIONAL legend (`RiskLegend`) rather than one chip claiming to describe
 * a strategy whose segment we cannot verify. The showcase page is the one
 * place a single chip is truthful today: it is unambiguously futures (NRML).
 */

export const RISK_SEGMENTS = ["cash", "futures", "options"] as const;
export type RiskSegment = (typeof RISK_SEGMENTS)[number];

export type RiskLevel = "low" | "medium" | "high";

export interface SegmentRisk {
  /** Drives colour only — never rendered as a value. */
  level: RiskLevel;
  /** Short chip text, e.g. "MEDIUM risk / medium return". */
  label: string;
  /** Customer-facing segment name. */
  segmentLabel: string;
  /** One-line plain-language "why", Hinglish (app-consistent). */
  why: string;
}

export const SEGMENT_RISK: Record<RiskSegment, SegmentRisk> = {
  cash: {
    level: "low",
    label: "LOW risk",
    segmentLabel: "Cash",
    why: "Apne paise se seedha share kharidte ho — leverage nahi, isliye risk sabse kam.",
  },
  futures: {
    level: "medium",
    label: "MEDIUM risk / medium return",
    segmentLabel: "Futures",
    why: "Leverage hai — profit bhi bada, loss bhi bada. Lot size mein chalta hai.",
  },
  options: {
    level: "high",
    label: "HIGH risk / high return",
    segmentLabel: "Options",
    why: "Premium poora zero ho sakta hai, aur time-decay roz kaatta hai.",
  },
};

/**
 * Chip tone per level, on the current green theme. Deliberately uses the
 * profit/amber/loss role tokens so low/medium/high read at a glance.
 */
export const RISK_TONE: Record<RiskLevel, string> = {
  low: "bg-profit/12 text-profit border-profit/30",
  medium: "bg-amber-400/12 text-amber-300 border-amber-300/30",
  high: "bg-loss/12 text-loss border-loss/30",
};

/**
 * The honesty line. MUST be rendered as VISIBLE copy adjacent to any risk
 * chip/legend — not hidden behind a tooltip. This is the sentence that stops
 * the labels from reading as a measured score.
 */
export const EDITORIAL_NOTE =
  "Yeh labels founder ka judgement hain — segment ki nature pe based. Ye backtest se nikala hua score NAHI hai.";

/**
 * Founder-stated MINIMUM CAPITAL guidance per segment, in rupees.
 *
 * ⚠️ Same honesty discipline as the risk labels: these are the founder's
 * stated guidance numbers, NOT a live margin computed from the broker's
 * SPAN/exposure files and NOT a per-strategy requirement. They are
 * DISPLAY-ONLY — nothing validates, gates, or rejects a subscribe on them
 * (asserted by tests). Rendered with the app's existing `formatCurrency`
 * helper so ₹ formatting stays consistent app-wide (no bespoke formatter).
 */
export const SEGMENT_MIN_CAPITAL: Record<RiskSegment, number> = {
  cash: 50_000,
  options: 200_000,
  futures: 500_000,
};

/**
 * Visible guidance line for the capital minimums. Like EDITORIAL_NOTE this is
 * rendered as plain copy, never as a stat tile, so it cannot be mistaken for a
 * broker-calculated margin figure.
 */
export const MIN_CAPITAL_NOTE =
  "Minimum capital bhi founder ki guidance hai — broker ka live margin (SPAN/exposure) calculation NAHI. Aapka actual margin broker aur contract ke hisaab se alag ho sakta hai.";

/** Shown on the certified metrics so their basis is never ambiguous. */
export const FUTURES_BASIS_LABEL = "Futures-basis (NRML)";

/**
 * Shown when a customer selects Cash or Options: our published numbers are
 * futures-priced, so we say so and show NO segment-specific metrics.
 */
export const CROSS_SEGMENT_METRICS_WARNING =
  "Humare saare published performance numbers futures-basis (NRML) hain. Cash / Options ke apne verified numbers abhi nahi hain — isliye yahan koi segment-wise metric nahi dikhaya jaata.";

/**
 * Instrument-level volatility notes. Kept SEPARATE from the segment risk
 * label on purpose: "BSE Ltd is a volatile name" is a statement about the
 * INSTRUMENT, not about Cash/Futures/Options as a segment. Conflating the two
 * would let a name-level caveat read as a segment rating (or vice-versa).
 */
export const HIGH_VOLATILITY_NAMES: Record<string, string> = {
  BSE: "BSE Ltd ek high-volatility naam hai — moves tez aur bade hote hain.",
};

/** Case-insensitive lookup of the instrument volatility note; null if none. */
export function highVolatilityNote(instrument: string | null | undefined): string | null {
  if (!instrument) return null;
  const key = instrument.trim().toUpperCase();
  return HIGH_VOLATILITY_NAMES[key] ?? null;
}
