import type { IndicatorContent } from "./_types";

export const SUPPORTS_RESISTANCES: IndicatorContent = {
  slug: "supports-resistances",
  name: "Auto Support / Resistance",
  category: "pattern",
  complexity: "intermediate",

  one_liner_en:
    "Algorithmic detection of horizontal price levels that have been touched repeatedly. Removes the subjectivity of hand-drawn S/R.",
  one_liner_hi:
    "Horizontal price levels ka algorithmic detection jo repeatedly touched hue hain. Hand-drawn S/R ki subjectivity remove karta.",

  description_en:
    "Hand-drawing support and resistance is the most subjective part of technical analysis — two traders looking at the same chart will pick different levels. Auto S/R algorithms try to remove that subjectivity by detecting price levels that have been tested by multiple swing highs or swing lows over a lookback window.\n\nThe typical algorithm: find local pivots (bars where the high is greater than the N bars on either side, or the low is lower than the N bars on either side). Cluster nearby pivots into 'levels' — if 3+ pivots are within X% of each other, they form a level. Levels with more touches and more recent touches are scored higher.\n\nThe output: a small number of horizontal lines (usually 4-8) representing the strongest levels in the chart. Some implementations colour-code by strength; others just plot all levels at uniform thickness.\n\nReality: auto S/R is a starting point, not gospel. Algorithms can miss psychologically important levels (round numbers like NIFTY 22,000) and over-emphasize levels created by anomaly bars. Use as a fast scan, then validate manually for high-stakes setups.",
  description_hi:
    "Hand-drawing support aur resistance technical analysis ka sabse subjective part hai — do traders same chart dekh ke different levels pick karenge. Auto S/R algorithms us subjectivity ko remove karne ki koshish karte hain price levels detect karke jo multiple swing highs ya lows se tested hue hain lookback window mein.\n\nTypical algorithm: local pivots find karo (bars jahan high N bars ke either side se bada hai, ya low lower hai). Nearby pivots ko 'levels' mein cluster karo — 3+ pivots X% ke andar = ek level. Zyada touches aur recent touches wale levels higher score.\n\nOutput: kuch horizontal lines (usually 4-8) chart ke strongest levels representing. Kuch implementations strength se colour-code karte; doosre saare levels uniform thickness pe plot karte.\n\nReality: auto S/R starting point hai, gospel nahi. Algorithms psychologically important levels (NIFTY 22,000 jaise round numbers) miss kar sakte aur anomaly bars se bane levels ko over-emphasize kar sakte. Fast scan ki tarah use karo, phir high-stakes setups manually validate karo.",

  formula_explanation:
    "Pivot detection: bar[i] is a local high if high[i] > high[i-N..i-1] AND high[i] > high[i+1..i+N]. Local low: mirror. Cluster pivots: levels[i] = list of pivot values within `tolerance%` (default 0.5%) of each other. Score level by (count of touches × decay_factor^bars_since_last_touch). Keep top K levels (default 8). N typically 5-10 bars on intraday, 20-50 on daily.",

  default_period: 20,
  period_range: [5, 100],
  common_periods: [10, 20, 50],

  use_cases: [
    {
      scenario: "Fast multi-symbol scan",
      what_to_do: "Apply auto S/R to a watchlist of 50 F&O stocks. Flag stocks where current price is within 0.5% of a strong level for closer manual inspection",
      why: "Auto detection makes mechanical screening possible — manual S/R is too slow at this scale.",
    },
    {
      scenario: "Entry confirmation",
      what_to_do: "After your strategy signals an entry, verify there isn't a strong opposing S/R level between entry and your target",
      why: "Reduces 'good signal but wrong target' losses — auto S/R surfaces resistance / support the strategy itself doesn't see.",
    },
    {
      scenario: "Stop-loss placement reference",
      what_to_do: "Place stop just past the nearest auto-detected support (for longs) or resistance (for shorts)",
      why: "Volatility-aware stop placement that respects historical price memory — different from ATR-based stops in a useful way.",
    },
  ],

  common_signals: [
    {
      signal: "Strong-level test",
      condition: "Price approaches a level with 3+ historical touches",
      action: "High-conviction reversal zone — watch for confirmation candle.",
    },
    {
      signal: "Level break with volume",
      condition: "Price closes through a strong level with volume > 1.5× average",
      action: "Break-and-retest or continuation trade.",
    },
    {
      signal: "Level cluster",
      condition: "Multiple auto-detected levels within 0.5% of each other",
      action: "Exceptional support/resistance — high reaction probability.",
    },
  ],

  pitfalls: [
    "Different algorithms produce different levels. There's no single 'correct' auto S/R implementation.",
    "Auto S/R doesn't know about round-number psychology — NIFTY 22,000 might be more important than any algorithmic level but algorithms won't promote it.",
    "Pivot N parameter is sensitive. Small N (3-5) finds many noisy pivots; large N (20+) finds only major levels and misses tactical intermediate ones.",
    "Anomaly bars (flash crashes, fat-finger spikes) can create phantom levels that get high scores due to extreme touches. Manual sanity check helps.",
    "Auto S/R is descriptive (historical levels) — it doesn't predict where new levels will form.",
  ],

  works_well_with: ["volume-profile", "vwap", "atr", "ema"],
  works_poorly_with: ["bollinger-bands", "donchian-channel"],

  example_strategies: [
    "S/R Cluster Reversal (daily F&O stocks)",
    "Auto-S/R Watchlist Scan (multi-symbol momentum)",
    "Break-and-Retest at Strong Level (1h indices)",
  ],

  indian_context:
    "Auto S/R is increasingly popular among Indian retail technical traders as charting platforms (TradingView, Investing.com) ship reasonable default detectors. On NIFTY daily, auto S/R typically surfaces the 200-DMA, recent monthly highs / lows, and round numbers like 22000 / 23000 — these align with the levels Indian financial media reports. For F&O stocks, auto S/R is most useful as a screening tool to find stocks near major levels; positional setups still benefit from manual confirmation. Multi-touch levels on weekly charts of large-cap NSE F&O stocks are particularly reliable.",
};
