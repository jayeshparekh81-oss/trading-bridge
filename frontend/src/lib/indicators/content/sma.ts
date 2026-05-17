import type { IndicatorContent } from "./_types";

export const SMA: IndicatorContent = {
  slug: "sma",
  name: "SMA (Simple Moving Average)",
  category: "trend",
  complexity: "beginner",

  one_liner_en:
    "Average of the last N closing prices, weighted equally. The oldest, slowest, most-watched moving average.",
  one_liner_hi:
    "Last N closing prices ka average, equal weights ke saath. Sabse purani, slowest, sabse zyada watched moving average.",

  description_en:
    "SMA is the arithmetic mean of the last `period` closes. Every bar in the window weighs the same. Because old bars carry equal weight as new ones, SMA reacts slowly to fresh moves — it's smoother (less noisy) but laggier than EMA on the same period.\n\nThree historical anchors dominate Indian retail attention:\n- SMA-20: short-term trend, ~one month of trading days. Often paired with Bollinger Bands (the 'middle band' is SMA-20).\n- SMA-50: medium-term trend reference for swing traders.\n- SMA-200: long-term institutional reference. 'Price below 200-SMA' is widely used as bear-market shorthand.\n\nSMA's smoothness makes it useful when EMA whipsaws too much (volatile illiquid stocks, post-news days). The downside is the lag: SMA crosses fire 5-10 bars later than EMA crosses on the same chart, by which time the move has often started or completed.",
  description_hi:
    "SMA last `period` closes ka arithmetic mean hai. Window ka har bar same weight carry karta hai. Purane bars naye jaise hi weight rakhte hain, isliye SMA fresh moves pe slow react karta hai — smoother (kam noise) but EMA se laggier same period pe.\n\nTeen historical anchors Indian retail attention dominate karte hain:\n- SMA-20: short-term trend, ~one month trading days. Often Bollinger Bands ke saath paired (middle band SMA-20 hi hota hai).\n- SMA-50: medium-term trend reference swing traders ke liye.\n- SMA-200: long-term institutional reference. 'Price below 200-SMA' widely bear-market shorthand ki tarah use hota hai.\n\nSMA ki smoothness useful hai jab EMA zyada whipsaw karti hai (volatile illiquid stocks, post-news days). Downside lag hai: SMA crosses same chart pe EMA crosses se 5-10 bars baad fire hote hain, jab tak move shuru ho chuki ya complete ho chuki hoti hai.",

  formula_explanation:
    "SMA = (close[0] + close[1] + ... + close[period-1]) / period. Window slides forward one bar at a time. All bars in the window weighted equally. No seed period — first valid output is at bar index `period - 1`.",

  default_period: 20,
  period_range: [2, 500],
  common_periods: [10, 20, 50, 200],

  use_cases: [
    {
      scenario: "Long-term trend label",
      what_to_do: "Treat 'price above SMA-200 + SMA-200 sloping up' as bull regime, opposite as bear",
      why: "Single-condition trend label that institutional traders watch — useful as a sanity-check filter on any strategy.",
    },
    {
      scenario: "Bollinger Bands middle line",
      what_to_do: "Use SMA-20 as the centre of a 20-period Bollinger Band setup",
      why: "Bollinger's classic recipe is SMA-20 ± 2 standard deviations. SMA (not EMA) is the original spec.",
    },
    {
      scenario: "Smooth filter for noisy individual stocks",
      what_to_do: "Substitute SMA for EMA on stocks where EMA produces too many crossover whipsaws",
      why: "SMA's higher lag becomes an advantage when you want to filter out short-term noise.",
    },
  ],

  common_signals: [
    {
      signal: "SMA-50 / SMA-200 golden cross",
      condition: "SMA-50 crosses above SMA-200",
      action: "Long-term bullish regime change — slow but reliable.",
    },
    {
      signal: "Death cross",
      condition: "SMA-50 crosses below SMA-200",
      action: "Bearish regime — favoured exit signal for positional longs.",
    },
    {
      signal: "Price reclaim of SMA-200",
      condition: "Price closes above SMA-200 after being below for many sessions",
      action: "Long-term trend reversal — major bullish signal.",
    },
  ],

  pitfalls: [
    "Slow. By the time SMA-200 crosses, the move has been going for weeks. Crossover-only strategies on SMA-200 are positional, not tactical.",
    "Equal weighting means an old data point 199 days ago carries the same weight as yesterday. On rapidly-changing regimes this is a feature; in slow markets it's an over-smoothing bug.",
    "Different SMA periods on the same chart will sometimes disagree. That's the indicator, not a bug.",
    "SMA without a slope check is just a line — flat SMA = no trend = the indicator is silent, not bearish.",
  ],

  works_well_with: ["bollinger-bands", "ema", "atr", "adx"],
  works_poorly_with: ["wma"],

  example_strategies: [
    "SMA-50/200 Golden Cross (positional NIFTY-50 stocks)",
    "SMA-200 Reclaim (long-term swing)",
    "Bollinger Bands (uses SMA-20)",
  ],

  indian_context:
    "Indian financial press tracks NIFTY's 200-day SMA religiously — daily news headlines like 'Nifty 50 reclaims 200-DMA' refer to this exact indicator. SMA-200 for individual NSE F&O stocks is the swing-trader consensus reference for trend regime. For sector indices, SMA-50 on the daily catches rotation faster than SMA-200 and is the common screening cutoff for sector momentum scans. On BANKNIFTY's higher-volatility daily, SMA produces fewer false signals than EMA at the cost of slower entries — a fair trade for positional traders.",
};
