import type { IndicatorContent } from "./_types";

export const HEIKIN_ASHI: IndicatorContent = {
  slug: "heikin-ashi",
  name: "Heikin-Ashi (Smoothed Candles)",
  category: "advanced",
  complexity: "intermediate",

  one_liner_en:
    "Modified candlestick formula that smooths out noise. A run of same-coloured candles signals a clean trend.",
  one_liner_hi:
    "Modified candlestick formula jo noise smooth karta. Same-colour candles ka run ek clean trend signal karta.",

  description_en:
    "Heikin-Ashi ('average bar' in Japanese) recomputes each OHLC bar using values that incorporate the previous bar's data. The result is a chart that filters out small price reversals and emphasizes the dominant direction. Trends look smoother and clearer; chop looks like flat doji-style candles.\n\nFormula essence: each Heikin-Ashi candle's open averages the previous candle's open/close; the close averages all four current OHLC values; the high and low take the larger / smaller of (current high/low, HA open, HA close). The recursive design is what creates the smoothing.\n\nThe canonical use is trend visualization. A sequence of consecutive green (close > open) Heikin-Ashi candles signals a strong uptrend; consecutive red signals a strong downtrend. Tiny-bodied / wicked HA candles signal indecision and often precede reversals.\n\nLimitations: Heikin-Ashi candles are NOT the actual price action. The 'open' and 'close' are computed values, not real prices. Don't use HA values for stop-loss placement or for fills — always reference actual OHLC for those.",
  description_hi:
    "Heikin-Ashi ('average bar' Japanese mein) har OHLC bar ko recompute karta values use karke jo previous bar ke data incorporate karte hain. Result ek chart jo small price reversals filter karta aur dominant direction emphasize karta. Trends smoother aur clearer dikhte; chop flat doji-style candles ki tarah.\n\nFormula essence: har Heikin-Ashi candle ka open previous candle ke open/close ka average; close current OHLC ke saare 4 values ka average; high aur low (current high/low, HA open, HA close) mein se larger / smaller. Recursive design hi smoothing create karta.\n\nCanonical use trend visualization hai. Consecutive green (close > open) HA candles ka sequence strong uptrend signal karta; consecutive red strong downtrend. Tiny-bodied / wicked HA candles indecision signal karte aur often reversals se pehle aate.\n\nLimitations: Heikin-Ashi candles actual price action NAHI hain. 'Open' aur 'close' computed values hain, real prices nahi. Stop-loss placement ya fills ke liye HA values use mat karo — un ke liye hamesha actual OHLC reference karo.",

  formula_explanation:
    "HA_close = (open + high + low + close) / 4. HA_open = (prev HA_open + prev HA_close) / 2 (first bar uses regular open). HA_high = max(high, HA_open, HA_close). HA_low = min(low, HA_open, HA_close). Recursive on HA_open — that's the smoothing.",

  default_period: null,
  period_range: null,
  common_periods: [],

  use_cases: [
    {
      scenario: "Trend visualization and bias filter",
      what_to_do: "Replace regular candlesticks with Heikin-Ashi on the higher timeframe (daily or 4h) for cleaner trend reading",
      why: "Smoother candles make trend regime obvious at a glance — 5 consecutive green HA candles vs a mixed regular chart is a clear visual difference.",
    },
    {
      scenario: "Trend-ride hold rule",
      what_to_do: "Hold longs as long as HA candles stay green; exit when the first red HA candle appears (or first HA candle with a meaningful upper wick)",
      why: "Mechanical exit rule that captures most of a clean trend and exits on the first sign of weakness — popular for swing trades.",
    },
    {
      scenario: "Multi-timeframe HA confluence",
      what_to_do: "Take signals when daily HA is green AND 4h HA flips to green",
      why: "Top-down alignment using the same indicator across timeframes — simple and effective for swing setups.",
    },
  ],

  common_signals: [
    {
      signal: "Strong-trend run",
      condition: "5+ consecutive same-coloured HA candles with no significant wicks on the trending side",
      action: "Hold position — high-quality trend underway.",
    },
    {
      signal: "Trend-weakness candle",
      condition: "First HA candle with a significant opposing wick after a clean trend run",
      action: "Tighten stops or scale out — momentum fading.",
    },
    {
      signal: "Doji-style HA",
      condition: "HA candle with tiny body and wicks on both sides",
      action: "Indecision; stand aside or wait for next-bar confirmation.",
    },
    {
      signal: "Trend flip",
      condition: "First red HA candle in a green run (or vice versa)",
      action: "Exit trend trades; consider reverse setup if confirmed.",
    },
  ],

  pitfalls: [
    "HA values are NOT real prices. Stop-losses, take-profits, broker orders must all reference actual OHLC, not HA OHLC.",
    "HA lags the real chart by 1-2 bars because of the recursive smoothing. Reversal candles appear slightly later than on regular candlesticks.",
    "Doesn't help with entry precision — HA tells you 'are we in a trend?' not 'enter here'. Pair with a real trigger.",
    "Gap days produce HA candles that 'absorb' the gap into a long body — they can hide important price-action information.",
    "Different platforms handle the first HA bar's seed slightly differently. The first 5-10 bars of an HA chart can disagree across tools.",
  ],

  works_well_with: ["ema", "supertrend", "adx", "macd"],
  works_poorly_with: ["bollinger-bands", "rsi"],

  example_strategies: [
    "Daily HA Trend Ride (NIFTY positional)",
    "HA + EMA Pullback (1h F&O stocks)",
    "Multi-Timeframe HA Confluence (swing trades)",
  ],

  indian_context:
    "Heikin-Ashi gained popularity in Indian retail via YouTube education channels in the late 2010s — it's now a standard alternative chart-style choice on TradingView and Indian charting platforms. On daily NIFTY, HA reveals trend regimes more clearly than regular candlesticks, especially the boundaries between trend phases and consolidation. For BANKNIFTY's higher volatility, HA's noise-smoothing is particularly useful — it filters out the intraday whipsaws that make regular BANKNIFTY candles look chaotic. Positional swing traders use weekly HA on F&O stocks for multi-month trend reads. Critical reminder: real broker fills happen at actual prices, not HA prices — many beginners learn this expensively.",
};
