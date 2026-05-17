import type { IndicatorContent } from "./_types";

export const BOLLINGER_BANDS: IndicatorContent = {
  slug: "bollinger-bands",
  name: "Bollinger Bands",
  category: "volatility",
  complexity: "beginner",

  one_liner_en:
    "A 20-period SMA with two bands one standard deviation above and below. Bands widen in volatility, contract in calm.",
  one_liner_hi:
    "20-period SMA jiske upar aur neeche standard deviation ki do bands hain. Volatility mein bands chodi, calm mein narrow.",

  description_en:
    "Bollinger Bands plot three lines: the middle is an SMA (default 20-period), the upper band is the SMA + (standard deviation × multiplier), the lower band is the SMA - (standard deviation × multiplier). Default multiplier is 2.\n\nStatistically, ~95% of bar closes fall inside the bands when prices are normally distributed. Closes near the upper band signal high relative prices; closes near the lower band signal low relative prices. The bands themselves expand when realized volatility rises and contract when it falls — visible volatility regime.\n\nThree common reads:\n• **Mean reversion**: in range-bound markets, price tends to revert toward the middle band after touching either outer band.\n• **Squeeze breakout**: when the bands contract tightly (low volatility), a breakout in either direction often signals the start of a new directional move.\n• **Walking the band**: in strong trends, price 'rides' along the upper (or lower) band for many bars — counter-trend mean-reversion entries lose money during these phases.\n\nBollinger Bands are popular partly because they're visually intuitive — you can see volatility regime, trend direction, and extreme readings on a single chart.",
  description_hi:
    "Bollinger Bands teen lines plot karta: middle ek SMA (default 20-period), upper band SMA + (standard deviation × multiplier), lower band SMA - (standard deviation × multiplier). Default multiplier 2 hai.\n\nStatistically, normally distributed prices mein ~95% bar closes bands ke andar fall karte hain. Upper band ke paas closes high relative prices signal karte; lower band ke paas low relative prices. Bands khud expand karti hain realized volatility rise hone pe aur contract hone pe — visible volatility regime.\n\nTeen common reads:\n• **Mean reversion**: range-bound markets mein outer band touch karne ke baad price middle band ki taraf revert karta hai.\n• **Squeeze breakout**: jab bands tightly contract karein (low volatility), kisi bhi direction mein breakout often new directional move start karta hai.\n• **Walking the band**: strong trends mein price upper (ya lower) band ke saath 'ride' karta hai kaafi bars tak — in phases mein counter-trend mean-reversion entries paise lose karte hain.\n\nBollinger Bands popular hain partly visually intuitive hone ki wajah se — volatility regime, trend direction, aur extreme readings ek hi chart pe dikhte hain.",

  formula_explanation:
    "Middle band = SMA(close, period). Standard deviation σ = sqrt(mean((close - SMA)²)) over the same window. Upper band = SMA + (mult × σ). Lower band = SMA - (mult × σ). Defaults: period 20, multiplier 2. The stddev is biased (divisor N), matching Pine Script's default.",

  default_period: 20,
  period_range: [5, 50],
  common_periods: [10, 20, 50],

  use_cases: [
    {
      scenario: "Mean reversion in range-bound NIFTY",
      what_to_do: "When NIFTY is consolidating, buy near the lower band, sell near the upper band, target the middle",
      why: "Range markets respect the bands as mean-reversion levels — high hit rate when there's no trend.",
    },
    {
      scenario: "Bollinger Squeeze breakout setup",
      what_to_do: "Watch for unusually narrow bandwidth (bands close together) — exit any range trades and prepare for a breakout",
      why: "Volatility clusters. After contracted-band periods, the next directional move is statistically larger than average — squeeze breakouts are pre-positioned for big winners.",
    },
    {
      scenario: "Trend-strength gauge",
      what_to_do: "If price is consistently closing above the upper band, the uptrend is strong; if it can't even reach the upper band on rallies, the trend is fading",
      why: "Band-walking is a quantitative trend-strength signal that complements ADX.",
    },
  ],

  common_signals: [
    {
      signal: "Lower band bounce",
      condition: "Price touches/closes below lower band, then closes back inside",
      action: "Mean-reversion long candidate (range market).",
    },
    {
      signal: "Upper band rejection",
      condition: "Price touches upper band but closes back below",
      action: "Mean-reversion short / long exit (range market).",
    },
    {
      signal: "Squeeze setup",
      condition: "Bandwidth at multi-week lows",
      action: "Reduce range-trading; prepare for breakout in either direction.",
    },
    {
      signal: "Squeeze release",
      condition: "Bands begin expanding from a squeeze, price breaks out",
      action: "Trend continuation entry in breakout direction.",
    },
  ],

  pitfalls: [
    "Strong trends 'walk' the upper or lower band — mean-reversion shorts on every upper-band touch in an uptrend will accumulate losses.",
    "2-standard-deviation 95% containment assumes normal distribution. Real markets have fatter tails — outer-band 'touches' happen more often than the math predicts.",
    "Bollinger Bands say nothing about direction during a squeeze — the breakout could be up or down. Don't pre-commit.",
    "Different libraries occasionally use sample vs biased stddev — band widths differ slightly. Be consistent.",
    "On daily charts with weekend gaps, the first bar after a gap can produce unusually wide bands until the SMA window catches up.",
  ],

  works_well_with: ["rsi", "atr", "volume-profile", "macd"],
  works_poorly_with: ["keltner-channel", "donchian-channel"],

  example_strategies: [
    "Bollinger Squeeze Breakout (daily NIFTY-50 stocks)",
    "Bollinger Mean Reversion (15m sideways BANKNIFTY)",
    "Bollinger Band-Walking Filter (positional trends)",
  ],

  indian_context:
    "Bollinger Bands on daily NIFTY are widely watched — the upper band near 21-day highs is reported in business media as a 'momentum' signal. BANKNIFTY's higher beta makes its bands wider in absolute terms; comparing 'NIFTY at upper band' to 'BANKNIFTY at upper band' isn't apples-to-apples without normalization. For F&O stocks during earnings season, Bollinger Squeeze on the daily right before results is a popular pre-event setup — the squeeze captures the pre-announcement consolidation, and the breakout direction on results day is a high-conviction trade. On expiry day intraday, bands compress unnaturally in the last 90 minutes due to OI-driven mean reversion — don't trade Bollinger setups after 2:00 PM IST on expiry.",
};
