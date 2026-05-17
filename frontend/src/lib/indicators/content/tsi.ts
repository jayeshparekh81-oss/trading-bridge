import type { IndicatorContent } from "./_types";

export const TSI: IndicatorContent = {
  slug: "tsi",
  name: "TSI (True Strength Index)",
  category: "rate",
  complexity: "advanced",

  one_liner_en:
    "Double-smoothed momentum oscillator. Combines responsiveness with low noise — divergence-friendly.",
  one_liner_hi:
    "Double-smoothed momentum oscillator. Responsiveness aur low noise dono combine karta — divergence-friendly hai.",

  description_en:
    "TSI takes raw momentum (today's close minus yesterday's close), then applies two layers of EMA smoothing — typically 25 periods then 13 periods. The same double-smoothing is applied to the absolute value of momentum. The ratio is multiplied by 100, giving a centered oscillator that ranges roughly -100 to +100 (with typical values in -50 to +50 in real markets).\n\nWhy bother with double-smoothing? Single EMA smoothing kills noise but introduces lag. TSI's two-pass approach removes more noise than a single EMA without proportionally more lag — the result is a momentum line that's clean enough to read divergences on, fast enough to fire meaningful signals.\n\nThe canonical usage is signal-line crossover (TSI + an SMA / EMA of TSI) like MACD, plus zero-line crosses and divergence. TSI has a small but loyal following — it's well-suited to swing trading on daily charts where you want fewer-but-better signals than RSI gives.",
  description_hi:
    "TSI raw momentum (aaj ka close minus kal ka close) leta hai, phir EMA smoothing ki do layers apply karta — typically 25 periods phir 13 periods. Wahi double-smoothing absolute value of momentum pe bhi apply hota. Ratio 100 se multiply hota, ek centered oscillator deta jo roughly -100 se +100 range karta (real markets mein typical values -50 se +50).\n\nDouble-smoothing kyun? Single EMA smoothing noise kills karti but lag introduce karti hai. TSI ka two-pass approach single EMA se zyada noise remove karta bina proportionally zyada lag ke — result hai ek momentum line jo divergences read karne ke liye clean hai, meaningful signals fire karne ke liye fast hai.\n\nCanonical usage signal-line crossover (TSI + TSI ka SMA / EMA) MACD ki tarah, plus zero-line crosses aur divergence. TSI ka chhota but loyal following hai — swing trading daily charts pe well-suited jahan RSI se fewer-but-better signals chahiye.",

  formula_explanation:
    "PC = close - prev_close (price change). Double-smoothed PC = EMA(EMA(PC, slow), fast). Double-smoothed |PC| = EMA(EMA(|PC|, slow), fast). TSI = 100 × (double-smoothed PC) / (double-smoothed |PC|). Defaults: slow=25, fast=13. A signal line is typically EMA(TSI, 13).",

  default_period: 25,
  period_range: [5, 100],
  common_periods: [13, 25, 50],

  use_cases: [
    {
      scenario: "Swing-trade signal-line crossover",
      what_to_do: "Use TSI(25, 13) with a 13-period EMA signal line. Long on TSI crossing above its signal; short on opposite",
      why: "Cleaner than MACD on daily charts because of double-smoothing; fewer false crosses in choppy markets.",
    },
    {
      scenario: "Divergence at major levels",
      what_to_do: "TSI divergence near 52-week highs or major support tests — high-conviction reversal setup",
      why: "Double-smoothing kills micro-noise, so TSI divergences are more meaningful than RSI / MACD divergences at the same chart resolution.",
    },
    {
      scenario: "Zero-line trend filter",
      what_to_do: "Only take long signals when TSI > 0 and rising",
      why: "TSI above 0 reflects sustained upside momentum across both smoothing windows — strong filter for trend-followers.",
    },
  ],

  common_signals: [
    {
      signal: "TSI signal-line cross up",
      condition: "TSI crosses above its EMA signal line",
      action: "Long entry candidate — quality momentum confirmation.",
    },
    {
      signal: "Zero-line cross up",
      condition: "TSI crosses above 0",
      action: "Trend regime change to bullish.",
    },
    {
      signal: "Bearish divergence",
      condition: "Price new high, TSI lower high",
      action: "Strong reversal warning — TSI's smoothing makes divergence more reliable.",
    },
  ],

  pitfalls: [
    "Two layers of smoothing means significant lag on fast moves. TSI is for swing / positional, not scalping.",
    "Default parameters (25, 13) are TradingView's; some references use (13, 7) for faster reaction. Verify your library.",
    "Less popular than RSI / MACD means thinner Indian retail discussion / setup-sharing — you're often working from primary sources.",
    "Output range is technically -100 to +100 but rarely reaches those extremes in real data. Don't expect ±70 to mean overbought / oversold the way RSI's ±70 does.",
    "On very-low-volatility periods, double-smoothing collapses TSI near zero — indicator goes silent.",
  ],

  works_well_with: ["macd", "ema", "supertrend", "atr"],
  works_poorly_with: ["momentum", "roc"],

  example_strategies: [
    "TSI Signal Cross (daily NIFTY-50 stocks)",
    "TSI Divergence at 52-Week Highs (weekly indices)",
    "TSI Zero-Line Trend Filter (positional swing)",
  ],

  indian_context:
    "TSI has a niche following among Indian swing traders working on daily charts of large-cap NSE F&O stocks. The double-smoothing makes it well-suited to the multi-day swings of cash equities while filtering out intraday whipsaws that other oscillators struggle with. On indices, TSI is less differentiated from MACD because index data is already smoothed by aggregation. For BANKNIFTY's higher-volatility daily, TSI(13, 7) [faster setting] tracks better than the default (25, 13).",
};
