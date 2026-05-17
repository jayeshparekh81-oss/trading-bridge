import type { IndicatorContent } from "./_types";

export const MFI: IndicatorContent = {
  slug: "mfi",
  name: "MFI (Money Flow Index)",
  category: "volume",
  complexity: "intermediate",

  one_liner_en:
    "Volume-weighted RSI. 0-100 scale, 80/20 extremes. RSI's same logic but factoring in trade size.",
  one_liner_hi:
    "Volume-weighted RSI. 0-100 scale, 80/20 extremes. RSI ki same logic but trade size factor karte hue.",

  description_en:
    "MFI is RSI's volume-aware cousin. Instead of comparing raw up-move vs down-move price changes (RSI), MFI compares 'positive money flow' (typical price × volume on up days) to 'negative money flow' (same on down days). Output is bounded 0-100 like RSI, with conventional overbought/oversold lines at 80/20 (slightly tighter than RSI's 70/30 because MFI tends to print more conservative extremes).\n\nWhy volume-weighting matters: a 1% up-move on 3× average volume signals stronger buying than a 1% up-move on quiet volume. RSI treats them identically; MFI treats the volume-heavy day as more bullish. On individual stocks especially, this distinction picks up institutional flow that price-only oscillators miss.\n\nThe trade patterns mirror RSI: overbought/oversold crosses, divergences with price, centerline (50) cross as bias filter. Divergences carry more weight on MFI than on RSI because the indicator is bringing in independent information (volume) — a price-MFI divergence implies volume isn't following price.",
  description_hi:
    "MFI RSI ka volume-aware cousin hai. Raw up-move vs down-move price changes (RSI) compare karne ke bajaye, MFI 'positive money flow' (up days pe typical price × volume) ko 'negative money flow' (down days pe same) se compare karta. Output RSI ki tarah 0-100 bounded, conventional overbought/oversold lines 80/20 (RSI ke 70/30 se thoda tighter kyunki MFI conservative extremes print karta).\n\nVolume-weighting kyun matter karta: 1% up-move 3× average volume pe quiet volume ke 1% up-move se zyada strong buying signal hai. RSI dono ko identically treat karta; MFI volume-heavy day ko zyada bullish treat karta. Individual stocks pe especially, yeh distinction institutional flow pick karti hai jo price-only oscillators miss karte.\n\nTrade patterns RSI ko mirror karte hain: overbought/oversold crosses, price ke saath divergences, centerline (50) cross bias filter ki tarah. Divergences MFI pe RSI se zyada weight carry karte hain kyunki indicator independent information (volume) la raha — price-MFI divergence imply karta volume price ko follow nahi kar raha.",

  formula_explanation:
    "Typical price = (high + low + close) / 3. Money flow = typical_price × volume. Positive flow = sum of money flows on bars where typical_price > prev typical_price; negative flow = sum on bars where typical_price < prev. Money Ratio = positive / negative. MFI = 100 - 100 / (1 + Money Ratio). Default period: 14.",

  default_period: 14,
  period_range: [3, 50],
  common_periods: [10, 14, 21],

  use_cases: [
    {
      scenario: "Volume-confirmed mean reversion",
      what_to_do: "Long when MFI crosses up through 20 (not just RSI through 30) — confirms low-volume capitulation rather than quiet drift",
      why: "MFI < 20 with bottoming price is statistically a higher-conviction long than RSI < 30 alone — institutional flow is exhausting on the sell side.",
    },
    {
      scenario: "Divergence at key resistance",
      what_to_do: "At a major resistance test, look for bearish MFI divergence (price new high, MFI lower high)",
      why: "Bearish MFI divergence = price extends without volume support = institutional buyers are absent = high-conviction reversal setup.",
    },
    {
      scenario: "Volume confirmation of breakouts",
      what_to_do: "When price breaks resistance, require MFI > 60 simultaneously",
      why: "Confirms the breakout has volume behind it — filters most fake-out moves that fail within a few bars.",
    },
  ],

  common_signals: [
    {
      signal: "Oversold bounce",
      condition: "MFI crosses up through 20",
      action: "Long entry candidate — volume-confirmed.",
    },
    {
      signal: "Overbought rejection",
      condition: "MFI crosses down through 80",
      action: "Long exit / short candidate.",
    },
    {
      signal: "Bearish MFI divergence",
      condition: "Price new high, MFI lower high",
      action: "Strong reversal warning — distribution likely.",
    },
    {
      signal: "Bullish MFI divergence",
      condition: "Price new low, MFI higher low",
      action: "Accumulation underway — reversal long candidate.",
    },
  ],

  pitfalls: [
    "Volume data quality matters. On illiquid stocks, sparse or unreliable volume makes MFI noisy.",
    "Strong trends pin MFI at 80+ or 20- for many bars (same as RSI behavior).",
    "On NSE intraday, MFI's first 15-min readings are dominated by retail volume — institutional-flow interpretation kicks in after 10:00 IST.",
    "Different libraries occasionally include / exclude the equal-price-bar case (typical_price unchanged) — minor numerical differences.",
    "MFI and OBV both use volume but differently — they sometimes disagree. Use OBV for trend confirmation, MFI for overbought/oversold.",
  ],

  works_well_with: ["rsi", "vwap", "macd", "ema"],
  works_poorly_with: ["stochastic", "williams-r", "cci"],

  example_strategies: [
    "MFI Oversold Bounce with Volume (1h F&O stocks)",
    "MFI Divergence at Resistance (daily NIFTY-50)",
    "MFI-Confirmed Breakout (15m BANKNIFTY)",
  ],

  indian_context:
    "MFI is the go-to oscillator for Indian swing traders on individual NSE F&O stocks — the volume-awareness picks up institutional accumulation/distribution that price-only RSI misses. On large-cap names (Reliance, HDFC Bank, TCS), MFI(14) on the daily has historically caught earnings-driven reversal setups 1-2 sessions earlier than RSI. On index futures, MFI is less differentiated from RSI because index volume is so aggregated that the volume signal is diluted — for NIFTY / BANKNIFTY intraday, RSI is the typical default; for stocks, MFI.",
};
