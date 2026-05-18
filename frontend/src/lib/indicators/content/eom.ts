import type { IndicatorContent } from "./_types";

export const EOM: IndicatorContent = {
  slug: "eom",
  name: "EOM (Ease of Movement)",
  category: "volume",
  complexity: "intermediate",

  one_liner_en:
    "Measures how 'easily' price moves — high EOM = small volume drove big price move; low EOM = lots of volume, little movement.",
  one_liner_hi:
    "Measure karta price kitna 'easily' move karta — high EOM = small volume ne big price move drive kiya; low EOM = lots of volume, little movement.",

  description_en:
    "Richard Arms' Ease of Movement (1980s) inverts the usual volume-confirmation logic. Most indicators say 'high volume good, low volume bad'. EOM asks a more nuanced question: how much volume did it TAKE to move price by a given amount?\n\nBig price move on light volume = high EOM = market is 'easy' to push in that direction = trend has strong tailwind. Big price move on heavy volume = low EOM = market is 'resisting' the move = trend may stall.\n\nThe canonical signals:\n- EOM crossing above 0 = bullish bias confirmed (price moving up easily)\n- EOM crossing below 0 = bearish bias confirmed\n- Bullish divergence: price lower low, EOM higher low — same logic as other oscillator divergences.\n\nUseful as a 'quality of trend' read alongside trend-following indicators. A trend with rising EOM is healthier than one with falling EOM at the same price magnitude.",
  description_hi:
    "Richard Arms ka Ease of Movement (1980s) usual volume-confirmation logic ko invert karta. Most indicators kehte 'high volume good, low volume bad'. EOM zyada nuanced sawal poochta: given amount se price move karne ke liye kitna volume LAGA?\n\nBig price move on light volume = high EOM = market us direction mein 'easy' to push = trend strong tailwind ke saath. Big price move on heavy volume = low EOM = market move ko 'resist' kar raha = trend stall ho sakti.\n\nCanonical signals:\n- EOM 0 ke upar cross = bullish bias confirmed (price easily up move kar raha)\n- EOM 0 ke neeche cross = bearish bias confirmed\n- Bullish divergence: price lower low, EOM higher low — other oscillator divergences ki same logic.\n\nTrend-following indicators ke baju 'quality of trend' read ki tarah useful. Rising EOM ke saath trend same price magnitude pe falling EOM wale trend se healthier.",

  formula_explanation:
    "Midpoint move = ((high + low) / 2) - ((prev_high + prev_low) / 2). Box ratio = volume / (high - low). EOM_raw = Midpoint move / Box ratio. Smoothed via 14-bar SMA. Output unbounded. Default smoothing period: 14.",

  default_period: 14,
  period_range: [5, 50],
  common_periods: [9, 14, 21],

  use_cases: [
    {
      scenario: "Trend-quality filter",
      what_to_do: "Long bias only when smoothed EOM > 0 AND rising over the last 10 bars",
      why: "Confirms not just direction but that the move is happening with 'ease' — high-quality trends.",
    },
    {
      scenario: "Divergence at key levels",
      what_to_do: "At 52-week-high tests, watch for falling EOM as price prints new highs — trend is straining",
      why: "Price hitting new highs but EOM falling means it takes ever-more volume to push higher — exhaustion.",
    },
  ],

  common_signals: [
    {
      signal: "EOM zero cross up",
      condition: "Smoothed EOM crosses above 0",
      action: "Bullish bias activated.",
    },
    {
      signal: "Bearish divergence at resistance",
      condition: "Price new high + smoothed EOM lower high",
      action: "Heads-up for reversal; trend losing 'ease'.",
    },
  ],

  pitfalls: [
    "Division-by-(high-low) blows up on doji-like bars where high ≈ low. Implementations should guard; verify yours does.",
    "Output is unbounded and not cross-symbol comparable. Direction + divergence only.",
    "On low-volume holiday weeks, the box-ratio collapses and EOM becomes meaningless.",
    "Less common in Indian retail than OBV / MFI — community discussion thin.",
  ],

  works_well_with: ["obv", "mfi", "ema", "atr"],
  works_poorly_with: ["volume-profile", "cmf"],

  example_strategies: [
    "EOM Trend-Quality Filter (daily NIFTY-100 stocks)",
    "EOM Divergence Hunter (weekly indices)",
  ],

  indian_context:
    "EOM is well-suited to identifying 'easy' trending NSE F&O stocks during sector rotations — when capital rotates into a sector, the leaders show rising EOM (small volume moves them a lot, because there's no resistance). On index futures, EOM is less differentiated from raw price because aggregation dilutes the ease signal.",
};
