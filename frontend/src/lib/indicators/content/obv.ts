import type { IndicatorContent } from "./_types";

export const OBV: IndicatorContent = {
  slug: "obv",
  name: "OBV (On Balance Volume)",
  category: "volume",
  complexity: "beginner",

  one_liner_en:
    "Cumulative volume that adds on up days and subtracts on down days. Tracks whether volume is confirming the price trend.",
  one_liner_hi:
    "Cumulative volume jo up days mein add aur down days mein subtract karta hai. Track karta hai ki volume price trend ko confirm kar raha ya nahi.",

  description_en:
    "OBV is a running cumulative total. The rule is simple: if today's close > yesterday's close, ADD today's volume to OBV; if close < yesterday's, SUBTRACT; if equal, leave unchanged. The result is a single line that rises when buying is dominant and falls when selling is dominant.\n\nThe magnitude of OBV is meaningless — what matters is the direction and divergences relative to price. Three classic reads:\n• **Confirmation**: price makes new high, OBV makes new high — trend is healthy, volume is supporting the move.\n• **Bullish divergence**: price makes new low, OBV makes higher low — selling is exhausting even as price drops, often precedes a reversal up.\n• **Bearish divergence**: price makes new high, OBV makes lower high — buying is fading even as price rises, often precedes a reversal down.\n\nOBV was invented by Joe Granville in 1963. It's binary in the worst way — a 0.01% up close adds the SAME volume contribution as a 5% up close. That makes it noisy on tiny-move bars. But the cumulative shape is what carries signal, not individual bars.",
  description_hi:
    "OBV running cumulative total hai. Rule simple: aaj ka close > kal ka close hai to aaj ka volume OBV mein ADD karo; close < kal ka hai to SUBTRACT; equal hai to unchanged. Result ek single line jo buying dominant hone pe rise karti aur selling dominant hone pe fall karti.\n\nOBV ki magnitude meaningless hai — direction aur price ke saath divergences important hain. Teen classic reads:\n• **Confirmation**: price naya high banaye, OBV naya high banaye — trend healthy, volume move ko support kar raha.\n• **Bullish divergence**: price naya low banaye, OBV higher low banaye — selling exhaust ho raha bhale price drop ho raha, often reversal up se pehle.\n• **Bearish divergence**: price naya high banaye, OBV lower high banaye — buying fade ho raha bhale price rise ho raha, often reversal down se pehle.\n\nOBV Joe Granville ne 1963 mein invent kiya. Binary worst way mein — 0.01% up close 5% up close jaisa hi volume contribution add karta. Tiny-move bars pe noisy banata. But cumulative shape signal carry karti, individual bars nahi.",

  formula_explanation:
    "OBV(today) = OBV(yesterday) + sign(close - prev_close) × volume. sign returns +1, 0, or -1. Cumulative from a series start point — absolute values depend on when you started counting. No tunable parameters.",

  default_period: null,
  period_range: null,
  common_periods: [],

  use_cases: [
    {
      scenario: "Confirmation of breakouts",
      what_to_do: "After a price breakout above resistance, check that OBV also broke above its own recent high",
      why: "Price-only breakouts on weak volume are statistically more likely to fail; OBV-confirmed breakouts have higher follow-through.",
    },
    {
      scenario: "Divergence hunting near key levels",
      what_to_do: "At a 52-week high or 200-EMA test, watch for OBV to make a LOWER high while price prints a NEW high",
      why: "Bearish OBV divergence at key resistance is a high-conviction reversal setup — institutional accumulation has stopped.",
    },
    {
      scenario: "Smart-money tracking on quiet days",
      what_to_do: "If price is flat / ranging but OBV is steadily rising for many sessions, institutions are accumulating without moving the tape",
      why: "Sideways accumulation precedes many sustained uptrends — OBV makes it visible.",
    },
  ],

  common_signals: [
    {
      signal: "OBV confirms new high",
      condition: "Price makes new high AND OBV makes new high in the same bar/session",
      action: "Trend is volume-confirmed — hold longs, add on pullbacks.",
    },
    {
      signal: "Bearish OBV divergence",
      condition: "Price new high, OBV lower high",
      action: "Tighten stops, scale out — distribution likely.",
    },
    {
      signal: "Bullish OBV divergence",
      condition: "Price new low, OBV higher low",
      action: "Watch for reversal setup with candle pattern confirmation.",
    },
  ],

  pitfalls: [
    "OBV's magnitude depends on where you START the calculation. Two charts with different start dates can show very different absolute OBV values — only direction and divergence matter.",
    "Binary up/down classification means a 0.01% up close adds the same volume as a 5% up close. Big-move bars are under-counted; small-move bars are over-counted.",
    "On Indian markets, the first 15 minutes of trading is heavy on retail volume and lighter on institutional — OBV signals in 9:15-9:30 IST are less reliable than in mid-session.",
    "OBV doesn't distinguish between accumulation and distribution within the same bar — if a bar opens at 100, runs to 110, closes at 105, OBV counts the full bar volume as 'up' (close > prev close) even though selling was dominant from 110→105.",
    "Stocks with thin / patchy volume show jittery OBV — designed for continuously-trading liquid names.",
  ],

  works_well_with: ["vwap", "macd", "ema", "volume-profile"],
  works_poorly_with: ["bollinger-bands", "rsi"],

  example_strategies: [
    "OBV Divergence Reversal (daily F&O stocks)",
    "OBV + EMA Trend Confirmation (positional)",
    "OBV Breakout Confirmation (intraday F&O)",
  ],

  indian_context:
    "OBV is widely watched by Indian retail technical analysts during accumulation / distribution phases on F&O stocks. On NIFTY index daily, OBV is less differentiated from price (the index aggregates so much volume that bullish-divergence setups are rare); on individual stocks it's much more informative. For F&O stocks ahead of earnings, a rising OBV in the 5 sessions before announcement often predicts the post-results direction more reliably than price action alone. On low-float small-cap NSE F&O stocks, OBV becomes noisy — stick to large-caps for reliable signals.",
};
