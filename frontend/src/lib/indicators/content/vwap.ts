import type { IndicatorContent } from "./_types";

export const VWAP: IndicatorContent = {
  slug: "vwap",
  name: "VWAP (Volume Weighted Average Price)",
  category: "volume",
  complexity: "beginner",

  one_liner_en:
    "The session's average price weighted by volume — the 'fair price' institutions benchmark their fills against.",
  one_liner_hi:
    "Session ka volume-weighted average price — 'fair price' jise institutions apne fills ka benchmark maante hain.",

  description_en:
    "VWAP is the running average of every trade in the current session, weighted by trade size. By design it resets at the start of each trading day — VWAP is a session indicator, not a moving average.\n\nWhy traders care: VWAP is the price institutions are trying to beat. A large fund buying 10 lakh shares over a day tries to fill BELOW VWAP (better than average); a fund selling tries to fill ABOVE. Retail can read this directly — when price is below VWAP, institutions are likely net-buying; above, net-selling. (This is a heuristic, not a guarantee.)\n\nVWAP is also a dynamic intraday support/resistance line. In a strong uptrend, pullbacks to VWAP from above are common entry points; in a downtrend, rallies to VWAP from below are entry points for shorts.\n\nFor positional swing traders, anchored VWAP (resets at a chosen event, e.g. earnings or a swing low) becomes a multi-day fair-price reference. The session VWAP is the textbook default; anchored VWAP is the advanced variant.",
  description_hi:
    "VWAP current session ke har trade ka running average hai, trade size se weighted. Design se har trading day ke start pe reset hota — VWAP session indicator hai, moving average nahi.\n\nKyun traders care karte hain: VWAP wo price hai jise institutions beat karna chahti hain. Bada fund din mein 10 lakh shares buy karte hue VWAP ke NEECHE fill karne ki koshish karta (average se better); selling fund VWAP ke UPAR fill karne ki. Retail directly read kar sakta — price VWAP ke neeche hai to institutions likely net-buying; upar = net-selling. (Heuristic hai, guarantee nahi.)\n\nVWAP intraday dynamic support/resistance line bhi hai. Strong uptrend mein upar se VWAP tak pullbacks common entry points; downtrend mein neeche se VWAP tak rallies short entries.\n\nPositional swing traders ke liye anchored VWAP (chosen event pe reset, jaise earnings ya swing low) multi-day fair-price reference banta. Session VWAP textbook default hai; anchored VWAP advanced variant.",

  formula_explanation:
    "VWAP = Σ(typical_price × volume) / Σ(volume), accumulated from session start. Typical price = (high + low + close) / 3. The numerator and denominator both reset at session start (9:15 IST for NSE). No tunable parameters — it's session-driven, not period-driven.",

  default_period: null,
  period_range: null,
  common_periods: [],

  use_cases: [
    {
      scenario: "Intraday trend bias filter",
      what_to_do: "If price is above session VWAP and VWAP is sloping up, take only longs intraday; opposite for shorts",
      why: "Single-condition intraday trend filter that aligns retail directionality with institutional flow.",
    },
    {
      scenario: "Pullback entry to VWAP",
      what_to_do: "In an uptrend, wait for price to retrace from session highs back to VWAP, then enter long on a bullish candle close",
      why: "VWAP acts as intraday dynamic support; pullback entries here have empirically tight stops (just below VWAP) and high follow-through.",
    },
    {
      scenario: "Anchored VWAP from a key event",
      what_to_do: "Anchor VWAP to a recent swing high / low / earnings bar. The resulting line is a multi-day fair-price benchmark",
      why: "Anchored VWAP captures institutional positioning since the chosen event — powerful for swing trades that play out over days.",
    },
  ],

  common_signals: [
    {
      signal: "VWAP reclaim",
      condition: "Price closes back above VWAP after spending time below in an intraday session",
      action: "Intraday long entry candidate — institutional flow turning up.",
    },
    {
      signal: "VWAP rejection",
      condition: "Price rallies up to VWAP in a downtrend, fails to close above",
      action: "Short entry candidate.",
    },
    {
      signal: "VWAP cross + volume spike",
      condition: "VWAP cross coincides with a > 2× average-volume bar",
      action: "Stronger signal than VWAP cross alone — institutional flow likely.",
    },
  ],

  pitfalls: [
    "VWAP RESETS daily. Don't compare today's VWAP to yesterday's — they're different sessions, different anchors.",
    "On low-volume days, VWAP is dominated by a few large prints and the line gets unstable.",
    "Pre-open and post-close ticks don't count toward VWAP in NSE — line only forms during 09:15-15:30 IST.",
    "Different libraries seed VWAP slightly differently for the first few ticks of the day; values can diverge in the first 5 minutes.",
    "For F&O contracts near expiry, VWAP gets distorted by closing-out activity — less reliable on Wednesday-Thursday of expiry week.",
  ],

  works_well_with: ["volume-profile", "ema", "supertrend", "obv"],
  works_poorly_with: ["bollinger-bands", "rsi"],

  example_strategies: [
    "VWAP Pullback Buyer (intraday NIFTY F&O)",
    "VWAP Reclaim with Volume Spike (1m scalp)",
    "Anchored VWAP from Earnings (positional swing)",
  ],

  indian_context:
    "VWAP is the most-watched intraday line on Indian F&O — every BANKNIFTY scalper has it on their chart. Algorithmic VWAP-aware execution is widespread among NSE proprietary desks; retail can read 'price above VWAP' as a directional hint about who's buying. NIFTY 50 intraday tends to mean-revert toward VWAP in the first 90 minutes (9:15-10:45) and trend away from it in the last 90 (14:00-15:30). On expiry day, VWAP is less informative after 14:00 IST because OI-driven settlement flow overwhelms organic trade flow.",
};
