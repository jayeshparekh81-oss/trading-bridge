import type { IndicatorContent } from "./_types";

export const CCI: IndicatorContent = {
  slug: "cci",
  name: "CCI (Commodity Channel Index)",
  category: "momentum",
  complexity: "intermediate",

  one_liner_en:
    "Measures how far price has moved from its typical-price average, normalized by mean deviation. Unbounded oscillator.",
  one_liner_hi:
    "Price apne typical-price average se kitna door gaya, mean deviation se normalize karke. Unbounded oscillator hai.",

  description_en:
    "CCI was built by Donald Lambert in 1980 for commodities, but it's now used widely across equities, currencies, and indices. The math compares the current 'typical price' (high+low+close/3) to a moving average of that typical price, then scales the difference by the average mean deviation. Output is unbounded but typically oscillates between -300 and +300, with -100 and +100 as the traditional 'normal range' boundaries.\n\nThe canonical reads:\n- CCI > +100: price is above the upper extreme — strong upside momentum, often a continuation signal (NOT a reversal).\n- CCI < -100: strong downside momentum.\n- CCI crossing back through ±100 from outside: momentum unwinding — potential reversal.\n\nCCI is louder and faster than RSI on the same chart. The +100/-100 lines are crossed many more times. That makes it useful for momentum-continuation traders (the ones who enter ON the +100 break) but worse for mean-reversion traders.\n\nDivergence and zero-line crosses both apply — same general patterns as MACD.",
  description_hi:
    "CCI Donald Lambert ne 1980 mein commodities ke liye banaya tha, but ab equities, currencies, indices sab mein use hota hai. Math compare karta hai current 'typical price' (high+low+close/3) ko us typical price ke moving average se, phir difference ko average mean deviation se scale karta hai. Output unbounded hai but typically -300 se +300 mein oscillate karta hai, -100 aur +100 traditional 'normal range' boundaries hain.\n\nCanonical reads:\n- CCI > +100: price upper extreme ke upar — strong upside momentum, often continuation signal (reversal NAHI).\n- CCI < -100: strong downside momentum.\n- CCI ±100 ke through wapas cross kare bahar se: momentum unwinding — potential reversal.\n\nCCI same chart pe RSI se louder aur faster hai. +100/-100 lines kaafi zyada cross hoti hain. Momentum-continuation traders ke liye useful (jo +100 break PE enter karte hain) but mean-reversion traders ke liye worse.\n\nDivergence aur zero-line crosses dono apply hote hain — same general patterns as MACD.",

  formula_explanation:
    "Typical price = (high + low + close) / 3. CCI = (typical_price - SMA(typical_price, period)) / (0.015 × mean_deviation). The 0.015 constant scales the indicator so ~75% of values land between -100 and +100 over long histories. Default period: 20.",

  default_period: 20,
  period_range: [5, 50],
  common_periods: [14, 20, 30],

  use_cases: [
    {
      scenario: "Momentum-continuation breakouts",
      what_to_do: "Enter long when CCI crosses ABOVE +100 (not below) with rising price",
      why: "CCI breaking +100 is a 'momentum confirmed' signal, not 'overbought sell'. Counter-intuitive vs RSI.",
    },
    {
      scenario: "Trend exhaustion on weeklies",
      what_to_do: "On weekly charts, watch for CCI to peak above +200 then drop through +100 with bearish price action",
      why: "Extreme weekly CCI readings (>+200) are rare and often coincide with multi-week tops in indices.",
    },
    {
      scenario: "Choppy zero-line whipsaws",
      what_to_do: "If CCI is crossing zero rapidly, stand aside — let trend resume",
      why: "CCI's high sensitivity makes it a chop detector by accident.",
    },
  ],

  common_signals: [
    {
      signal: "Bullish breakout",
      condition: "CCI crosses above +100",
      action: "Long entry candidate — trend-following.",
    },
    {
      signal: "Bearish breakout",
      condition: "CCI crosses below -100",
      action: "Short entry candidate — trend-following.",
    },
    {
      signal: "Reversion from extreme",
      condition: "CCI crosses back through +100 from above (or -100 from below)",
      action: "Counter-trend mean-reversion candidate. Risky — confirm with price.",
    },
    {
      signal: "Zero-line cross",
      condition: "CCI crosses 0",
      action: "Trend-bias filter (above 0 = bullish bias, below 0 = bearish bias).",
    },
  ],

  pitfalls: [
    "CCI's +100/-100 are NOT overbought/oversold lines like RSI's 70/30 — they're momentum-confirmation lines. Reading them as 'overbought' loses money in trends.",
    "Unbounded output: a CCI of +300 vs +400 isn't a 33% stronger signal — both are 'extreme'. Don't over-interpret magnitudes.",
    "The 0.015 scaling constant was chosen empirically. Different libraries occasionally use slightly different scalings — verify which you're consuming.",
    "On low-volume sessions, the typical-price and its SMA collapse onto each other and CCI loses signal — quiet pre-event days are noise.",
  ],

  works_well_with: ["ema", "atr", "volume-profile", "supertrend"],
  works_poorly_with: ["rsi", "stochastic", "williams-r"],

  example_strategies: [
    "CCI Momentum Breakout (daily NIFTY)",
    "CCI +200 Exhaustion Short (weekly index)",
  ],

  indian_context:
    "On Indian indices, CCI(20) on the daily catches sector-rotation breakouts cleanly — when NIFTY IT or NIFTY METAL prints a CCI > +100 cross, sector ETFs / heavyweight stocks usually follow within 2-3 sessions. For individual NSE F&O stocks, CCI is most useful around earnings: a fresh CCI > +100 break in the week before results is a quantifiable momentum read separate from the news-driven volatility. Don't use CCI in the last hour of expiry day — index OI rebalancing creates artificial typical-price moves.",
};
