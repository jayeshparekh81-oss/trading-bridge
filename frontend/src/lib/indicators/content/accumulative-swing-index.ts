import type { IndicatorContent } from "./_types";

export const ACCUMULATIVE_SWING_INDEX: IndicatorContent = {
  slug: "accumulative-swing-index",
  name: "Accumulative Swing Index (ASI)",
  category: "trend",
  complexity: "advanced",

  one_liner_en:
    "Cumulative sum of Swing Index values — Wilder's smoothed trend indicator that catches breakouts when ASI confirms before price does.",
  one_liner_hi:
    "Swing Index values ka cumulative sum — Wilder ka smoothed trend indicator jo ASI price se pehle confirm kare to breakouts catch karta.",

  description_en:
    "The Accumulative Swing Index is Welles Wilder's intended use for the Swing Index calculation: sum the per-bar SI values cumulatively to produce a trendable line. Where Swing Index is too noisy to trade, ASI smooths via accumulation and creates a continuous trend line that responds to all aspects of price action (open-close direction, range, gaps).\n\nThe most-cited ASI trade rule from Wilder: when ASI breaks above the previous ASI peak BEFORE price breaks above the previous price peak, it's an early confirmation of an upcoming price breakout. The reverse — ASI breaking below previous low before price does — signals downside breakouts.\n\nASI's strength is leading price by 1-5 bars at key turning points. The combined open-close + range + gap math captures information that's not visible in price alone (especially gap-related accumulation patterns).\n\nFor Indian retail, ASI on F&O daily provides reliable advance warning on intermediate-term breakouts. The leading-edge nature comes at the cost of false signals (~30% false positive rate in choppy markets), so always pair with a trend filter.",
  description_hi:
    "Accumulative Swing Index Welles Wilder ka Swing Index calculation ka intended use hai: per-bar SI values cumulatively sum karke trendable line produce karna. Swing Index trade karne mein bahut noisy hota; ASI accumulation se smooth karta aur ek continuous trend line banata jo price action ke sab aspects (open-close direction, range, gaps) pe respond karti.\n\nWilder ka most-cited ASI trade rule: jab ASI previous ASI peak ke upar break kare PRICE previous price peak break karne SE PEHLE, ye upcoming price breakout ka early confirmation hai. Reverse — ASI price ke pehle previous low ke neeche break kare — downside breakouts signal karta.\n\nASI ki strength key turning points pe price ko 1-5 bars lead karna hai. Combined open-close + range + gap math jo information capture karta wo pure price mein visible nahi hota (especially gap-related accumulation patterns).\n\nIndian retail ke liye, ASI F&O daily pe intermediate-term breakouts pe reliable advance warning deta. Leading-edge nature ka cost false signals hai (~30% false positive rate choppy markets mein), to hamesha trend filter ke saath pair karo.",

  formula_explanation:
    "ASI[today] = ASI[yesterday] + SwingIndex[today]. Initial seed: ASI[0] = 0. The cumulative sum produces a line that trends with price but with subtle differences due to SI's incorporation of gaps and range factors. ASI breakouts (above/below prior ASI peaks/troughs) are watched relative to price breakouts.",

  default_period: null,
  period_range: null,
  common_periods: [],

  use_cases: [
    {
      scenario: "Leading-edge breakout confirmation",
      what_to_do: "Take long breakout entries when ASI has ALREADY broken above its prior peak (price still catching up)",
      why: "ASI's leading-edge gives 1-5 bars advance warning; entry near breakout level with conviction before price confirms.",
    },
    {
      scenario: "Confirming trend continuation in established trends",
      what_to_do: "If price makes higher high AND ASI makes higher high, trend continuation is confirmed",
      why: "Both confirming together is a high-conviction trend continuation signal; ASI's broader math reduces false signals.",
    },
    {
      scenario: "Detecting hidden divergence",
      what_to_do: "Compare ASI trend to price trend — divergence (price up, ASI flat or down) signals trend exhaustion",
      why: "ASI divergence is similar to OBV/A-D divergence but uses range/gap information that volume-based indicators miss.",
    },
  ],

  common_signals: [
    {
      signal: "Leading breakout signal",
      condition: "ASI breaks above prior peak before price does",
      action: "Early long entry candidate; aggressive trader entry.",
    },
    {
      signal: "Confirmed breakout",
      condition: "Both ASI and price break above prior peaks",
      action: "Conservative long entry with full confirmation.",
    },
    {
      signal: "Bullish divergence",
      condition: "Price lower low, ASI higher low",
      action: "Bullish reversal candidate.",
    },
    {
      signal: "Trend exhaustion",
      condition: "Price rising but ASI flat or falling",
      action: "Tighten longs; underlying momentum fading.",
    },
  ],

  pitfalls: [
    "False positive rate ~30% in choppy markets — always pair with ADX > 20 filter.",
    "Cumulative nature means absolute ASI value is meaningless; only relative levels (vs prior peaks/troughs) matter.",
    "Initial seed of 0 means warm-up period needed before ASI becomes meaningful.",
    "Gap-heavy stocks distort the Swing Index input, which feeds into ASI noise.",
    "ASI leads price but doesn't lead by a predictable amount — sometimes 1 bar, sometimes 5 — risk management essential.",
  ],

  works_well_with: ["swing-index", "adx", "ema", "supports-resistances"],
  works_poorly_with: ["obv", "accumulation-distribution"],

  example_strategies: [
    "ASI breakout leading-edge entry on NIFTY daily",
    "ASI divergence reversal scanner across F&O stocks",
    "ASI + ADX trend confirmation overlay on positional swing trades",
  ],

  indian_context:
    "ASI on NIFTY daily during sustained trends provides reliable 1-3 bar advance warning of breakouts at key levels (52-week highs, prior swing highs). The 2024 budget-rally breakout was confirmed in ASI 2 days before price cleared the prior swing high. BANKNIFTY's higher beta makes ASI moves larger; signals come slightly faster but with more false positives. For F&O cash equity, ASI works best on RIL, ICICI Bank, INFY where consistent gap dynamics give ASI clean information. Avoid on illiquid stocks where Swing Index input gets distorted.",
};
