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

import { ADX } from "./content/adx";
import { ALMA } from "./content/alma";
import { ATR } from "./content/atr";
import { AWESOME_OSCILLATOR } from "./content/awesome-oscillator";
import { BALANCE_OF_POWER } from "./content/balance-of-power";
import { BOLLINGER_BANDS } from "./content/bollinger-bands";
import { CCI } from "./content/cci";
import { CHANDE_MOMENTUM_OSCILLATOR } from "./content/chande-momentum-oscillator";
import { CHOPPINESS_INDEX } from "./content/choppiness-index";
import { DMI } from "./content/dmi";
import { DMI_MINUS } from "./content/dmi-minus";
import { DEMA } from "./content/dema";
import { DMI_PLUS } from "./content/dmi-plus";
import { DONCHIAN_CHANNEL } from "./content/donchian-channel";
import { EMA } from "./content/ema";
import { EOM } from "./content/eom";
import { FIBONACCI_RETRACEMENT } from "./content/fibonacci-retracement";
import { FISHER_TRANSFORM } from "./content/fisher-transform";
import { FORCE_INDEX } from "./content/force-index";
import { GAUSSIAN_CHANNEL } from "./content/gaussian-channel";
import { HEIKIN_ASHI } from "./content/heikin-ashi";
import { HMA } from "./content/hma";
import { ICHIMOKU } from "./content/ichimoku";
import { KAMA } from "./content/kama";
import { LINEAR_REGRESSION } from "./content/linear-regression";
import { KELTNER_CHANNEL } from "./content/keltner-channel";
import { MACD } from "./content/macd";
import { MFI } from "./content/mfi";
import { MOMENTUM } from "./content/momentum";
import { NEGATIVE_VOLUME_INDEX } from "./content/negative-volume-index";
import { OBV } from "./content/obv";
import { PARABOLIC_SAR } from "./content/parabolic-sar";
import { PIVOT_POINTS } from "./content/pivot-points";
import { POSITIVE_VOLUME_INDEX } from "./content/positive-volume-index";
import { ROC } from "./content/roc";
import { RSI } from "./content/rsi";
import { SMA } from "./content/sma";
import { STANDARD_DEVIATION } from "./content/standard-deviation";
import { VOLUME_PROFILE } from "./content/volume-profile";
import { STOCHASTIC } from "./content/stochastic";
import { SUPERTREND } from "./content/supertrend";
import { SUPPORTS_RESISTANCES } from "./content/supports-resistances";
import { TEMA } from "./content/tema";
import { TRIX } from "./content/trix";
import { TSI } from "./content/tsi";
import { ULTIMATE_OSCILLATOR } from "./content/ultimate-oscillator";
import { VWAP } from "./content/vwap";
import { WILLIAMS_R } from "./content/williams-r";
import { WMA } from "./content/wma";
import { ZLEMA } from "./content/zlema";
import { MASS_INDEX } from "./content/mass-index";
import { COPPOCK_CURVE } from "./content/coppock-curve";
import { DETRENDED_PRICE_OSCILLATOR } from "./content/detrended-price-oscillator";
import { PRICE_OSCILLATOR } from "./content/price-oscillator";
import { ACCELERATOR_OSCILLATOR } from "./content/accelerator-oscillator";
import { WILLIAMS_VIX_FIX } from "./content/williams-vix-fix";
import { RELATIVE_VIGOR_INDEX } from "./content/relative-vigor-index";
import { DEMARKER } from "./content/demarker";
import { ACCUMULATION_DISTRIBUTION } from "./content/accumulation-distribution";
import { PRICE_VOLUME_TREND } from "./content/price-volume-trend";
import { KLINGER_OSCILLATOR } from "./content/klinger-oscillator";
import { ELDER_RAY_BULL_BEAR } from "./content/elder-ray-bull-bear";
import { SCHAFF_TREND_CYCLE } from "./content/schaff-trend-cycle";
import { RANDOM_WALK_INDEX } from "./content/random-walk-index";
import { LINEAR_REGRESSION_CHANNEL } from "./content/linear-regression-channel";
import { STANDARD_ERROR_CHANNEL } from "./content/standard-error-channel";
import { MCGINLEY_DYNAMIC } from "./content/mcginley-dynamic";
import { SWING_INDEX } from "./content/swing-index";

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
  supertrend: SUPERTREND,
  "parabolic-sar": PARABOLIC_SAR,
  adx: ADX,
  dmi: DMI,
  "dmi-plus": DMI_PLUS,
  "dmi-minus": DMI_MINUS,
  kama: KAMA,
  tema: TEMA,
  dema: DEMA,
  zlema: ZLEMA,
  hma: HMA,
  alma: ALMA,
  "linear-regression": LINEAR_REGRESSION,
  "choppiness-index": CHOPPINESS_INDEX,
  "fisher-transform": FISHER_TRANSFORM,
  "awesome-oscillator": AWESOME_OSCILLATOR,
  "ultimate-oscillator": ULTIMATE_OSCILLATOR,
  "balance-of-power": BALANCE_OF_POWER,
  "force-index": FORCE_INDEX,
  eom: EOM,
  "negative-volume-index": NEGATIVE_VOLUME_INDEX,
  "positive-volume-index": POSITIVE_VOLUME_INDEX,
  "chande-momentum-oscillator": CHANDE_MOMENTUM_OSCILLATOR,
  trix: TRIX,
  ichimoku: ICHIMOKU,
  "bollinger-bands": BOLLINGER_BANDS,
  atr: ATR,
  "keltner-channel": KELTNER_CHANNEL,
  "donchian-channel": DONCHIAN_CHANNEL,
  "standard-deviation": STANDARD_DEVIATION,
  vwap: VWAP,
  obv: OBV,
  "volume-profile": VOLUME_PROFILE,
  mfi: MFI,
  roc: ROC,
  momentum: MOMENTUM,
  tsi: TSI,
  "pivot-points": PIVOT_POINTS,
  "fibonacci-retracement": FIBONACCI_RETRACEMENT,
  "supports-resistances": SUPPORTS_RESISTANCES,
  "gaussian-channel": GAUSSIAN_CHANNEL,
  "heikin-ashi": HEIKIN_ASHI,
  "mass-index": MASS_INDEX,
  "coppock-curve": COPPOCK_CURVE,
  "detrended-price-oscillator": DETRENDED_PRICE_OSCILLATOR,
  "price-oscillator": PRICE_OSCILLATOR,
  "accelerator-oscillator": ACCELERATOR_OSCILLATOR,
  "williams-vix-fix": WILLIAMS_VIX_FIX,
  "relative-vigor-index": RELATIVE_VIGOR_INDEX,
  "demarker": DEMARKER,
  "accumulation-distribution": ACCUMULATION_DISTRIBUTION,
  "price-volume-trend": PRICE_VOLUME_TREND,
  "klinger-oscillator": KLINGER_OSCILLATOR,
  "elder-ray-bull-bear": ELDER_RAY_BULL_BEAR,
  "schaff-trend-cycle": SCHAFF_TREND_CYCLE,
  "random-walk-index": RANDOM_WALK_INDEX,
  "linear-regression-channel": LINEAR_REGRESSION_CHANNEL,
  "standard-error-channel": STANDARD_ERROR_CHANNEL,
  "mcginley-dynamic": MCGINLEY_DYNAMIC,
  "swing-index": SWING_INDEX,
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
