/**
 * The 44 explainer slugs, with NO content imports — so a client component
 * (the template catalog card) can ask "does an explainer exist?" without
 * pulling the whole explainer registry (~130 KB of prose) into its bundle.
 * Parity with the content registry is pinned by
 * tests/templates/template-explainer-link.test.tsx.
 */

export const EXPLAINER_SLUGS: ReadonlySet<string> = new Set([
  "adx-strong-trend-filter",
  "aroon-crossover",
  "bb-mean-reversion",
  "bb-rsi-oversold",
  "bb-squeeze-breakout",
  "bollinger-pct-b-extreme",
  "camarilla-pivots-intraday",
  "cci-momentum",
  "chandelier-exit-trail",
  "cmf-confirmation",
  "doji-reversal",
  "donchian-channel-breakout",
  "ema-crossover-20-50",
  "ema-crossover-9-21",
  "engulfing-candle-reversal",
  "fibonacci-retracement-entry",
  "hammer-hanging-man-pattern",
  "heikin-ashi-trend",
  "hull-ma-trend",
  "ichimoku-cloud-crossover",
  "inside-bar-breakout",
  "keltner-channel-bounce",
  "macd-divergence",
  "macd-histogram-momentum",
  "macd-trend-signal",
  "mfi-overbought-oversold",
  "obv-divergence",
  "orb-15min",
  "parabolic-sar-reversal",
  "pdh-pdl-breakout",
  "pivot-point-bounce",
  "premarket-gap",
  "psar-ema-combo",
  "range-trading-sr",
  "rsi-divergence",
  "rsi-macd-confluence",
  "rsi-oversold-bounce",
  "squeeze-momentum",
  "stochastic-oscillator",
  "supertrend-rider",
  "triple-ema-crossover",
  "volume-spike-price-confirm",
  "vwap-bounce",
  "williams-pct-r-reversal",
]);

export function hasExplainer(slug: string): boolean {
  return EXPLAINER_SLUGS.has(slug);
}
