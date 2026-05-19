import type { IndicatorContent } from "./_types";

export const PRICE_OSCILLATOR: IndicatorContent = {
  slug: "price-oscillator",
  name: "Price Oscillator (PPO)",
  category: "momentum",
  complexity: "beginner",

  one_liner_en:
    "Percentage version of MACD — shows momentum as a percentage of price, comparable across stocks at different price levels.",
  one_liner_hi:
    "MACD ka percentage version — momentum ko price ke percentage ke roop mein dikhata, different price levels ke stocks pe comparable.",

  description_en:
    "Price Oscillator (PPO, Percentage Price Oscillator) is mathematically nearly identical to MACD with one critical change: the output is expressed as a PERCENTAGE of the slower moving average, not as an absolute difference. This single change makes PPO directly comparable across instruments at different price levels.\n\nWhy this matters: MACD of NIFTY trading at 22,000 has values in the hundreds; MACD of a small-cap at ₹150 has values in single digits. You can't compare them. PPO normalizes both into the same percentage scale, so 'PPO at 2%' means the same momentum strength whether you're looking at NIFTY, Reliance, or a small-cap.\n\nFor a single instrument, PPO and MACD give identical signals — same crosses, same divergences, same trend reads. The advantage of PPO appears when you're scanning across many stocks or comparing momentum strength between instruments.\n\nFor Indian retail traders running cross-stock screens (e.g., 'find top 10 NIFTY 100 stocks with strongest momentum'), PPO is the right choice. For a focused trader on one or two instruments, the choice between PPO and MACD is largely cosmetic.",
  description_hi:
    "Price Oscillator (PPO, Percentage Price Oscillator) mathematically MACD ke nearly identical hai with one critical change: output slower moving average ke PERCENTAGE ke roop mein expressed hota, absolute difference nahi. Ye single change PPO ko different price levels ke instruments pe directly comparable banata.\n\nKyun matter karta: NIFTY 22,000 pe trade kar raha to MACD values hundreds mein hote; ₹150 ka small-cap MACD single digits mein. Compare nahi kar sakte. PPO dono ko same percentage scale mein normalize karta, to 'PPO at 2%' ka same matlab whether NIFTY, Reliance, ya small-cap dekho.\n\nSingle instrument ke liye PPO aur MACD identical signals dete — same crosses, same divergences, same trend reads. PPO ka advantage tab dikhta jab aap many stocks screen kar rahe ho ya instruments ke beech momentum strength compare kar rahe ho.\n\nIndian retail traders jo cross-stock screens chala te hain (e.g., 'NIFTY 100 ke top 10 strongest momentum stocks dhundo'), unke liye PPO right choice hai. Ek-do instruments pe focused trader ke liye PPO vs MACD ka choice largely cosmetic hai.",

  formula_explanation:
    "PPO = ((12-EMA - 26-EMA) / 26-EMA) × 100. Signal line = 9-EMA of PPO. Identical to MACD's structure, except divided by the slow EMA to express as percentage. The 12/26/9 defaults match MACD's defaults exactly.",

  default_period: 26,
  period_range: [10, 50],
  common_periods: [12, 26],

  use_cases: [
    {
      scenario: "Cross-stock momentum scanning",
      what_to_do: "Rank NIFTY 100 stocks by PPO value; trade the top 10 long-side, bottom 10 short-side",
      why: "PPO's normalization makes ranking valid; doing the same with raw MACD would be meaningless across different price levels.",
    },
    {
      scenario: "Comparing momentum strength between two stocks for relative trades",
      what_to_do: "If PPO of RIL > PPO of HDFC, prefer RIL as the long leg of a pair trade",
      why: "Direct momentum comparison guides the long/short selection in pair-trading and relative-strength setups.",
    },
    {
      scenario: "Single-stock trend trading (interchangeable with MACD)",
      what_to_do: "PPO signal line cross = entry/exit signal, identical to MACD",
      why: "Use whichever you prefer visually; signals are identical.",
    },
  ],

  common_signals: [
    {
      signal: "Bullish cross",
      condition: "PPO line crosses above its signal line",
      action: "Long entry candidate — momentum has shifted bullish.",
    },
    {
      signal: "Bearish cross",
      condition: "PPO line crosses below its signal line",
      action: "Long exit / short entry candidate.",
    },
    {
      signal: "Histogram peak",
      condition: "PPO histogram bars peak and start declining",
      action: "Momentum acceleration is fading; consider profit-taking.",
    },
    {
      signal: "Centerline cross",
      condition: "PPO crosses above zero (bull bias) or below zero (bear bias)",
      action: "Trend-bias filter for longer-timeframe positions.",
    },
  ],

  pitfalls: [
    "Identical signal frequency to MACD — same whipsaw issues in choppy markets.",
    "The 'percentage' framing fools beginners into thinking PPO is 'more accurate' — it isn't, just more comparable.",
    "On very low-priced stocks (penny stocks), the percentage calculation can produce wild swings that look like signals.",
    "Cross-stock comparisons assume similar volatility regimes — comparing a low-vol large-cap to a high-vol small-cap via PPO can mislead.",
    "Default 12/26/9 isn't sacred — adjust for timeframe and instrument.",
  ],

  works_well_with: ["rsi", "adx", "ema", "bollinger-bands"],
  works_poorly_with: ["macd", "roc"],

  example_strategies: [
    "PPO momentum-rank scanner across NIFTY 100",
    "PPO + RSI confluence on F&O stocks",
    "Pair-trading long/short selection via PPO comparison",
  ],

  indian_context:
    "PPO is particularly useful for Indian traders running multi-stock screens because NSE F&O includes stocks from ₹50 (e.g., some PSU banks) to ₹50,000+ (Page Industries, MRF). MACD comparisons across this range are meaningless; PPO works. For NIFTY 100 momentum scans, daily PPO has historically picked sector leaders 2-3 weeks before they show up in financial news. BANKNIFTY constituents tend to have higher PPO volatility due to sector concentration — adjust thresholds upward (e.g., look for >3% PPO rather than 1%).",
};
