import type { IndicatorContent } from "./_types";

export const CHOPPINESS_INDEX: IndicatorContent = {
  slug: "choppiness-index",
  name: "Choppiness Index",
  category: "volatility",
  complexity: "intermediate",

  one_liner_en:
    "0-100 scale that quantifies how 'choppy' the market is. Above 60 = sideways, below 40 = trending.",
  one_liner_hi:
    "0-100 scale jo market kitna 'choppy' hai quantify karta. 60 ke upar sideways, 40 ke neeche trending.",

  description_en:
    "The Choppiness Index (E. W. Dreiss) answers exactly one question: is the market trending or chopping? Above 61.8 (a Fibonacci number) suggests a sideways / range-bound market; below 38.2 suggests a trending market.\n\nThe math compares the sum of true ranges over `period` bars to the max-minus-min of the same window — essentially asking 'is the total path length much bigger than the net displacement?'. If yes, lots of back-and-forth = high chop. If the path length is close to net displacement, the market moved in roughly a straight line = low chop.\n\nUseful as a CONTEXT filter rather than a trade trigger. Pair with trend-following systems: only enable trend strategies when Choppiness is below 50. Pair with mean-reversion systems: only enable range strategies when Choppiness is above 60.",
  description_hi:
    "Choppiness Index (E. W. Dreiss) ek hi sawal ka jawab deta: market trending hai ya chopping? 61.8 (Fibonacci number) ke upar sideways/range-bound suggest; 38.2 ke neeche trending suggest.\n\nMath `period` bars over true ranges ke sum ko same window ke max-minus-min se compare karta — essentially poochta 'kya total path length net displacement se kaafi bigger hai?'. Yes = lots of back-and-forth = high chop. Path length close to net displacement = market roughly straight line mein moved = low chop.\n\nCONTEXT filter ki tarah useful, trade trigger nahi. Trend-following systems ke saath pair karo: trend strategies sirf tab enable jab Choppiness 50 ke neeche. Mean-reversion systems ke saath pair karo: range strategies sirf tab jab Choppiness 60 ke upar.",

  formula_explanation:
    "CI = 100 × log10(sum(TR, period) / (max(high, period) - min(low, period))) / log10(period). Output is bounded 0-100. The log scaling spreads readings around 50 for readability. Default period: 14.",

  default_period: 14,
  period_range: [5, 50],
  common_periods: [10, 14, 20],

  use_cases: [
    {
      scenario: "Strategy regime switcher",
      what_to_do: "Run trend-following when CI < 50, mean-reversion when CI > 60, stand aside in 50-60",
      why: "Different strategies have edge in different regimes. CI makes regime detection objective.",
    },
    {
      scenario: "Context filter for crossover systems",
      what_to_do: "Only take EMA crossover signals when CI < 45",
      why: "Crossover systems lose money in chop. CI < 45 confirms the market is in a state where they have edge.",
    },
  ],

  common_signals: [
    {
      signal: "Trend regime confirmation",
      condition: "CI crosses below 38.2 (Fibonacci threshold)",
      action: "Enable trend strategies.",
    },
    {
      signal: "Chop regime confirmation",
      condition: "CI crosses above 61.8",
      action: "Switch to range / mean-reversion strategies.",
    },
  ],

  pitfalls: [
    "Lagging — by the time CI confirms a trend, the trend has been going for several bars.",
    "61.8 / 38.2 thresholds are conventions; not statistical laws. Some traders use 60/40 instead.",
    "CI doesn't tell you DIRECTION of trend, only WHETHER one exists. Pair with DI+ / DI- or price for direction.",
    "On very short periods, CI is noisy. Stick to 14+ on daily and 10+ on intraday.",
  ],

  works_well_with: ["adx", "dmi", "supertrend", "ema"],
  works_poorly_with: ["rsi", "stochastic"],

  example_strategies: [
    "Choppiness-Gated Trend Following (daily NIFTY-50 stocks)",
    "Regime-Switch Strategy Selector (multi-strategy portfolio)",
  ],

  indian_context:
    "NIFTY's daily Choppiness hovers around 50-65 most of the time — Indian indices spend more time in chop than in trends. CI < 40 days on NIFTY are notable trend days; the post-budget / post-RBI sessions often produce CI dipping to 30-35. For sector indices, NIFTY METAL and NIFTY ENERGY produce cleaner trending regimes (lower average CI) than NIFTY FMCG and NIFTY CONSUMER (higher CI / more range-bound).",
};
