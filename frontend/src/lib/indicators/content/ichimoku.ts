import type { IndicatorContent } from "./_types";

export const ICHIMOKU: IndicatorContent = {
  slug: "ichimoku",
  name: "Ichimoku Cloud (Kinko Hyo)",
  category: "trend",
  complexity: "advanced",

  one_liner_en:
    "Five-line Japanese trend system that visualizes future support/resistance via a 'cloud' ahead of price.",
  one_liner_hi:
    "Paanch-line Japanese trend system jo future support/resistance visualize karta hai price ke aage 'cloud' ke through.",

  description_en:
    "Ichimoku Kinko Hyo (literally 'one-glance equilibrium chart') is the Swiss Army knife of Japanese trend analysis. It plots five components:\n\n• Tenkan-sen (Conversion line, default 9 periods): (highest high + lowest low) / 2 over 9 bars — fast trend reference.\n• Kijun-sen (Base line, default 26): same formula, 26 bars — slower trend.\n• Senkou Span A (Leading span A): (Tenkan + Kijun) / 2, plotted 26 bars INTO THE FUTURE.\n• Senkou Span B (Leading span B): (highest high + lowest low) / 2 over 52 bars, also plotted 26 bars into the future.\n• Chikou Span (Lagging span): current close plotted 26 bars BACKWARD.\n\nThe shaded area between Span A and Span B is the 'cloud' (kumo) — green when A > B, red when B > A. Price above the cloud = uptrend; below = downtrend; inside = consolidation. Crossings of the Tenkan / Kijun, of price / cloud, and the cloud's own colour flip are all distinct signals.\n\nIchimoku is information-dense — five lines on a chart looks overwhelming. The payoff is that ONE indicator answers trend / momentum / support-resistance / forward-projection in a single visual. The cost is a steep learning curve.",
  description_hi:
    "Ichimoku Kinko Hyo (literally 'one-glance equilibrium chart') Japanese trend analysis ka Swiss Army knife hai. Paanch components plot karta:\n\n• Tenkan-sen (Conversion line, default 9 periods): (highest high + lowest low) / 2 over 9 bars — fast trend reference.\n• Kijun-sen (Base line, default 26): same formula, 26 bars — slower trend.\n• Senkou Span A (Leading span A): (Tenkan + Kijun) / 2, 26 bars FUTURE mein plot.\n• Senkou Span B (Leading span B): (highest high + lowest low) / 2 over 52 bars, bhi 26 bars future mein plot.\n• Chikou Span (Lagging span): current close 26 bars PEECHE plot.\n\nSpan A aur Span B ke beech ka shaded area 'cloud' (kumo) hai — green when A > B, red when B > A. Cloud ke upar price = uptrend; neeche = downtrend; andar = consolidation. Tenkan / Kijun crossings, price / cloud crossings, aur cloud ka khud ka colour flip — sab distinct signals hain.\n\nIchimoku information-dense hai — paanch lines chart pe overwhelming dikhti hain. Payoff yeh hai ki EK indicator trend / momentum / support-resistance / forward-projection sab ek single visual mein answer karta hai. Cost steep learning curve hai.",

  formula_explanation:
    "Tenkan = (highest_high(9) + lowest_low(9)) / 2. Kijun = (highest_high(26) + lowest_low(26)) / 2. Span A = (Tenkan + Kijun) / 2, shifted +26 bars. Span B = (highest_high(52) + lowest_low(52)) / 2, shifted +26 bars. Chikou = close, shifted -26 bars. The 9/26/52 defaults come from Hosoda's 1968 publication.",

  default_period: 26,
  period_range: [10, 100],
  common_periods: [9, 26, 52],

  use_cases: [
    {
      scenario: "Multi-timeframe trend assessment",
      what_to_do: "Glance at Ichimoku: is price above cloud, is cloud green, are Tenkan/Kijun aligned bullish, is Chikou above price-26-bars-ago?",
      why: "All four conditions positive = textbook strong uptrend. Saves cross-referencing 3-4 separate indicators.",
    },
    {
      scenario: "Cloud breakout entries",
      what_to_do: "Enter long when price closes above the cloud after a period inside or below",
      why: "Cloud edges are powerful psychological levels; sustained breakouts often run for many sessions.",
    },
    {
      scenario: "Cloud-thickness as volatility proxy",
      what_to_do: "Thin cloud = weak support/resistance; thick cloud = strong support/resistance",
      why: "Trade size and conviction calibration. Thick green cloud below price is a high-confidence pullback buy zone.",
    },
  ],

  common_signals: [
    {
      signal: "Bullish cloud breakout",
      condition: "Price closes above the cloud after being inside or below",
      action: "Long entry — multi-week trend candidate.",
    },
    {
      signal: "Tenkan-Kijun bullish cross",
      condition: "Tenkan crosses above Kijun",
      action: "Faster trend signal — stronger when ABOVE the cloud.",
    },
    {
      signal: "Cloud colour flip (Kumo twist)",
      condition: "Span A crosses above Span B (or below) in the future portion of the chart",
      action: "Trend regime change projected ~26 bars out.",
    },
    {
      signal: "Chikou span confirms",
      condition: "Chikou (current close shifted back) is above price-26-bars-ago in an uptrend",
      action: "Cleanest 4th leg of the textbook strong trend filter.",
    },
  ],

  pitfalls: [
    "Five lines + shaded cloud = visually overwhelming for beginners. Hide the Chikou span if it confuses you initially.",
    "26-bar forward projection looks predictive but is purely a mathematical shift — it doesn't 'know' the future.",
    "Doesn't work well in slow-grinding markets — the cloud becomes a vague consolidation zone with no edge.",
    "Default 9/26/52 was tuned for Japanese stock data in the 1960s. Some traders use 7/22/44 for crypto, 12/24/120 for weekly — be aware your default may not be your edge.",
    "Mid-cap and small-cap Indian stocks often have gaps that make the cloud calculations choppy — Ichimoku is cleaner on indices and large caps.",
  ],

  works_well_with: ["rsi", "atr", "volume-profile"],
  works_poorly_with: ["bollinger-bands", "donchian-channel"],

  example_strategies: [
    "Ichimoku Cloud Breakout (daily NIFTY-50 stocks)",
    "Tenkan-Kijun Cross with Cloud Filter (1h BANKNIFTY)",
    "Multi-Timeframe Ichimoku Confluence (positional swing)",
  ],

  indian_context:
    "Ichimoku has a small but devoted following in Indian retail — most common on daily NIFTY-50 and BANKNIFTY for positional trend analysis. The cloud's leading-forward projection makes it visually intuitive for traders who use 'levels-based' language (support, resistance, breakout) more than oscillator language. Less common on intraday Indian markets because the 9/26/52 default doesn't map cleanly to 5-min / 15-min bars without re-tuning. NIFTY swing-traders sometimes use Tenkan-Kijun cross on weekly charts as a multi-month bias signal.",
};
