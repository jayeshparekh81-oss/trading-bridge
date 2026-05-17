/**
 * Indicator content registry — single index for the educational
 * content layer. Pages/components import from here, not from
 * individual content files, so we have one place to swap the
 * runtime shape (server-fetched vs static) later.
 *
 * Adding a new indicator:
 *   1. Create `frontend/src/lib/indicators/content/<slug>.ts`
 *      exporting a `const <SLUG>: IndicatorContent = {...}`.
 *   2. Import + add to `INDICATORS` below.
 *   3. The completeness test in `tests/indicators/registry.test.ts`
 *      auto-asserts the new entry is well-formed.
 */

import type { IndicatorContent } from "./content/_types";

import { CCI } from "./content/cci";
import { EMA } from "./content/ema";
import { MACD } from "./content/macd";
import { RSI } from "./content/rsi";
import { SMA } from "./content/sma";
import { STOCHASTIC } from "./content/stochastic";
import { WILLIAMS_R } from "./content/williams-r";
import { WMA } from "./content/wma";

export type { IndicatorContent } from "./content/_types";
export type {
  IndicatorCategory,
  IndicatorComplexity,
  UseCase,
  IndicatorSignal,
} from "./content/_types";

// Indicators register themselves below as their content files are
// authored. Keep insertion order = priority order (matches the P1
// build plan; the glossary page uses `listIndicators()` which sorts
// alphabetically, so this ordering is internal-only).
export const INDICATORS: Readonly<Record<string, IndicatorContent>> = {
  rsi: RSI,
  macd: MACD,
  stochastic: STOCHASTIC,
  "williams-r": WILLIAMS_R,
  cci: CCI,
  ema: EMA,
  sma: SMA,
  wma: WMA,
};

/** Total indicator count — derived so tests can assert a stable
 *  contract without re-reading the registry shape. */
export const INDICATOR_COUNT = Object.keys(INDICATORS).length;

/** Look up an indicator by slug. Returns null when the slug isn't
 *  registered — callers should display a friendly "no content yet"
 *  fallback rather than crashing. */
export function getIndicator(slug: string): IndicatorContent | null {
  return INDICATORS[slug] ?? null;
}

/** All indicators sorted alphabetically by display name — handy for
 *  glossary-style listings. */
export function listIndicators(): IndicatorContent[] {
  return Object.values(INDICATORS).sort((a, b) =>
    a.name.localeCompare(b.name),
  );
}

/** Filter helper used by the glossary page. */
export function filterIndicators(opts: {
  category?: IndicatorContent["category"];
  complexity?: IndicatorContent["complexity"];
  query?: string;
}): IndicatorContent[] {
  const q = (opts.query ?? "").trim().toLowerCase();
  return listIndicators().filter((ind) => {
    if (opts.category && ind.category !== opts.category) return false;
    if (opts.complexity && ind.complexity !== opts.complexity) return false;
    if (q === "") return true;
    return (
      ind.name.toLowerCase().includes(q) ||
      ind.slug.toLowerCase().includes(q) ||
      ind.one_liner_en.toLowerCase().includes(q) ||
      ind.one_liner_hi.toLowerCase().includes(q)
    );
  });
}
