import type { IndicatorContent } from "./_types";

export const WMA: IndicatorContent = {
  slug: "wma",
  name: "WMA (Weighted Moving Average)",
  category: "trend",
  complexity: "intermediate",

  one_liner_en:
    "Linear-weighted moving average — newer bars matter more, in straight-line proportion to age.",
  one_liner_hi:
    "Linearly-weighted moving average — naye bars zyada matter karte hain, age ke seedha proportion mein.",

  description_en:
    "WMA sits between SMA and EMA in responsiveness. SMA weights every bar equally; EMA decays weights exponentially; WMA decays them linearly — yesterday is weighted `period`, day-before-yesterday is `period-1`, and so on. The newest bar carries the most weight, the oldest the least, but the decay is a straight line not a curve.\n\nIn practice WMA reacts about as fast as EMA in trending conditions but produces fewer false crossovers in choppy conditions. The math is harder to compute incrementally than EMA (you have to do the full sum every bar), so older charting tools defaulted to EMA — that's the main reason EMA is more commonly seen even when WMA is technically the better choice for some setups.\n\nMost retail platforms expose WMA via the same crossover patterns as SMA/EMA: WMA-9 over WMA-21 for fast, WMA-50 over WMA-200 for slow. The Hull Moving Average (HMA) is built FROM WMAs.",
  description_hi:
    "WMA responsiveness mein SMA aur EMA ke beech baithta hai. SMA har bar ko equal weight deti; EMA exponentially decay karti; WMA linearly decay karti — kal `period` weight, parson `period-1`, etc. Newest bar most weight, oldest least, but decay straight line hai curve nahi.\n\nPractice mein WMA trending conditions mein EMA jaisi fast react karti hai, but choppy conditions mein fewer false crossovers deti hai. Incrementally compute karna EMA se mushkil hai (har bar full sum karna padta hai), isliye purane charting tools EMA pe default karte the — yahi main reason hai EMA zyada common dikhti hai jab WMA technically better choice ho.\n\nMost retail platforms WMA ko same crossover patterns ke through expose karte hain SMA/EMA jaise: WMA-9 over WMA-21 fast, WMA-50 over WMA-200 slow. Hull Moving Average (HMA) WMAs SE bana hai.",

  formula_explanation:
    "WMA(today) = (n × close[0] + (n-1) × close[1] + ... + 1 × close[n-1]) / (n × (n + 1) / 2), where n is the period and close[0] is the most recent bar. The denominator is the sum of weights 1 + 2 + ... + n.",

  default_period: 20,
  period_range: [2, 200],
  common_periods: [9, 20, 50, 200],

  use_cases: [
    {
      scenario: "Smoother crossover than EMA on choppy stocks",
      what_to_do: "Use WMA-9/WMA-21 instead of EMA-9/EMA-21 on stocks with frequent EMA-cross whipsaws",
      why: "Linear-weighting filters single-bar spikes that EMA reacts to, reducing false crosses by ~10-20% on noisy small-cap data.",
    },
    {
      scenario: "Building Hull Moving Average",
      what_to_do: "HMA(n) = WMA(2 × WMA(n/2) - WMA(n), sqrt(n))",
      why: "HMA is dramatically smoother than SMA/EMA/WMA alone and is the modern preferred smooth MA — but its construction is pure WMA math.",
    },
  ],

  common_signals: [
    {
      signal: "Bullish WMA cross",
      condition: "Fast WMA crosses above slow WMA (e.g. WMA-9 above WMA-21)",
      action: "Long entry candidate — works in trending markets.",
    },
    {
      signal: "Bearish WMA cross",
      condition: "Fast WMA crosses below slow WMA",
      action: "Exit longs / short candidate.",
    },
  ],

  pitfalls: [
    "Less common than EMA/SMA — retail community discusses WMA-crosses less, so social-trading signal flow is thin.",
    "Heavier to compute on long histories (re-summing each bar). For long backtests this matters; for live trading it's negligible.",
    "Linear weighting can over-react to the most recent bar on gap-open days — first 5 minutes of trading is noisy on WMA.",
  ],

  works_well_with: ["adx", "atr", "supertrend"],
  works_poorly_with: ["sma", "ema"],

  example_strategies: [
    "WMA Crossover (1h NSE-100 stocks)",
    "Hull Moving Average (built from WMA components)",
  ],

  indian_context:
    "Indian retail uses WMA less than EMA in daily practice — the dominant scalper crossovers in BANKNIFTY / NIFTY communities are EMA-based. WMA's edge shows up on individual mid-cap and small-cap NSE F&O stocks where intraday gaps create EMA whipsaws — switching to WMA-9 / WMA-21 typically reduces churn on these names. The Hull Moving Average (HMA), a WMA-derived smoother, is gaining traction among Indian quant retail in 2025-26.",
};
