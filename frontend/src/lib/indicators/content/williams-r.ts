import type { IndicatorContent } from "./_types";

export const WILLIAMS_R: IndicatorContent = {
  slug: "williams-r",
  name: "Williams %R",
  category: "momentum",
  complexity: "beginner",

  one_liner_en:
    "An inverted Stochastic, scaled -100 to 0. Above -20 is overbought, below -80 is oversold.",
  one_liner_hi:
    "Inverted Stochastic, scale -100 se 0. -20 ke upar overbought, -80 ke neeche oversold.",

  description_en:
    "Williams %R is the Stochastic Oscillator's older cousin — same idea (close position within recent range) but signed the other way. A reading of -10 means the close is near the recent high (overbought); -90 means near the recent low (oversold). It uses only %R (one line), no smoothing average like Stochastic's %D.\n\nLarry Williams designed it for short-term overbought/oversold detection on individual stocks. Because there's no %D, the indicator is noisier — you read the level itself, not crossovers.\n\nThe classic trade is the failure swing: %R drops below -80, climbs back above -80, fails to reach above -50, then drops below -80 again — that pattern signals continued downside momentum. Mirror inverted for upside.\n\nIn modern Indian retail, Williams %R is less common than RSI or Stochastic, but it remains useful as a third 'tie-breaker' oscillator when RSI and Stochastic disagree.",
  description_hi:
    "Williams %R Stochastic Oscillator ka older cousin hai — same idea (close position within recent range) but signed ulta. Reading of -10 matlab close recent high ke paas (overbought); -90 matlab recent low ke paas (oversold). Sirf %R (ek line) use karta, Stochastic ki tarah %D smoothing nahi.\n\nLarry Williams ne short-term overbought/oversold detection ke liye individual stocks ke liye design kiya tha. %D nahi hai isliye noisier hai — level khud read karte ho, crossovers nahi.\n\nClassic trade hai failure swing: %R -80 ke neeche jaye, wapas -80 ke upar aaye, -50 tak nahi pahunch paaye, phir wapas -80 ke neeche jaye — yeh pattern continued downside momentum signal karta hai. Upside ke liye mirror inverted.\n\nModern Indian retail mein RSI ya Stochastic se kam common hai, but tie-breaker oscillator ki tarah useful hai jab RSI aur Stochastic disagree karein.",

  formula_explanation:
    "%R = -100 × (highest_high(period) - close) / (highest_high(period) - lowest_low(period)). Output range: -100 to 0. Default period: 14. No secondary smoothing line.",

  default_period: 14,
  period_range: [3, 50],
  common_periods: [10, 14, 21],

  use_cases: [
    {
      scenario: "Tie-break when two other oscillators disagree",
      what_to_do: "If RSI and Stochastic give opposite signals, add Williams %R as the third vote",
      why: "Three independent reads of the same overbought/oversold concept reduce single-indicator false reads.",
    },
    {
      scenario: "Failure-swing setup in choppy markets",
      what_to_do: "Watch for the four-step failure-swing pattern at -80 (long) or -20 (short)",
      why: "The pattern is more informative than a single threshold cross because it incorporates the reaction strength.",
    },
  ],

  common_signals: [
    {
      signal: "Overbought rejection",
      condition: "%R crosses below -20 (from above)",
      action: "Long exit / short candidate. Confirm with price action.",
    },
    {
      signal: "Oversold bounce",
      condition: "%R crosses above -80 (from below)",
      action: "Long entry candidate.",
    },
    {
      signal: "Bullish failure swing",
      condition: "%R dips below -80, recovers above -50, dips again but doesn't reach -80",
      action: "Sustained upside momentum — long entry.",
    },
  ],

  pitfalls: [
    "Noisier than RSI; treat single-bar crosses as suggestions, not triggers.",
    "On strong trends, %R can stick near -10 or -90 for many bars — fighting that loses money.",
    "Inverted sign convention confuses beginners — -20 is the 'upper' zone, not lower. Always orient before trading.",
    "Less effective on indices than on single stocks (Williams designed it for stocks).",
  ],

  works_well_with: ["ema", "supertrend", "atr"],
  works_poorly_with: ["rsi", "stochastic", "cci"],

  example_strategies: [
    "Williams %R Failure Swing (daily mid-cap stocks)",
    "%R + EMA Trend Filter (1h NIFTY F&O stocks)",
  ],

  indian_context:
    "On NSE mid-cap and small-cap stocks, Williams %R(14) on the daily catches oversold bounces that RSI sometimes prints too late because of RSI's smoothing. Less useful for indices — NIFTY's lower volatility keeps %R bouncing in mid-range, where the indicator doesn't carry much information. For Bank Nifty futures intraday, %R(9) on 5-min candles is a niche scalper setting; most Indian scalpers prefer Stochastic 5-3-3 for the same job.",
};
