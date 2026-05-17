import type { IndicatorContent } from "./_types";

export const VOLUME_PROFILE: IndicatorContent = {
  slug: "volume-profile",
  name: "Volume Profile",
  category: "volume",
  complexity: "advanced",

  one_liner_en:
    "Horizontal histogram showing how much volume traded at each price level. Reveals high-volume nodes (support/resistance) and low-volume gaps.",
  one_liner_hi:
    "Horizontal histogram jo dikhata har price level pe kitna volume traded hua. High-volume nodes (support/resistance) aur low-volume gaps reveal karta.",

  description_en:
    "Volume Profile bins all trades over a chosen range (session, week, custom) by PRICE LEVEL, not by time. The output is a horizontal histogram plotted on the price axis. The price level with the most volume is the Point of Control (POC) — usually the strongest support/resistance in the analyzed range.\n\nThree key concepts:\n• **Point of Control (POC)**: single price level with highest traded volume. Acts as the most-watched level in the range — fair-value magnet.\n• **Value Area (VA)**: the price range containing ~70% of the volume, centered on POC. Inside VA = balanced market; outside = imbalance.\n• **Low Volume Nodes (LVNs)**: price levels where almost nothing traded. Price tends to slice through LVNs quickly because there are no resting orders to absorb moves.\n\nReading a Volume Profile is more art than indicator: high-volume nodes are support/resistance, low-volume nodes are 'air gaps' where price moves fast.\n\nProfiles can be Session Volume Profile (single trading day), Composite (multiple days merged), or Anchored (from a chosen event). Each serves a different timeframe purpose.",
  description_hi:
    "Volume Profile chosen range (session, week, custom) ke saare trades ko PRICE LEVEL se bin karta, time se nahi. Output horizontal histogram price axis pe plot. Most volume wala price level Point of Control (POC) hai — usually analyzed range ka strongest support/resistance.\n\nTeen key concepts:\n• **Point of Control (POC)**: single price level highest traded volume ke saath. Range ka most-watched level — fair-value magnet.\n• **Value Area (VA)**: price range jo ~70% volume contain karta, POC ke centered. VA ke andar = balanced market; bahar = imbalance.\n• **Low Volume Nodes (LVNs)**: price levels jahan almost nothing traded. Price LVNs ke through fast slice karta kyunki absorb karne ke liye resting orders nahi hote.\n\nVolume Profile read karna art zyada hai indicator kam: high-volume nodes support/resistance, low-volume nodes 'air gaps' jahan price fast move karta.\n\nProfiles Session Volume Profile (single day), Composite (multiple days merged), ya Anchored (chosen event se) ho sakte. Har ek different timeframe purpose serve karta.",

  formula_explanation:
    "Bin price range into N price buckets (default 24-100 bins depending on chart range). For each bar in the chosen range, allocate its volume across the price levels it covered (proportionally between high and low). Sum the allocations per bin to get the histogram. POC = bin with max sum. Value Area = smallest set of bins that contains ≥ 70% of total volume, expanding outward from POC.",

  default_period: null,
  period_range: null,
  common_periods: [],

  use_cases: [
    {
      scenario: "Identifying intraday support / resistance",
      what_to_do: "Plot Session Volume Profile. POC and Value Area boundaries are the day's most-relevant levels",
      why: "Volume-based levels are objective (where trading actually happened) whereas drawn support/resistance is subjective. POC respect rate is empirically higher than swing-high/low S/R.",
    },
    {
      scenario: "Trading air-gap moves through LVNs",
      what_to_do: "When price enters a low-volume zone, expect a fast move through to the next high-volume node",
      why: "LVNs have no absorbing orders. Price doesn't pause at them — momentum trades through.",
    },
    {
      scenario: "Composite profile for multi-day swing setup",
      what_to_do: "Build a 5-day composite profile. Multi-day POC is a strong swing-level reference",
      why: "Composite POC concentrates many days of trading interest at one price — exceptional structural support/resistance.",
    },
  ],

  common_signals: [
    {
      signal: "POC reject from above",
      condition: "Price approaches POC from above and bounces",
      action: "Trend-continuation long candidate — POC acted as support.",
    },
    {
      signal: "POC break-through",
      condition: "Price breaks decisively through POC with volume confirmation",
      action: "Trend regime change candidate — POC has flipped from support to resistance (or vice versa).",
    },
    {
      signal: "LVN slice",
      condition: "Price enters a low-volume zone in trend direction",
      action: "Hold position through the air-gap; expect rapid move to next HVN.",
    },
  ],

  pitfalls: [
    "Different libraries handle the per-bar volume allocation differently (some assume uniform distribution between high-low, others use OHLC weighting). Results can differ visibly.",
    "Bin count is a tuning parameter — too few bins blurs POC; too many bins makes every level a 'small POC'. 24-50 is a common sweet spot.",
    "Profile is RANGE-DEPENDENT. Today's profile excludes yesterday's structure. A swing trader needs composite profiles, not session.",
    "Doesn't work well on stocks with sparse trading — needs continuous liquid volume.",
    "Volume Profile is descriptive (what happened) not predictive (what will happen). Always pair with a trigger indicator.",
  ],

  works_well_with: ["vwap", "supertrend", "atr", "obv"],
  works_poorly_with: ["bollinger-bands", "rsi"],

  example_strategies: [
    "POC Reversal (intraday F&O)",
    "Value Area Mean Reversion (15m NIFTY)",
    "Composite Profile Swing Trade (daily NSE-100 stocks)",
  ],

  indian_context:
    "Volume Profile became mainstream in Indian retail via TradingView's free tools and YouTube education in the late 2010s. On NIFTY index futures, daily Session Volume Profile POCs cluster within 50-100 points of each other across normal weeks — these multi-day clusters are the most-respected horizontal levels intraday. BANKNIFTY's wider intraday range means its POC ladders span 200-500 points. For NSE F&O stocks, weekly composite profiles built from 5 trading sessions catch institutional accumulation zones that price-only charts miss. Pre-budget weeks often see unusual POC concentration as pre-positioning dominates trading.",
};
