import type { IndicatorContent } from "./_types";

export const STOCHASTIC: IndicatorContent = {
  slug: "stochastic",
  name: "Stochastic Oscillator",
  category: "momentum",
  complexity: "beginner",

  one_liner_en:
    "Where the current close sits within the recent high-low range, scaled 0-100. Sensitive momentum reader.",
  one_liner_hi:
    "Current close recent high-low range mein kahan baitha hai, 0-100 scale pe. Sensitive momentum reader hai.",

  description_en:
    "The Stochastic plots two lines: %K (the raw position of the close inside the last `period` bars' high-low range) and %D (a moving average of %K, typically 3-period). Above 80 is overbought; below 20 is oversold. It is faster and noisier than RSI — the same conditions that produce a 70 on RSI often produce an 85 on Stochastic.\n\nThe two flavours you'll see most are Fast Stochastic (raw %K + a 3-SMA %D) and Slow Stochastic (one extra smoothing on %K). Slow is the default in most platforms because Fast crosses too often to be tradeable.\n\nThe canonical signal is the %K-crossing-%D inside an extreme zone: %K crosses up through %D while both are below 20 = oversold reversal long. %K crosses down through %D while both are above 80 = overbought rejection short. Crosses in the middle (20-80) are mostly noise unless paired with a trend filter.\n\nLike RSI, Stochastic stays pinned in extremes during strong trends. Don't naively short every 80 read on a breakout day; pair with a trend filter (EMA slope, supertrend direction) or use 90/10 wider bands.",
  description_hi:
    "Stochastic do lines plot karta hai: %K (current close last `period` bars ke high-low range mein kahan hai) aur %D (%K ka moving average, typically 3-period). 80 ke upar overbought; 20 ke neeche oversold. RSI se zyada fast aur noisy hai — wahi conditions jo RSI pe 70 banati hain, Stochastic pe 85 banati hain.\n\nDo flavours sabse zyada milte hain: Fast Stochastic (raw %K + 3-SMA %D) aur Slow Stochastic (%K pe ek extra smoothing). Slow most platforms ka default hai kyunki Fast itne crosses karta hai ki tradeable nahi rehta.\n\nCanonical signal hai %K-crossing-%D ek extreme zone ke andar: %K %D ke upar cross kare aur dono 20 ke neeche = oversold reversal long. %K %D ke neeche cross kare aur dono 80 ke upar = overbought rejection short. Middle (20-80) ke crosses mostly noise hain unless trend filter ke saath paired ho.\n\nRSI ki tarah, Stochastic strong trends mein extremes pe pinned reh sakta hai. Breakout day pe har 80 read pe short mat lo; trend filter (EMA slope, supertrend direction) ke saath pair karo ya 90/10 wider bands use karo.",

  formula_explanation:
    "%K = 100 × (close - lowest_low(period)) / (highest_high(period) - lowest_low(period)). %D = SMA(%K, smoothing). Slow Stochastic adds one more SMA pass on %K before the formula. Default: period=14, %D smoothing=3, slow-K smoothing=3.",

  default_period: 14,
  period_range: [3, 50],
  common_periods: [5, 14, 21],

  use_cases: [
    {
      scenario: "Sideways consolidations on hourly NIFTY",
      what_to_do: "Trade %K crosses inside the 20-80 zone for mean-reversion",
      why: "In range markets Stochastic is the cleanest oscillator — its sensitivity catches reversals that RSI misses by 1-2 bars.",
    },
    {
      scenario: "Entry timing inside an existing trend",
      what_to_do: "Wait for Stochastic to pull back below 20 in an uptrend, then enter on cross-up",
      why: "Trend-aligned oversold dips are statistically better than naive 20-line bounces because they remove counter-trend false starts.",
    },
    {
      scenario: "Confirmation of breakout exhaustion",
      what_to_do: "Watch for Stochastic to fail to make a new high while price tests resistance again",
      why: "Bearish divergence on Stochastic confirms what RSI may already be showing — the second source reduces single-indicator false reads.",
    },
  ],

  common_signals: [
    {
      signal: "Oversold bullish cross",
      condition: "%K crosses above %D while both < 20",
      action: "Long entry candidate.",
    },
    {
      signal: "Overbought bearish cross",
      condition: "%K crosses below %D while both > 80",
      action: "Long exit / short candidate.",
    },
    {
      signal: "Bullish divergence",
      condition: "Price lower low, Stochastic higher low",
      action: "Heads-up for a reversal; require confirmation.",
    },
  ],

  pitfalls: [
    "Faster than RSI by design — gives more signals AND more false signals. Don't size positions purely on Stochastic alone.",
    "On strongly trending days, Stochastic pins at 80+ for hours. The 'overbought' read is the trend continuing, not an exit signal.",
    "Stochastic on 1-minute candles is essentially noise during the first 15 minutes of market open — the high-low range is still forming.",
    "%K and %D crossing exactly at the open or close of a bar (no follow-through) often reverses on the next bar.",
  ],

  works_well_with: ["ema", "supertrend", "bollinger-bands"],
  works_poorly_with: ["rsi", "williams-r", "cci"],

  example_strategies: [
    "Slow Stochastic Reversal (15m BANKNIFTY)",
    "Stochastic Pullback in Uptrend (1h NIFTY)",
  ],

  indian_context:
    "Indian intraday traders use Stochastic 5-3-3 (very fast) on 1-min and 3-min charts for momentum scalps, especially on BANKNIFTY where intraday ranges are wide enough to give the indicator room to extend. On illiquid mid-cap stocks, Stochastic gets gappy and the cross signals are unreliable — stick to liquid F&O names. For the index futures, Stochastic crosses at 9:30-10:00 IST (post-opening volatility settling) tend to be the cleanest setups of the day.",
};
