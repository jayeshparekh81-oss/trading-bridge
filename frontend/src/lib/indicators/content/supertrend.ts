import type { IndicatorContent } from "./_types";

export const SUPERTREND: IndicatorContent = {
  slug: "supertrend",
  name: "Supertrend",
  category: "trend",
  complexity: "beginner",

  one_liner_en:
    "An ATR-based trailing stop that flips on every trend reversal. Green when bullish, red when bearish.",
  one_liner_hi:
    "ATR-based trailing stop jo har trend reversal pe flip karta hai. Bullish mein green, bearish mein red.",

  description_en:
    "Supertrend is one of the most popular indicators in Indian retail F&O — it's a single visual line that tracks below price during uptrends (acting as dynamic support) and above price during downtrends (acting as dynamic resistance). When price crosses through the line, the indicator flips: trend regime change.\n\nMechanically: take the median of the recent high-low (midpoint), then offset by ATR × a multiplier (default 3). That gives upper and lower bands. The indicator outputs whichever band is currently 'active' based on whether the trend is up or down — and the band is sticky in one direction (it only moves to follow price, not against it).\n\nThe two tunable parameters are ATR period (default 10) and ATR multiplier (default 3). Smaller multiplier (1.5-2) = tighter trail, more flips, smaller losses per flip but more whipsaws. Larger (4-5) = wider trail, fewer flips, larger drawdown per flip but better trend-following on sustained moves.\n\nSupertrend's strength is its binary clarity — 'are we in an uptrend or downtrend?' has a yes/no answer. Its weakness is sideways markets: in chop, Supertrend flips at every fake-out and loses money on consecutive small losses.",
  description_hi:
    "Supertrend Indian retail F&O mein sabse popular indicators mein se ek hai — ek single visual line jo uptrend mein price ke neeche track karti (dynamic support) aur downtrend mein price ke upar (dynamic resistance). Price line ke through cross kare to indicator flip ho jaata — trend regime change.\n\nMechanically: recent high-low ka median (midpoint) lo, phir ATR × multiplier (default 3) se offset karo. Upper aur lower bands milte hain. Indicator wahi band output karta jo currently 'active' hai based on trend direction — aur band ek direction mein sticky hota hai (sirf price follow karne ke liye move karta hai, against nahi).\n\nDo tunable parameters: ATR period (default 10) aur ATR multiplier (default 3). Chhota multiplier (1.5-2) = tighter trail, zyada flips, har flip pe chhota loss but zyada whipsaws. Bada (4-5) = wider trail, kam flips, har flip pe bigger drawdown but sustained moves pe better trend-following.\n\nSupertrend ki strength binary clarity hai — 'uptrend ya downtrend?' ka yes/no jawab. Weakness sideways markets hai: chop mein Supertrend har fake-out pe flip karta hai aur consecutive small losses se paise lose karta hai.",

  formula_explanation:
    "Mid = (high + low) / 2. Upper band = Mid + ATR(period) × multiplier. Lower band = Mid - ATR(period) × multiplier. Supertrend follows the lower band when the trend is up, the upper band when trend is down, and flips when price closes across the active band. Defaults: ATR period 10, multiplier 3.",

  default_period: 10,
  period_range: [3, 50],
  common_periods: [7, 10, 14],

  use_cases: [
    {
      scenario: "Trailing stop for trend-following entries",
      what_to_do: "Use the active Supertrend line as the stop-loss for any long entry, updating each bar",
      why: "Mechanically backed by volatility (ATR), the trail loosens during volatile bars and tightens during calm — better than a fixed-percent trail.",
    },
    {
      scenario: "Trend-direction filter",
      what_to_do: "Only take long signals when Supertrend is green (bullish)",
      why: "Reduces false counter-trend signals dramatically on most strategies — the single biggest filter improvement for beginners.",
    },
    {
      scenario: "Index futures swing trading",
      what_to_do: "On daily NIFTY / BANKNIFTY, hold positions only while Supertrend stays in one regime",
      why: "Daily Supertrend flips are rare and meaningful — 2-5 per quarter on indices. Trading only between flips removes a lot of intraday noise.",
    },
  ],

  common_signals: [
    {
      signal: "Bullish flip",
      condition: "Price closes above the upper band; Supertrend switches from red to green",
      action: "Trend regime change — long entry candidate.",
    },
    {
      signal: "Bearish flip",
      condition: "Price closes below the lower band; Supertrend switches from green to red",
      action: "Long exit / short candidate.",
    },
    {
      signal: "Pullback to active band",
      condition: "In an uptrend, price retraces toward the (green) Supertrend line without breaking it",
      action: "Continuation entry — Supertrend acting as dynamic support.",
    },
  ],

  pitfalls: [
    "Sideways markets shred Supertrend. The indicator was never designed for chop — pair with an ADX > 20 filter to suppress signals when no trend exists.",
    "Multiplier sensitivity is significant. ATR × 3 vs ATR × 2 on the same chart will flip at very different times. Backtest before changing the default.",
    "Supertrend is lagging — by the time it flips, the move has started. Use it as confirmation, not prediction.",
    "Gap-open days can produce an instant flip with no entry opportunity at the indicator's price — slippage risk if you're trading the flip.",
    "Two different Supertrend libraries can disagree on the exact flip-bar because of subtle differences in how they handle equal-to-band closes. Be consistent.",
  ],

  works_well_with: ["adx", "atr", "rsi", "vwap"],
  works_poorly_with: ["bollinger-bands", "donchian-channel"],

  example_strategies: [
    "Supertrend Flip Reversal (15m BANKNIFTY)",
    "Supertrend + ADX Filter (daily NIFTY-50)",
    "Supertrend Trailing Stop (positional F&O stocks)",
  ],

  indian_context:
    "Supertrend is arguably the single most-discussed indicator in Indian retail F&O Telegram and YouTube circles. Default 10/3 on 15-minute BANKNIFTY is the textbook scalper setting; 7/3 on 5-minute is the aggressive variant. On daily NIFTY-500 stocks, Supertrend(14, 3) is a common positional regime filter. Watch out for Supertrend flips on the morning of Indian budget / RBI policy days — pre-event positioning often generates a false flip in the first 30 minutes that reverses by noon.",
};
