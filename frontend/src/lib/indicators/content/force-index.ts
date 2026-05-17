import type { IndicatorContent } from "./_types";

export const FORCE_INDEX: IndicatorContent = {
  slug: "force-index",
  name: "Force Index (Elder)",
  category: "volume",
  complexity: "intermediate",

  one_liner_en:
    "Alexander Elder's volume-momentum hybrid: (close change) × volume. Sustained positive = institutional buying.",
  one_liner_hi:
    "Alexander Elder ka volume-momentum hybrid: (close change) × volume. Sustained positive = institutional buying.",

  description_en:
    "Force Index multiplies the close-to-close price change by the bar's volume — a simple but powerful combination. A big up-day on big volume produces a large positive Force; same up-day on light volume produces a small positive Force. Conversely, light-volume rallies show low Force (suggesting they may not stick); heavy-volume rallies show high Force (institutional involvement).\n\nRaw Force is noisy bar-to-bar. Standard practice: smooth with an EMA. Short EMA (13-period) for trade-timing reads; long EMA (50+) for trend-confirmation reads.\n\nElder's recommendation: use Force(13) for entries, Force(2) for stop-loss timing (very sensitive), Force(100) for longer-term trend bias. Zero-line crosses on Force EMA = momentum-regime shift; divergence between Force EMA and price = trend exhaustion candidate.",
  description_hi:
    "Force Index close-to-close price change ko bar ke volume se multiply karta — simple but powerful combination. Big up-day on big volume = large positive Force; same up-day on light volume = small positive Force. Conversely, light-volume rallies show low Force (suggest karta they may not stick); heavy-volume rallies show high Force (institutional involvement).\n\nRaw Force bar-to-bar noisy hai. Standard practice: EMA se smooth karo. Short EMA (13-period) trade-timing reads ke liye; long EMA (50+) trend-confirmation reads ke liye.\n\nElder ki recommendation: Force(13) entries ke liye, Force(2) stop-loss timing ke liye (very sensitive), Force(100) longer-term trend bias ke liye. Force EMA pe zero-line crosses = momentum-regime shift; Force EMA aur price ke beech divergence = trend exhaustion candidate.",

  formula_explanation:
    "Force_raw = (close - prev_close) × volume. Output in (price units × shares), so absolute values aren't cross-symbol comparable — only direction and divergences matter. Smoothed via EMA. Default smoothing: 13.",

  default_period: 13,
  period_range: [2, 100],
  common_periods: [2, 13, 50, 100],

  use_cases: [
    {
      scenario: "Volume-confirmed entry timing",
      what_to_do: "Long when Force(13) crosses above 0 AND price > 50-EMA",
      why: "Captures the moment institutional buying flips positive; trend-aligned via EMA filter.",
    },
    {
      scenario: "Divergence at key resistance",
      what_to_do: "Watch for price new high + Force(13) lower high — bearish divergence with volume context",
      why: "Force divergence is more informative than RSI divergence because it factors volume — institutional drying up of demand is more meaningful than retail-only oscillator divergence.",
    },
    {
      scenario: "Stop-loss timing with Force(2)",
      what_to_do: "Exit when Force(2) flips against you for 2 consecutive bars",
      why: "Force(2) is so sensitive it acts as a tight trailing-stop trigger.",
    },
  ],

  common_signals: [
    {
      signal: "Force zero-line cross up",
      condition: "Force(13) crosses above 0",
      action: "Bullish regime — long candidate.",
    },
    {
      signal: "Bullish Force divergence",
      condition: "Price lower low, Force(13) higher low",
      action: "Reversal candidate — institutional selling is exhausting.",
    },
  ],

  pitfalls: [
    "Raw values not cross-symbol comparable (depend on share count and price level). Use direction + divergence only.",
    "On low-volume bars, Force values flatten and lose information. Indian holiday weeks and pre-event quiet days produce low Force noise-floors.",
    "Three different period regimes (2 / 13 / 100) tell different stories. Don't mix them naively.",
    "Less popular in Indian retail than OBV / MFI — community setup-sharing thin.",
  ],

  works_well_with: ["obv", "mfi", "ema", "vwap"],
  works_poorly_with: ["volume-profile", "cmf"],

  example_strategies: [
    "Force Index Crossover (daily F&O)",
    "Force(2) Trailing-Stop Trail (positional)",
  ],

  indian_context:
    "Force Index on daily NSE F&O stocks captures earnings-period institutional positioning unusually well — the 5 sessions before results often show building Force in the eventual breakout direction. For BANKNIFTY index futures intraday, Force(13) on 15-min reliably flags the day's directional bias by 10:30 IST.",
};
