import type { IndicatorContent } from "./_types";

export const ADX: IndicatorContent = {
  slug: "adx",
  name: "ADX (Average Directional Index)",
  category: "trend",
  complexity: "intermediate",

  one_liner_en:
    "Measures trend STRENGTH (not direction) on a 0-100 scale. Above 25 = trend present, above 40 = strong trend.",
  one_liner_hi:
    "Trend ki STRENGTH measure karta hai (direction nahi) 0-100 scale pe. 25 ke upar trend hai, 40 ke upar strong trend.",

  description_en:
    "ADX answers ONE question: 'is the market trending or ranging right now?' It does NOT tell you the direction — for that you need its siblings DI+ and DI- (the Directional Indicator pair, see DMI).\n\nA reading below 20 means the market is in chop / range — trend-following strategies will whipsaw. 20-40 means a trend is developing or active — most trend-following setups work here. Above 40 means a strong trend — trend-continuation entries are higher probability, mean-reversion entries are dangerous. Above 60 is unusual and often marks late-trend exhaustion.\n\nThe practical use is as a filter on top of other strategies. Take a moving-average crossover system: it shreds in chop. Add a rule 'only enter when ADX > 25' and the same crossover system suddenly has fewer trades and better win rate.\n\nADX rises during trends and falls during chop. The rise/fall of ADX itself is also informative — ADX rising while in a downtrend means the downtrend is accelerating, not exhausting.",
  description_hi:
    "ADX ek hi question ka jawab deta hai: 'market trending hai ya ranging?' Direction NAHI batata — uske liye iske siblings DI+ aur DI- chahiye (DMI dekho).\n\n20 ke neeche matlab market chop / range mein hai — trend-following strategies whipsaw karengi. 20-40 matlab trend develop ho raha ya active hai — most trend-following setups yahan kaam karte hain. 40 ke upar strong trend — trend-continuation entries higher probability, mean-reversion dangerous. 60 ke upar unusual aur often late-trend exhaustion mark karta hai.\n\nPractical use other strategies ke upar filter ki tarah hai. Ek moving-average crossover system lo: chop mein shred hota hai. Rule add karo 'only enter when ADX > 25' aur wahi system suddenly fewer trades aur better win rate ke saath chalta hai.\n\nADX trends mein rise karta aur chop mein fall karta. ADX ka khud ka rise/fall bhi informative hai — ADX rising while in downtrend matlab downtrend accelerating hai, exhaust nahi ho raha.",

  formula_explanation:
    "Compute DI+ and DI- from upward/downward directional movement (see DMI). DX = 100 × |DI+ - DI-| / (DI+ + DI-). ADX = Wilder's smoothed moving average of DX over `period` bars. Default period: 14. Output bounded 0-100.",

  default_period: 14,
  period_range: [5, 50],
  common_periods: [10, 14, 20],

  use_cases: [
    {
      scenario: "Trend filter on top of crossover strategies",
      what_to_do: "Only fire EMA / MACD / SAR crossover signals when ADX > 20",
      why: "Eliminates ~60% of false crossover signals that happen during chop — single biggest reliability improvement for trend-following systems.",
    },
    {
      scenario: "Confirmation of strong-move continuation",
      what_to_do: "If ADX > 40 and rising, hold trend positions longer; don't take profit early",
      why: "Strong rising ADX means the trend has momentum. Early profit-taking leaves money on the table.",
    },
    {
      scenario: "Stand-aside signal when chop is obvious",
      what_to_do: "If ADX < 20 for many bars, skip the day for trend-following; consider mean-reversion or sit out",
      why: "Forcing trades in chop is the #1 way trend systems destroy edge. ADX makes the chop visible.",
    },
  ],

  common_signals: [
    {
      signal: "Trend confirmation",
      condition: "ADX crosses above 25 (and is rising)",
      action: "Trend regime active — enable trend-following strategies.",
    },
    {
      signal: "Chop warning",
      condition: "ADX falls below 20",
      action: "Disable trend-following strategies — pause or switch to mean-reversion.",
    },
    {
      signal: "Trend exhaustion",
      condition: "ADX peaks above 40 then starts falling",
      action: "Tighten stops, scale out — the trend is losing strength even if price keeps moving.",
    },
  ],

  pitfalls: [
    "ADX is direction-AGNOSTIC. A high ADX could mean a strong uptrend OR a strong downtrend. Never enter long just because ADX is high — check DI+/DI- or price action.",
    "Lags by design. ADX confirms trends; it doesn't predict them. Early in a trend ADX is still <20 — you might miss the first leg.",
    "Short periods (<10) make ADX twitchy and produce false trend confirmations. 14 is the conservative standard.",
    "ADX doesn't model volatility regimes. A high-vol chop day can look superficially like a trend by some signals — ADX correctly stays low through it.",
    "On low-volume sessions, ADX values become unreliable as the directional-movement components flatten.",
  ],

  works_well_with: ["ema", "macd", "supertrend", "rsi"],
  works_poorly_with: ["bollinger-bands", "stochastic"],

  example_strategies: [
    "ADX-Filtered EMA Crossover (daily F&O)",
    "ADX > 25 Momentum Breakout (15m BANKNIFTY)",
    "ADX-Threshold Strategy Selector",
  ],

  indian_context:
    "On NIFTY daily, ADX hovers 15-25 most of the time — Indian indices have many low-trend periods. ADX > 30 days on NIFTY are notable; > 40 days are usually post-budget / post-major-policy moves. BANKNIFTY has higher average ADX than NIFTY due to higher beta. For F&O stocks during earnings season, ADX often spikes from the announcement day onward — use ADX > 25 as a quantitative confirmation that the earnings move 'has legs' rather than fading.",
};
