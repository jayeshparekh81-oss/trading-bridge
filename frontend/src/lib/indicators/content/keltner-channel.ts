import type { IndicatorContent } from "./_types";

export const KELTNER_CHANNEL: IndicatorContent = {
  slug: "keltner-channel",
  name: "Keltner Channel",
  category: "volatility",
  complexity: "intermediate",

  one_liner_en:
    "An EMA with two ATR-distance bands. Smoother than Bollinger and better for trend-following.",
  one_liner_hi:
    "Ek EMA jiske paas ATR-distance ki do bands hain. Bollinger se smoother aur trend-following ke liye behtar.",

  description_en:
    "Keltner Channel plots three lines: a middle EMA (default 20), an upper band = EMA + (ATR × multiplier), and a lower band = EMA - (ATR × multiplier). Multiplier defaults to 2.\n\nIt's Bollinger Bands' close cousin — same concept, different volatility input. Bollinger uses standard deviation; Keltner uses ATR. The practical difference: ATR is less spike-prone than stddev (TR doesn't get inflated by a single big bar the way stddev does), so Keltner bands are smoother and contract less dramatically during low-volume periods.\n\nThe trade-offs:\n• Bollinger reacts faster to volatility regime changes (good for squeeze breakouts).\n• Keltner is steadier and works better as a trend-following channel — price 'walking' the Keltner upper band is a cleaner trend signal than walking the Bollinger upper.\n\nClassic combo: 'Bollinger inside Keltner' (the TTM Squeeze pattern). When Bollinger Bands contract inside Keltner Channels, volatility is anomalously low — primed for breakout.",
  description_hi:
    "Keltner Channel teen lines plot karta: middle EMA (default 20), upper band = EMA + (ATR × multiplier), lower band = EMA - (ATR × multiplier). Multiplier default 2.\n\nBollinger Bands ka close cousin hai — same concept, different volatility input. Bollinger standard deviation use karta; Keltner ATR. Practical difference: ATR stddev se kam spike-prone hai (TR ek bade bar se inflate nahi hota stddev ki tarah), isliye Keltner bands smoother hain aur low-volume periods mein kam dramatically contract karti hain.\n\nTrade-offs:\n• Bollinger volatility regime changes pe faster react karta (squeeze breakouts ke liye accha).\n• Keltner steadier hai aur trend-following channel ki tarah better kaam karta — Keltner upper band ke saath price 'walk' karna Bollinger upper walk se cleaner trend signal hai.\n\nClassic combo: 'Bollinger inside Keltner' (TTM Squeeze pattern). Jab Bollinger Bands Keltner Channels ke andar contract karein, volatility anomalously low — breakout ke liye primed.",

  formula_explanation:
    "Middle = EMA(close, period). Upper = Middle + (mult × ATR(period)). Lower = Middle - (mult × ATR(period)). Defaults: period 20, multiplier 2. Variations use typical price ((H+L+C)/3) for the EMA basis.",

  default_period: 20,
  period_range: [5, 50],
  common_periods: [10, 20, 50],

  use_cases: [
    {
      scenario: "Trend-following channel ride",
      what_to_do: "In an uptrend, hold longs as long as price stays above the middle line and pulls back to it (rather than the lower band)",
      why: "Keltner middle line is a cleaner pullback-buy zone than Bollinger middle because ATR-based bands are less spike-prone.",
    },
    {
      scenario: "TTM Squeeze setup",
      what_to_do: "Watch for Bollinger Bands to compress entirely INSIDE Keltner Channels — that's the squeeze. Enter on the breakout direction.",
      why: "Volatility is unusually low when Bollinger fits inside Keltner; statistically, a large move follows.",
    },
    {
      scenario: "Breakout confirmation",
      what_to_do: "Treat a Keltner upper-band breakout (close above) as a strong-trend confirmation, not an overbought sell",
      why: "Keltner band breaks are rarer than Bollinger band touches — more meaningful when they happen.",
    },
  ],

  common_signals: [
    {
      signal: "Upper band breakout",
      condition: "Close above the upper Keltner band",
      action: "Strong uptrend confirmation — long-continuation entry.",
    },
    {
      signal: "Lower band breakdown",
      condition: "Close below the lower Keltner band",
      action: "Strong downtrend confirmation — short or exit longs.",
    },
    {
      signal: "TTM Squeeze fire",
      condition: "Bollinger Bands move from inside Keltner to outside",
      action: "Squeeze release — enter in the breakout direction.",
    },
    {
      signal: "Middle-line pullback",
      condition: "Price retraces from an extended move back to the EMA middle line in a confirmed trend",
      action: "Continuation entry with stop just past the middle line.",
    },
  ],

  pitfalls: [
    "Less famous than Bollinger Bands — Indian retail communities rarely discuss Keltner alone. You're often on your own for setup-sharing.",
    "ATR input means same warmup caveats as ATR — first 14 bars unreliable.",
    "Trending markets can keep price beyond the upper / lower band for many bars; don't fade extended Keltner moves.",
    "Different libraries use SMA vs EMA vs typical-price for the middle line — the visual shifts slightly across tools.",
  ],

  works_well_with: ["bollinger-bands", "atr", "supertrend", "ema"],
  works_poorly_with: ["donchian-channel", "standard-deviation"],

  example_strategies: [
    "TTM Squeeze Breakout (daily F&O stocks)",
    "Keltner Trend Continuation (1h NIFTY)",
  ],

  indian_context:
    "Keltner Channels see less explicit Indian retail discussion than Bollinger Bands, but the TTM Squeeze setup (Bollinger inside Keltner) is well-known among quant retail and Telegram-channel traders. On NIFTY daily, TTM Squeeze setups average 3-6 per year and have historically delivered above-average follow-through magnitude. For BANKNIFTY's higher volatility, Keltner with multiplier 2.5 sometimes beats the default 2 — the wider band reduces false breakout signals from intraday volatility.",
};
