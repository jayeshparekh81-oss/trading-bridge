import type { IndicatorContent } from "./_types";

export const RELATIVE_VIGOR_INDEX: IndicatorContent = {
  slug: "relative-vigor-index",
  name: "Relative Vigor Index (RVI/RVGI)",
  category: "momentum",
  complexity: "intermediate",

  one_liner_en:
    "Measures conviction in price moves by comparing close-vs-open relative to high-vs-low — high readings mean strong intraday participation.",
  one_liner_hi:
    "Price moves mein conviction measure karta close-vs-open ko high-vs-low ke against compare karke — high readings strong intraday participation matlab.",

  description_en:
    "The Relative Vigor Index reads the strength behind price moves, not just the moves themselves. The core observation: in genuine uptrends, prices tend to close near the bar's high (closing > opening for green candles); in downtrends, prices close near the bar's low. RVI quantifies this 'closing-pressure' across multiple bars and compares it to the bar's range.\n\nThink of it as: 'are buyers actually winning the day, or just nudging price up?'. A 50-point NIFTY move that closes near the day's high reads as high-conviction. The same 50-point move that closes near the day's low (despite ending green) reads as weak — sellers came in late.\n\nRVI is plotted as an oscillator with a signal line (its 4-bar smoothed version). The most-cited signal: RVI crossover above its signal line = bullish; below = bearish. The signal is most reliable when RVI is rising from below zero or falling from above zero.\n\nIndian retail traders often confuse RVI with RSI — but they measure different things. RSI reads price velocity; RVI reads intra-bar conviction. Both can disagree usefully — when price is rising (good RSI) but RVI is weak, the rally has poor underlying support.",
  description_hi:
    "Relative Vigor Index price moves ke peeche ki strength read karta, sirf moves nahi. Core observation: genuine uptrends mein prices bar ke high ke paas close hote (green candles ke liye close > open); downtrends mein bar ke low ke paas close hote. RVI ye 'closing-pressure' multiple bars pe quantify karta aur bar ke range se compare karta.\n\nIsko aise socho: 'buyers actually din jeet rahe ya bas price nudge kar rahe?' 50-point NIFTY move jo day ke high ke paas close ho high-conviction read hota. Same 50-point move jo day ke low ke paas close (green hone ke bawajood) weak read hota — sellers late aaye.\n\nRVI ek oscillator ke roop mein plot hota signal line (uska 4-bar smoothed version) ke saath. Most-cited signal: RVI crossover signal line ke upar = bullish; neeche = bearish. Signal most reliable jab RVI zero se neeche se rising ho ya zero ke upar se falling ho.\n\nIndian retail traders often RVI ko RSI se confuse karte — but ye different cheezein measure karte. RSI price velocity read karta; RVI intra-bar conviction. Dono useful ways mein disagree kar sakte — price rise ho rahi (good RSI) but RVI weak hai, rally ka underlying support poor hai.",

  formula_explanation:
    "Numerator: 4-period SWMA (symmetrically-weighted moving average, 1-2-2-1 weights) of (Close - Open). Denominator: 4-period SWMA of (High - Low). RVI = Numerator / Denominator. Signal Line = 4-period SWMA of RVI. The SWMA smoothing reduces noise vs simple averaging; outputs oscillate roughly between -1 and +1.",

  default_period: 10,
  period_range: [4, 20],
  common_periods: [10, 14],

  use_cases: [
    {
      scenario: "Confirming the conviction behind a breakout",
      what_to_do: "Take breakout entries only when RVI is rising AND above zero",
      why: "Breakouts with rising RVI tend to follow through; breakouts with falling RVI often fail in 1-2 bars.",
    },
    {
      scenario: "Detecting weakening rallies before they reverse",
      what_to_do: "If price keeps rising but RVI is flat or falling, rally is on borrowed time — tighten stops",
      why: "RVI's intra-bar conviction read catches the weakening before price-based oscillators do.",
    },
    {
      scenario: "Bullish divergence at supports",
      what_to_do: "Lower low in price, higher low in RVI at a known support = bullish reversal setup",
      why: "Like RSI divergence but reads conviction (not just velocity); often catches reversals that pure RSI divergence misses.",
    },
  ],

  common_signals: [
    {
      signal: "Bullish signal cross",
      condition: "RVI crosses above its signal line, ideally below zero",
      action: "Long entry candidate with conviction confirmation.",
    },
    {
      signal: "Bearish signal cross",
      condition: "RVI crosses below its signal line, ideally above zero",
      action: "Long exit / short entry candidate.",
    },
    {
      signal: "Bullish divergence",
      condition: "Price lower low, RVI higher low",
      action: "Bullish reversal candidate; confirm with reversal candle.",
    },
    {
      signal: "Conviction fading",
      condition: "RVI declining while price still rising",
      action: "Tighten longs; rally lacks conviction.",
    },
  ],

  pitfalls: [
    "RVI works on daily and 4-hour charts; on 5-min/15-min the SWMA smoothing makes it laggy.",
    "Choppy markets produce many false signal-line crosses; pair with ADX > 20 filter.",
    "RVI looks very similar to a Stochastic on screen — they measure different things, don't conflate.",
    "Around news gaps, the (close - open) component spikes and produces false readings.",
    "The 'conviction' read assumes liquid markets; on small-caps with low volume, RVI loses meaning.",
  ],

  works_well_with: ["adx", "rsi", "macd", "ema"],
  works_poorly_with: ["stochastic", "tsi"],

  example_strategies: [
    "RVI signal cross + ADX filter on NIFTY daily",
    "RVI divergence at S/R levels for swing entries",
    "RVI-confirmed breakout entries on F&O stocks",
  ],

  indian_context:
    "RVI on NIFTY daily reads bullish conviction well during sector rotation periods — when banks lead or IT leads, RVI tends to rise alongside the leading sector's contribution to NIFTY. On expiry days RVI gets distorted by OI-driven closing pressure that doesn't reflect real sentiment — filter out expiry-day RVI readings. For F&O cash equities, RVI works best on RIL, ICICI Bank, INFY where consistent volume and clean intra-bar action give meaningful conviction reads. BANKNIFTY's high beta means RVI swings are larger; adjust signal-cross thresholds accordingly.",
};
