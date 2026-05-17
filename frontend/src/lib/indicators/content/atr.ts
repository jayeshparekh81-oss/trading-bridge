import type { IndicatorContent } from "./_types";

export const ATR: IndicatorContent = {
  slug: "atr",
  name: "ATR (Average True Range)",
  category: "volatility",
  complexity: "beginner",

  one_liner_en:
    "Average size of recent price ranges. Measures volatility — bigger ATR = bigger expected moves per bar.",
  one_liner_hi:
    "Recent price ranges ka average size. Volatility measure karta — bada ATR = har bar bada expected move.",

  description_en:
    "ATR is a pure volatility measure — it does NOT tell you direction. Wilder (the same author as RSI / ADX / SAR) defined 'true range' as the largest of: today's high-low, |today's high - yesterday's close|, |today's low - yesterday's close|. ATR is the smoothed average of true range over `period` bars. Default period is 14.\n\nThe key uses are stop-loss and position-sizing:\n• **Volatility-aware stops**: instead of a fixed-percent stop, use 'price - 2 × ATR' for longs. Stops adapt to the symbol's normal noise — quiet stocks get tight stops, volatile ones get loose stops.\n• **Position-sizing**: target a fixed rupee risk per trade (e.g. ₹2000), divide by ATR-based stop distance, get position size. This auto-calibrates exposure to volatility — small positions in NIFTY's high-vol regimes, larger positions when calm.\n• **Volatility regime**: rising ATR means volatility is expanding (often coinciding with trends or news); falling ATR means volatility is contracting (often coinciding with consolidations).\n\nATR is the workhorse under Supertrend, Keltner Channels, and most volatility-aware risk-management systems.",
  description_hi:
    "ATR pure volatility measure hai — direction NAHI batata. Wilder (RSI / ADX / SAR ka same author) ne 'true range' define kiya: aaj ke high-low, |aaj ka high - kal ka close|, |aaj ka low - kal ka close| — in teen mein se sabse bada. ATR true range ka smoothed average hai `period` bars pe. Default period 14 hai.\n\nKey uses stop-loss aur position-sizing hain:\n• **Volatility-aware stops**: fixed-percent stop ke bajaye 'price - 2 × ATR' long ke liye use karo. Stops symbol ke normal noise ke saath adapt karte hain — quiet stocks ko tight stops, volatile ko loose stops.\n• **Position-sizing**: fixed rupee risk per trade target karo (e.g. ₹2000), ATR-based stop distance se divide karo, position size milta hai. Yeh auto-calibrate karta hai exposure ko volatility ke saath — NIFTY high-vol mein chhote positions, calm mein bade.\n• **Volatility regime**: rising ATR matlab volatility expand ho rahi (often trends ya news ke saath); falling ATR matlab contracting (often consolidations).\n\nATR Supertrend, Keltner Channels, aur most volatility-aware risk-management systems ka workhorse hai.",

  formula_explanation:
    "True Range (TR) = max(high - low, |high - prev_close|, |low - prev_close|). ATR = Wilder's smoothed moving average of TR over `period` bars (recursive: ATR(today) = (ATR(yesterday) × (period - 1) + TR(today)) / period). Default period: 14. Output unbounded, in price units.",

  default_period: 14,
  period_range: [3, 50],
  common_periods: [7, 14, 21],

  use_cases: [
    {
      scenario: "Initial stop-loss placement",
      what_to_do: "For longs, place stop at (entry - 2 × ATR). For shorts, (entry + 2 × ATR).",
      why: "Tight enough to limit loss, loose enough to avoid normal noise. The 2× multiplier is conservative; 1.5× is aggressive; 3× is wide.",
    },
    {
      scenario: "Position sizing under a fixed risk budget",
      what_to_do: "Size = risk_per_trade_₹ / (stop_distance_in_₹). Stop distance = ATR × multiplier × lot_size_for_F&O.",
      why: "Equalizes risk across symbols regardless of price level — a ₹50 stock and a ₹5000 stock both consume the same ₹ at the same stop hit.",
    },
    {
      scenario: "Volatility-aware Supertrend tuning",
      what_to_do: "Use ATR(10) × 3 for Supertrend on indices, ATR(7) × 2 for fast intraday F&O scalp",
      why: "Different volatility regimes need different trail aggressiveness — ATR makes that tuning explicit.",
    },
  ],

  common_signals: [
    {
      signal: "Volatility expansion",
      condition: "ATR rising for many consecutive bars",
      action: "Widen stops, reduce position size — bigger moves coming.",
    },
    {
      signal: "Volatility contraction",
      condition: "ATR at multi-week lows",
      action: "Tight stops feasible; squeeze breakouts likely (pair with Bollinger Squeeze).",
    },
  ],

  pitfalls: [
    "ATR doesn't give direction. Never trade on ATR alone — pair with a trend or momentum signal.",
    "Different libraries use slightly different smoothing (Wilder's vs simple vs Cutler's). Backtest values may diverge from live values by a few percent if you mix sources.",
    "ATR on illiquid stocks is noisy and gappy — the indicator was designed for continuously-trading liquid names.",
    "First `period` bars are warmup — ATR seeds from a simple average then transitions to Wilder smoothing. Don't use the first 14 values.",
    "Gap days inflate true-range temporarily; one big gap can dominate ATR for several days.",
  ],

  works_well_with: ["supertrend", "bollinger-bands", "ema", "keltner-channel"],
  works_poorly_with: ["rsi", "stochastic"],

  example_strategies: [
    "ATR Trailing Stop (positional F&O)",
    "ATR-Sized Risk Manager (all live strategies)",
    "Bollinger + ATR Confluence (volatility-regime breakouts)",
  ],

  indian_context:
    "NIFTY's daily ATR averages roughly 0.7-1.2% of price; BANKNIFTY 1.2-1.8% — BANKNIFTY is empirically ~50% more volatile. Mid-cap NSE F&O stocks during earnings season often spike ATR by 2-3× normal — these are the days to widen stops or stand aside, not narrow them. For commodity F&O (MCX gold, crude), ATR is in absolute price units that aren't comparable to equity-index ATR — always normalize ATR / price (the % ATR) for cross-symbol comparison.",
};
