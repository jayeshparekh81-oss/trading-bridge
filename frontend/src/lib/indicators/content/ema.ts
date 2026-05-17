import type { IndicatorContent } from "./_types";

export const EMA: IndicatorContent = {
  slug: "ema",
  name: "EMA (Exponential Moving Average)",
  category: "trend",
  complexity: "beginner",

  one_liner_en:
    "Moving average that weights recent prices more heavily — reacts faster than SMA to new info.",
  one_liner_hi:
    "Moving average jo recent prices ko zyada weight deti hai — SMA se fast react karti hai naye info pe.",

  description_en:
    "EMA gives exponentially decaying weights to past prices: today's bar carries the most weight, yesterday's a bit less, and so on out to the horizon. The decay rate is set by the period — a 20-EMA reacts faster than a 50-EMA, which reacts faster than a 200-EMA.\n\nThe practical effect: EMA tracks price more closely than SMA of the same period. On a sharp move, EMA pivots within a few bars; SMA lags noticeably because it weights everything in the window equally.\n\nThree common uses: (1) trend direction — if price is above EMA and EMA is sloping up, the trend is up; (2) dynamic support/resistance — pullbacks to a rising EMA often hold; (3) crossovers — fast EMA crossing slow EMA marks regime changes (golden cross 50 over 200, death cross opposite).\n\nThe 'right' period depends on what you're filtering. 9 and 21 are intraday-fast. 50 and 200 are positional-slow. 20 is the middle-of-the-road default that shows up in TradingView's defaults.",
  description_hi:
    "EMA past prices ko exponentially decaying weights deti hai: aaj ka bar sabse zyada weight carry karta, kal ka thoda kam, etc. horizon tak. Decay rate period set karta hai — 20-EMA 50-EMA se fast react karti, 50-EMA 200-EMA se fast react karti.\n\nPractical effect: EMA same period ki SMA se zyada closely price track karti hai. Sharp move pe EMA kuch bars mein pivot kar leti; SMA noticeably lag karti hai kyunki window mein sab kuch equally weight deti.\n\nTeen common uses: (1) trend direction — price EMA ke upar AND EMA up slope = trend up; (2) dynamic support/resistance — rising EMA tak pullbacks often hold karte hain; (3) crossovers — fast EMA slow EMA ke upar cross kare = regime change (golden cross 50 over 200, death cross ulta).\n\n'Right' period filter ki need pe depend karta hai. 9 aur 21 intraday-fast. 50 aur 200 positional-slow. 20 middle-of-the-road default jo TradingView mein bhi default hai.",

  formula_explanation:
    "EMA(today) = α × close(today) + (1 - α) × EMA(yesterday), where α = 2 / (period + 1). The first value is typically seeded with the SMA of the first `period` closes. Higher α (smaller period) = more responsive to recent bars.",

  default_period: 20,
  period_range: [2, 500],
  common_periods: [9, 20, 50, 200],

  use_cases: [
    {
      scenario: "Trend direction filter",
      what_to_do: "Only take long signals when price > 50-EMA and 50-EMA is sloping up",
      why: "Removes most counter-trend longs in obvious downtrends — easiest single-filter improvement to a strategy's edge.",
    },
    {
      scenario: "Pullback entry timing",
      what_to_do: "In an uptrend, wait for price to touch the 20-EMA from above, then enter on bullish candle close",
      why: "Pullback-to-MA is a classical mean-reversion-within-trend setup with empirically tight stops (just below the EMA).",
    },
    {
      scenario: "Crossover trend-regime change",
      what_to_do: "Long when 50-EMA crosses above 200-EMA; flat or short when reversed",
      why: "Slow but reliable. Filters out everything except multi-week trends — useful for positional, useless for intraday.",
    },
  ],

  common_signals: [
    {
      signal: "Golden cross",
      condition: "Faster EMA crosses above slower EMA (commonly 50 / 200)",
      action: "Bullish regime change — long entry candidate.",
    },
    {
      signal: "Death cross",
      condition: "Faster EMA crosses below slower EMA",
      action: "Bearish regime change — exit longs / short candidate.",
    },
    {
      signal: "EMA support hold",
      condition: "Price pulls back to rising EMA, then closes back above it",
      action: "Continuation long entry with stop just below the EMA.",
    },
    {
      signal: "EMA slope flatten",
      condition: "EMA goes from sloping up to flat",
      action: "Reduce position size / tighten stops — trend losing momentum.",
    },
  ],

  pitfalls: [
    "Choppy markets generate constant crossover whipsaws. Crossover strategies need a volatility / trend-strength filter (ADX > 20) to be tradeable.",
    "Period choice changes EVERYTHING. A 9-EMA and a 200-EMA on the same chart tell very different stories — always state the period.",
    "EMA on log-scale charts behaves slightly differently than on linear-scale — same indicator, different visual.",
    "EMAs lag price by design. They confirm trends; they don't predict reversals.",
    "First few bars after an EMA series starts (seed period) are unreliable — wait at least `period` bars before trusting the value.",
  ],

  works_well_with: ["macd", "rsi", "adx", "supertrend", "atr"],
  works_poorly_with: ["sma", "wma"],

  example_strategies: [
    "EMA-9/21 Crossover (intraday F&O)",
    "EMA-200 Trend Filter (positional)",
    "EMA Pullback Buyer (15m NIFTY)",
  ],

  indian_context:
    "Indian retail's most-watched levels are EMA-200 on the daily for NIFTY and BANKNIFTY — financial media routinely reference 'NIFTY above its 200-day EMA' as a bull-market headline. EMA-9 / EMA-21 on 5-min is the standard scalper crossover setup for BANKNIFTY F&O. For equity F&O stocks, EMA-50 on the hourly is a common positional-swing reference among Telegram-group calls. Crossover quality degrades around expiry week as forced OI unwinding distorts intraday EMA slopes.",
};
