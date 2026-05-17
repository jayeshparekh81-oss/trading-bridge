import type { IndicatorContent } from "./_types";

export const DEMARKER: IndicatorContent = {
  slug: "demarker",
  name: "DeMarker (DeM)",
  category: "momentum",
  complexity: "intermediate",

  one_liner_en:
    "Tom DeMark's price-exhaustion oscillator — readings above 0.7 mark overbought, below 0.3 oversold, with cleaner signals than RSI in cycling markets.",
  one_liner_hi:
    "Tom DeMark ka price-exhaustion oscillator — 0.7 ke upar readings overbought, 0.3 ke neeche oversold, cycling markets mein RSI se cleaner signals.",

  description_en:
    "DeMarker was designed by Tom DeMark to identify price exhaustion zones where reversals become probable. Unlike RSI which compares close-to-close changes, DeMarker compares each bar's high to the previous bar's high (DeMax) and each bar's low to the previous bar's low (DeMin). It reads how aggressively price is making new extremes.\n\nThe output ranges from 0 to 1. Readings above 0.7 indicate buyers are exhausting their willingness to bid higher — overbought. Below 0.3 indicates sellers exhausting their willingness to sell lower — oversold. The asymmetric design (separate DeMax/DeMin tracking) makes DeMarker particularly responsive in cyclic markets.\n\nDeMark's broader system uses sequential setup counts (TD-9, TD-13) that build on DeMarker readings; this content covers just the base oscillator. The 0.3/0.7 thresholds are conventions, not rules — adjust to 0.25/0.75 for high-volatility instruments.\n\nFor Indian retail, DeMarker shines on instruments that genuinely cycle — NIFTY in low-VIX environments, BANKNIFTY between major events. In strong trending periods, DeMarker stays pinned in its extreme zones similar to other oscillators.",
  description_hi:
    "DeMarker Tom DeMark ne design kiya price exhaustion zones identify karne ke liye jahan reversals probable hote. RSI close-to-close changes compare karta; DeMarker har bar ke high ko previous bar ke high se (DeMax) aur low ko previous low se (DeMin) compare karta. Read karta price kitni aggressively new extremes bana rahi.\n\nOutput 0 se 1 range mein hota. 0.7 ke upar readings batati buyers higher bid karne ki willingness exhaust kar rahe — overbought. 0.3 ke neeche sellers lower sell karne ki willingness exhaust kar rahe — oversold. Asymmetric design (separate DeMax/DeMin tracking) DeMarker ko cyclic markets mein particularly responsive banata.\n\nDeMark ka broader system sequential setup counts (TD-9, TD-13) use karta jo DeMarker readings pe build karte; ye content base oscillator cover karta. 0.3/0.7 thresholds conventions hain, rules nahi — high-volatility instruments ke liye 0.25/0.75 use karo.\n\nIndian retail ke liye DeMarker un instruments pe shine karta jo genuinely cycle karte — low-VIX environments mein NIFTY, major events ke beech BANKNIFTY. Strong trending periods mein DeMarker apne extreme zones mein pinned rehta dusre oscillators ki tarah.",

  formula_explanation:
    "Step 1: DeMax[i] = max(0, High[i] - High[i-1]). Step 2: DeMin[i] = max(0, Low[i-1] - Low[i]). Step 3: Smoothed DeMax = SMA[period] of DeMax. Step 4: Smoothed DeMin = SMA[period] of DeMin. Step 5: DeMarker = SmoothedDeMax / (SmoothedDeMax + SmoothedDeMin). Result is bounded in [0, 1]. Default period 14 matches RSI convention.",

  default_period: 14,
  period_range: [9, 30],
  common_periods: [13, 14, 21],

  use_cases: [
    {
      scenario: "Cyclic / range-bound market overbought-oversold detection",
      what_to_do: "Long on DeMarker cross up through 0.3; exit on cross down through 0.7",
      why: "DeMarker reads extreme-making aggression cleanly in cycling markets, giving timely reversal entries.",
    },
    {
      scenario: "Divergence-based reversal entries",
      what_to_do: "Lower low in price, higher low in DeMarker = bullish reversal candidate at known support",
      why: "Divergence on DeMarker tends to be earlier and cleaner than RSI divergence on cycling instruments.",
    },
    {
      scenario: "Filtering out weak breakout setups",
      what_to_do: "Avoid long breakouts when DeMarker already above 0.7; price exhaustion suggests poor follow-through",
      why: "Entering at exhaustion levels = entering when momentum is most likely to fade.",
    },
  ],

  common_signals: [
    {
      signal: "Oversold reversal",
      condition: "DeMarker crosses up through 0.3",
      action: "Long entry candidate; confirm with reversal candle.",
    },
    {
      signal: "Overbought rejection",
      condition: "DeMarker crosses down through 0.7",
      action: "Long exit / short entry candidate.",
    },
    {
      signal: "Bullish divergence",
      condition: "Price lower low, DeMarker higher low",
      action: "Bullish reversal candidate at established support.",
    },
    {
      signal: "Sustained extreme",
      condition: "DeMarker stays > 0.7 (or < 0.3) for 5+ bars",
      action: "Trend dominates; don't fade — wait for the reading to leave the zone.",
    },
  ],

  pitfalls: [
    "Strong trends keep DeMarker pinned at extremes — don't use 'sell at 0.7' in trending markets.",
    "Default period 14 mimics RSI but DeMarker's asymmetric construction means signals fire at different times.",
    "On intraday timeframes (5m, 15m), DeMarker is noisy; daily / 4h is its sweet spot.",
    "The 0.3/0.7 thresholds are conventions; some traders use 0.25/0.75 for high-volatility instruments like BANKNIFTY.",
    "DeMarker doesn't read volume — pair with a volume indicator for breakout confirmation.",
  ],

  works_well_with: ["bollinger-bands", "supports-resistances", "ema", "mfi"],
  works_poorly_with: ["rsi", "stochastic"],

  example_strategies: [
    "DeMarker mean-reversion on NIFTY daily in low-VIX regimes",
    "DeMarker divergence trader on BANKNIFTY 4h",
    "DeMark TD-9 sequential setup foundation",
  ],

  indian_context:
    "DeMarker on NIFTY daily produces clean reversal signals during pre-event consolidation periods (pre-budget, pre-RBI policy) when the index cycles between support and resistance. During trending months (post-budget rallies, post-COVID recoveries), it stays pinned at extremes and produces few useful signals. BANKNIFTY benefits from raising the threshold to 0.25/0.75 due to higher daily ranges. For F&O equity, DeMarker works well on mid-cap names (Tata Power, IRCTC) that show clear cyclical patterns and less so on large-caps that trend persistently.",
};
