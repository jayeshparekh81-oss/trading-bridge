/**
 * Shared types for indicator educational content.
 *
 * Every file under `frontend/src/lib/indicators/content/<slug>.ts`
 * exports a constant of type `IndicatorContent` keyed off the file's
 * slug. The slugs are kebab-case, stable identifiers — never reused,
 * never renamed once published (links + bookmarks + test fixtures
 * depend on them).
 *
 * Content rules:
 *   - English copy: standard editorial English, no jargon without
 *     a definition.
 *   - Hindi copy: Hinglish (conversational) — "Aapka data safe hai..."
 *     not formal "आपका डेटा सुरक्षित है". Tests enforce this.
 *   - No code samples here — descriptions only. The strategy editor
 *     hosts the actual Pine / Python wiring; this layer is the
 *     "what is it, when to use it, what could go wrong" surface.
 */

export type IndicatorCategory =
  | "momentum"
  | "trend"
  | "volatility"
  | "volume"
  | "rate"
  | "pattern"
  | "advanced";

export type IndicatorComplexity = "beginner" | "intermediate" | "advanced";

export interface UseCase {
  scenario: string;
  what_to_do: string;
  why: string;
}

export interface IndicatorSignal {
  signal: string;
  condition: string;
  action: string;
}

export interface IndicatorContent {
  /** Stable kebab-case slug, matches the filename without `.ts`. */
  slug: string;
  /** Display name (English form, includes acronym + spelled-out). */
  name: string;
  category: IndicatorCategory;
  complexity: IndicatorComplexity;

  /** One-line summary — fits inside a tooltip. */
  one_liner_en: string;
  one_liner_hi: string;

  /** Full 3-4 paragraph explanation; `\n\n` separates paragraphs. */
  description_en: string;
  description_hi: string;

  /** Plain-English math overview (no LaTeX, no code). */
  formula_explanation: string;

  /** Library default period. */
  default_period: number | null;
  /** Acceptable user-tunable range. `null` for indicators without a
   *  period concept (e.g. Heikin-Ashi). */
  period_range: [number, number] | null;
  /** Periods that are common in Indian retail. */
  common_periods: number[];

  use_cases: UseCase[];
  common_signals: IndicatorSignal[];
  pitfalls: string[];

  /** Slugs of other indicators that pair well in a strategy. */
  works_well_with: string[];
  /** Slugs of other indicators that overlap / redundancy / clash. */
  works_poorly_with: string[];

  /** Free-text example strategy names that use this indicator. */
  example_strategies: string[];

  /** India-specific notes — NIFTY tendencies, BANKNIFTY characteristics,
   *  expiry-day quirks, MCX/cash-segment differences, etc. */
  indian_context: string;
}
