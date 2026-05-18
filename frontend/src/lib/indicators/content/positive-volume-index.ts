import type { IndicatorContent } from "./_types";

export const POSITIVE_VOLUME_INDEX: IndicatorContent = {
  slug: "positive-volume-index",
  name: "PVI (Positive Volume Index)",
  category: "volume",
  complexity: "advanced",

  one_liner_en:
    "NVI's mirror — only updates on high-volume (up-volume) days. Tracks what retail / public participation does.",
  one_liner_hi:
    "NVI ka mirror — sirf high-volume (up-volume) days pe update hota. Retail / public participation kya karta track karta.",

  description_en:
    "PVI inverts NVI's logic. Where NVI tracks behaviour on quiet (smart-money) days, PVI tracks behaviour on noisy (retail) days — bars where volume INCREASED over the prior bar. The theory: retail-dominated up-volume days reveal 'crowd' behaviour.\n\nMechanics mirror NVI. PVI starts at 1000. Each bar where today's volume > yesterday's volume: PVI updates by today's percent price change. On low-volume bars (the smart-money quiet bars), PVI stays unchanged.\n\nFosback paired NVI and PVI as a regime-detection duo: when both NVI and PVI are above their respective 1-year EMAs, both smart and retail money are aligned bullish — strongest possible regime. When they disagree, the side that NVI confirms is usually the right side (per Fosback's research).\n\nLike NVI, PVI is slow. Useful for monthly / quarterly regime detection, not daily trading.",
  description_hi:
    "PVI NVI ki logic invert karta. NVI quiet (smart-money) days pe behaviour track karta hai, PVI noisy (retail) days pe track karta — bars jahan volume prior bar se INCREASED. Theory: retail-dominated up-volume days 'crowd' behaviour reveal karte.\n\nMechanics NVI ko mirror karte. PVI 1000 pe start. Har bar jahan today's volume > yesterday's volume: PVI today's percent price change se update. Low-volume bars (smart-money quiet bars) pe PVI unchanged.\n\nFosback ne NVI aur PVI ko regime-detection duo ki tarah paired: jab dono apni 1-year EMAs ke upar = smart aur retail dono aligned bullish — strongest possible regime. Jab disagree, NVI jo side confirm karta woh usually right side (Fosback ki research per).\n\nNVI ki tarah PVI slow hai. Monthly / quarterly regime detection ke liye useful, daily trading ke liye nahi.",

  formula_explanation:
    "PVI[0] = 1000 (seed). For each subsequent bar: if volume[i] > volume[i-1]: PVI[i] = PVI[i-1] × (1 + (close[i] - close[i-1]) / close[i-1]). Else: PVI[i] = PVI[i-1]. Output unbounded, anchored at 1000.",

  default_period: null,
  period_range: null,
  common_periods: [],

  use_cases: [
    {
      scenario: "Confirm NVI bull-regime with PVI agreement",
      what_to_do: "Long-only when BOTH daily NVI > 255-day EMA AND daily PVI > 255-day EMA",
      why: "Both smart and retail money confirming = highest-conviction regime read available from volume-flow analysis.",
    },
    {
      scenario: "Identify retail-driven bubbles (PVI > NVI gap)",
      what_to_do: "If PVI > 255-day EMA but NVI < 255-day EMA, retail is driving the move alone — risky",
      why: "Retail-only rallies without smart-money confirmation historically reverse hard.",
    },
  ],

  common_signals: [
    {
      signal: "PVI > 255-day EMA",
      condition: "PVI crosses above its 1-year EMA",
      action: "Retail / crowd participation bullish — bullish bias.",
    },
    {
      signal: "NVI / PVI divergence",
      condition: "Only one of NVI/PVI is above its EMA",
      action: "Caution — favour the side NVI confirms (Fosback).",
    },
  ],

  pitfalls: [
    "Slow signal cadence. PVI is for regime detection, not trade timing.",
    "Volume comparison is binary — doesn't capture magnitude.",
    "Indian market data may produce different historical probabilities than Fosback's US-data-derived results.",
    "Anchor value (1000) is arbitrary; absolute PVI numbers aren't comparable.",
  ],

  works_well_with: ["negative-volume-index", "ema", "obv"],
  works_poorly_with: ["volume-spike", "vwap"],

  example_strategies: [
    "NVI + PVI Double-Confirmation Bull Regime (monthly NIFTY)",
    "Retail-Bubble Detector (PVI without NVI alignment)",
  ],

  indian_context:
    "PVI on Indian indices is most useful as a 'crowded long' detector. When PVI is well above its EMA but NVI is sideways, the regime is conventionally read as retail-driven and potentially vulnerable to sharp reversals — back-test the specific PVI/NVI divergence pattern on recent NIFTY data to see how reliable the caution flag has been in your trading window before sizing on it.",
};
