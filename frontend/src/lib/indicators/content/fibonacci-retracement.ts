import type { IndicatorContent } from "./_types";

export const FIBONACCI_RETRACEMENT: IndicatorContent = {
  slug: "fibonacci-retracement",
  name: "Fibonacci Retracement",
  category: "pattern",
  complexity: "intermediate",

  one_liner_en:
    "Horizontal levels at 23.6%, 38.2%, 50%, 61.8%, and 78.6% of a chosen swing. Where pullbacks often pause.",
  one_liner_hi:
    "Chosen swing ka 23.6%, 38.2%, 50%, 61.8%, aur 78.6% pe horizontal levels. Jahan pullbacks often pause hote hain.",

  description_en:
    "Fibonacci Retracement is a drawing tool, not a computed indicator — the trader picks two points (a swing high and a swing low) and the tool plots horizontal lines at the Fibonacci ratios between them: 23.6%, 38.2%, 50% (not technically Fibonacci but conventional), 61.8%, 78.6%, plus the 0% and 100% extremes.\n\nThe theory: market pullbacks often pause at these proportional levels. The 38.2% and 61.8% are the most-watched — the 'golden ratio' (61.8%) shows up across nature and traders treat it as a fundamental pullback target.\n\nReality check: there's no rigorous mathematical reason markets should respect Fibonacci levels. The effect is partly self-fulfilling — millions of traders watch the same levels, so price reacts at them. It works often enough to be useful, fails often enough that you can't rely on a single level alone.\n\nUse Fibonacci as a target zone, not a precise trigger. Combine with candle reversal patterns, RSI conditions, or volume to confirm at the level. The 50% retracement (the 'half-back' in classical TA) is often the cleanest re-entry zone in trending markets.",
  description_hi:
    "Fibonacci Retracement drawing tool hai, computed indicator nahi — trader do points (swing high aur swing low) pick karta hai aur tool unke beech Fibonacci ratios pe horizontal lines plot karta: 23.6%, 38.2%, 50% (technically Fibonacci nahi but conventional), 61.8%, 78.6%, plus 0% aur 100% extremes.\n\nTheory: market pullbacks often in proportional levels pe pause hote hain. 38.2% aur 61.8% sabse zyada watched — 'golden ratio' (61.8%) nature mein dikhta hai aur traders fundamental pullback target ki tarah treat karte hain.\n\nReality check: koi rigorous mathematical reason nahi hai ki markets Fibonacci levels respect karein. Effect partly self-fulfilling hai — millions of traders same levels watch karte hain to price react karta hai. Often enough kaam karta hai useful hone ke liye, often enough fail karta hai ki ek single level pe rely nahi kar sakte.\n\nFibonacci ko target zone ki tarah use karo, precise trigger nahi. Candle reversal patterns, RSI conditions, ya volume ke saath combine karke level pe confirm karo. 50% retracement (classical TA mein 'half-back') often trending markets ka cleanest re-entry zone hai.",

  formula_explanation:
    "Pick a swing high (H) and swing low (L). Range = H - L. Plot horizontal lines at: H - 0.236 × Range (23.6% retracement), H - 0.382 × Range, H - 0.5 × Range, H - 0.618 × Range, H - 0.786 × Range. Plus the 0% (the recent extreme) and 100% (the prior extreme) reference lines. Extensions beyond 100% (typically 161.8%, 261.8%) are used for upside / downside targets after the retracement is over.",

  default_period: null,
  period_range: null,
  common_periods: [],

  use_cases: [
    {
      scenario: "Pullback entry in a confirmed trend",
      what_to_do: "In an uptrend, draw Fib from the most recent significant swing low to swing high. Look for long entries near the 38.2% or 50% retracement",
      why: "Trends often retrace 38-61% before continuing. Fib levels concentrate participant attention at these proportional levels.",
    },
    {
      scenario: "Confluence with structural levels",
      what_to_do: "Fib level coinciding with a moving average (e.g. 200-EMA) or a prior pivot is a high-confluence support",
      why: "Multiple independent levels at the same price = stronger participant memory = higher reaction probability.",
    },
    {
      scenario: "Profit-target extensions",
      what_to_do: "Use the 161.8% extension beyond the retracement endpoint as a profit-take target",
      why: "Classical impulse-extension target. Works on cleanly trending stocks; less useful in choppy / range markets.",
    },
  ],

  common_signals: [
    {
      signal: "Pullback to 50%",
      condition: "Price retraces to the 50% Fib level and prints a bullish reversal candle",
      action: "Long entry candidate — trend-continuation play.",
    },
    {
      signal: "61.8% rejection",
      condition: "Price tags 61.8% retracement and reverses sharply",
      action: "Strong trend-continuation signal; entry with stop just past 61.8%.",
    },
    {
      signal: "78.6% break",
      condition: "Price closes beyond 78.6% retracement",
      action: "Trend likely broken — reverse bias or stand aside.",
    },
  ],

  pitfalls: [
    "Drawing is subjective — picking different swing highs/lows produces different Fib levels. Two traders can disagree on 'the' Fib retracement of the same chart.",
    "50% retracement is widely used but technically NOT a Fibonacci number — it survives because it's a meaningful halfway point.",
    "Fib levels alone are noisy. They work as zones of interest where OTHER signals (candles, RSI, volume) get confirmation; they don't trigger trades by themselves.",
    "Fib extensions (>100%) project targets without statistical grounding — useful for setting initial profit targets but don't anchor trade decisions on them alone.",
    "Different drawing tools occasionally include / exclude the 78.6% or include 88.7%. Stay consistent.",
  ],

  works_well_with: ["supertrend", "ema", "rsi", "volume-profile"],
  works_poorly_with: ["donchian-channel", "bollinger-bands"],

  example_strategies: [
    "Fib Pullback in Uptrend (daily F&O stocks)",
    "Fib 61.8% Reversal (1h indices)",
    "Fib Extension Target (positional swing)",
  ],

  indian_context:
    "Fibonacci retracement is well-established in Indian retail technical analysis curricula — every NISM technical-analysis course covers it. On daily NIFTY swings, the 50% and 61.8% retracements have historically attracted clean reversal setups during normal market regimes. During trending phases (post-budget, sector rotation), 38.2% retracements often hold and produce continuation moves. For F&O stocks during earnings season, Fib retracement of the pre-results impulse move sometimes provides clean re-entry zones in the week after results. Less useful on choppy index intraday — pivots and CPR dominate that surface.",
};
