import type { IndicatorContent } from "./_types";

export const RSI: IndicatorContent = {
  slug: "rsi",
  name: "RSI (Relative Strength Index)",
  category: "momentum",
  complexity: "beginner",

  one_liner_en:
    "Measures the speed of price changes on a 0-100 scale. Above 70 is overbought, below 30 is oversold.",
  one_liner_hi:
    "Price changes ki speed measure karta hai 0-100 scale pe. 70 ke upar overbought, 30 ke neeche oversold.",

  description_en:
    "RSI compares the average size of recent up-moves to the average size of recent down-moves and squashes the result into a 0-100 range. A reading near 100 means almost every recent candle closed higher than the one before it; a reading near 0 means almost every recent candle closed lower.\n\nThe 30 / 70 thresholds are conventions, not laws. In a strong trending market, RSI can sit above 70 (or below 30) for many bars without reversing — that's the trend continuing, not a reversal signal. In a range-bound market, the 30 / 70 lines act much more reliably as bounce zones.\n\nDivergence is RSI's most-cited setup: when price makes a higher high but RSI makes a lower high, the underlying momentum is weakening even though price is still grinding up — often a heads-up before a reversal. The opposite (lower low in price, higher low in RSI) hints at a bullish reversal.\n\nRSI is computed bar-by-bar and updates on every new tick of the current bar. Pure-price input; volume isn't factored in.",
  description_hi:
    "RSI recent up-moves ki average size aur recent down-moves ki average size compare karta hai aur result ko 0-100 range mein squash karta hai. 100 ke paas reading matlab almost har recent candle pichli candle se higher closed hui; 0 ke paas matlab almost har candle lower closed hui.\n\n30 / 70 thresholds conventions hain, rules nahi. Strong trending market mein RSI 70 ke upar (ya 30 ke neeche) kaafi bars tak baith sakta hai bina reverse hue — yeh trend continue ho raha hai, reversal signal nahi. Range-bound market mein 30 / 70 lines bahut zyada reliable bounce zones ki tarah kaam karti hain.\n\nDivergence RSI ka sabse cited setup hai: jab price higher high banaye lekin RSI lower high banaye, underlying momentum weak ho raha hai bhale price grind kar raha ho — often reversal se pehle heads-up. Ulta (price mein lower low, RSI mein higher low) bullish reversal hint karta hai.\n\nRSI bar-by-bar compute hota hai aur current bar ke har tick pe update hota hai. Pure-price input; volume factor nahi hota.",

  formula_explanation:
    "Average gain (close-to-close ups over `period` bars) divided by average loss (close-to-close downs over the same window) gives the relative strength ratio. The ratio is then mapped to 0-100 via `100 - 100/(1 + RS)`. Wilder's smoothing (recursive exponential average) is the standard — pandas-ta, TA-Lib, and Pine all default to it.",

  default_period: 14,
  period_range: [2, 50],
  common_periods: [9, 14, 21],

  use_cases: [
    {
      scenario: "Range-bound market (NIFTY pre-event, BANKNIFTY consolidation)",
      what_to_do: "Use 30 / 70 levels as bounce-back zones",
      why: "When price isn't trending, the oscillator overshoots both extremes and reverts to the middle — making 30 / 70 reliable mean-reversion triggers.",
    },
    {
      scenario: "Strong trending market (NIFTY breakout day, sector momentum)",
      what_to_do: "Switch to 40 / 60 inner bands and treat them as support / resistance, not bounce zones",
      why: "An uptrend keeps RSI above 50 most of the time; pullbacks to 40-50 are entry continuation zones, not oversold reversals.",
    },
    {
      scenario: "Divergence hunting around supports / resistances",
      what_to_do: "Mark RSI peaks/troughs and compare to price peaks/troughs over the last 10-20 bars",
      why: "Divergence near a known structural level (52-week high, prior swing) has materially higher conversion than divergence in the middle of nowhere.",
    },
  ],

  common_signals: [
    {
      signal: "Oversold bounce",
      condition: "RSI crosses up through 30",
      action: "Long entry candidate — confirm with a candle reversal pattern or higher-timeframe trend.",
    },
    {
      signal: "Overbought rejection",
      condition: "RSI crosses down through 70",
      action: "Long exit / short entry candidate — risky to short in a strong uptrend.",
    },
    {
      signal: "Bullish divergence",
      condition: "Price prints a lower low, RSI prints a higher low",
      action: "Watch for a reversal candle pattern; long entry on confirmation.",
    },
    {
      signal: "Bearish divergence",
      condition: "Price prints a higher high, RSI prints a lower high",
      action: "Tighten long stops or set up a short.",
    },
    {
      signal: "Centerline cross",
      condition: "RSI crosses above 50 (bull bias) or below 50 (bear bias)",
      action: "Trend-bias filter — pair with a moving-average direction check.",
    },
  ],

  pitfalls: [
    "Strong trends keep RSI overbought/oversold for many bars — fighting that with a 'sell at 70' rule loses money fast.",
    "Lower periods (5-7) produce frequent whipsaws. Use 14+ on daily charts; 7-9 only for fast intraday scalps with strict stops.",
    "RSI from a 5-min chart is not the same indicator as RSI from a daily chart. Always specify which timeframe you're reading.",
    "Divergence can persist for many bars before resolving — divergence is a heads-up, not an entry trigger by itself.",
    "On illiquid stocks (low volume), RSI gets gappy and noisy; the indicator was designed for continuously-trading liquid names.",
  ],

  works_well_with: ["macd", "bollinger-bands", "vwap", "supertrend"],
  works_poorly_with: ["stochastic", "williams-r", "cci"],

  example_strategies: [
    "RSI 14 Oversold Bounce (15m NIFTY)",
    "RSI Divergence Trader (1h BANKNIFTY)",
    "RSI + EMA Pullback (daily large-cap stocks)",
  ],

  indian_context:
    "NIFTY and BANKNIFTY around expiry week tend to range — RSI 30/70 reads bounce-zone reliably. On expiry day itself, both indices are dominated by OI unwinding and RSI loses predictive power for the last 90 minutes. For Bank Nifty intraday, RSI(9) on 5-minute candles is a common scalper setting because the index is faster-moving than the broader NIFTY. For positional NSE F&O stocks (Reliance, HDFC Bank), RSI(14) on the daily is the textbook default and works well as a divergence detector around support/resistance from monthly pivots.",
};
