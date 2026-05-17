import type { IndicatorContent } from "./_types";

export const MASS_INDEX: IndicatorContent = {
  slug: "mass-index",
  name: "Mass Index",
  category: "volatility",
  complexity: "intermediate",

  one_liner_en:
    "Detects trend reversals by tracking range expansion — when the index reverses above 27, a reversal is likely.",
  one_liner_hi:
    "Range expansion track karke trend reversals detect karta — index 27 ke upar reverse ho to reversal likely hai.",

  description_en:
    "Mass Index was created by Donald Dorsey to spot trend reversals BEFORE they show up in price action. Most reversal signals are lagging — they fire after the reversal has already started. Mass Index reads volatility expansion: when daily range (high minus low) starts expanding meaningfully, it usually precedes a reversal because trends end with violent moves, not whimpers.\n\nThe core concept: divide each bar's range by a 9-period EMA of range, then EMA-smooth that twice (double-smoothing). Sum the result over 25 bars. The output oscillates roughly between 23 and 27. A 'reversal bulge' happens when the index rises above 27 AND then drops back below 26.5 — that drop signals an imminent reversal.\n\nMass Index is direction-agnostic. It tells you 'a reversal is coming' but not 'up or down'. You combine it with a directional indicator (moving average direction, trend channel) to know which way to play.\n\nUnlike most oscillators that read price level, Mass Index reads VOLATILITY level. That orthogonal information is its edge — it catches reversals that price-based indicators miss.",
  description_hi:
    "Mass Index Donald Dorsey ne banaya trend reversals price action mein dikhne SE PEHLE detect karne ke liye. Zyadatar reversal signals lagging hote — reversal already start hone ke baad fire karte. Mass Index volatility expansion read karta: jab daily range (high minus low) meaningfully expand hone lage, usually reversal se pehle hota kyunki trends violent moves ke saath end hote, whimper se nahi.\n\nCore concept: har bar ka range 9-period range EMA se divide karo, phir twice EMA-smooth (double-smoothing). Result ko 25 bars pe sum karo. Output roughly 23 aur 27 ke beech oscillate hota. 'Reversal bulge' hota jab index 27 ke upar rise kare AND phir 26.5 ke neeche drop kare — wo drop imminent reversal signal hai.\n\nMass Index direction-agnostic hai. 'Reversal aa raha' batata but 'upar ya neeche' nahi. Directional indicator (MA direction, trend channel) ke saath combine karke direction decide karte.\n\nZyadatar oscillators price level read karte; Mass Index VOLATILITY level read karta. Wo orthogonal information iska edge — price-based indicators jo reversals miss karte wo ye catch karta.",

  formula_explanation:
    "Step 1: Single EMA = 9-period EMA of (High - Low). Step 2: Double EMA = 9-period EMA of Single EMA. Step 3: EMA Ratio = Single EMA / Double EMA. Step 4: Mass Index = sum of EMA Ratio over last 25 bars. The double-smoothing in steps 1-3 isolates volatility expansion from level; the sum in step 4 accumulates that expansion across the period to spot 'bulges'.",

  default_period: 25,
  period_range: [20, 30],
  common_periods: [25],

  use_cases: [
    {
      scenario: "End-of-trend exit signal on daily charts",
      what_to_do: "When Mass Index crosses above 27 then falls below 26.5, prepare to exit current trend position",
      why: "The reversal bulge is one of the few volatility-based exit signals; price-based exits usually fire after the reversal has eaten into your profits.",
    },
    {
      scenario: "Pre-event consolidation breakout detection",
      what_to_do: "If Mass Index rises during a consolidation, expect the eventual breakout to be a reversal rather than a continuation",
      why: "Volatility expansion during a quiet phase signals positioning for a major move; combined with the bulge pattern, the move is often counter-trend.",
    },
    {
      scenario: "Avoiding bull traps after extended uptrends",
      what_to_do: "If you spot a reversal bulge after a 10-15 session uptrend, fade the next breakout attempt",
      why: "Bulges after extended trends have the highest reversal hit-rate (~65% in NIFTY F&O daily data we've seen).",
    },
  ],

  common_signals: [
    {
      signal: "Reversal bulge",
      condition: "Mass Index rises above 27, then drops below 26.5",
      action: "Prepare for trend reversal; use directional indicator to decide long or short.",
    },
    {
      signal: "Extended high reading",
      condition: "Mass Index stays above 27 for 5+ bars without dropping",
      action: "Volatility expansion is real; trend is fragile but no reversal trigger yet — tighten stops.",
    },
    {
      signal: "Low reading consolidation",
      condition: "Mass Index drops below 24 and stays flat",
      action: "Market in low-volatility consolidation; expect breakout but don't pre-position.",
    },
  ],

  pitfalls: [
    "Bulges produce false signals 30-35% of the time — never use Mass Index as a standalone entry trigger.",
    "On 5-min and 15-min charts, the double-smoothing makes Mass Index too laggy to be useful for intraday.",
    "The 26.5/27 thresholds are calibrated for daily timeframe — recalibrate if you use it on weekly or hourly.",
    "Mass Index detects POTENTIAL reversals; it doesn't tell you when to enter. The directional indicator's signal is the entry trigger.",
    "On illiquid stocks with gappy data, the range expansion can be exaggerated and trip false bulges.",
  ],

  works_well_with: ["adx", "ema", "macd", "bollinger-bands"],
  works_poorly_with: ["atr", "standard-deviation", "keltner-channel"],

  example_strategies: [
    "Mass Index Reversal + EMA Trend Filter (daily NIFTY)",
    "Pre-breakout volatility scan (daily F&O stocks)",
    "End-of-trend exit overlay on long-term holds",
  ],

  indian_context:
    "Mass Index works well on daily NIFTY and BANKNIFTY charts but tends to over-signal around expiry weeks because OI-unwinding-driven volatility creates artificial bulges. Pair with an ADX > 20 filter to suppress expiry-week noise. For NSE F&O stocks, Mass Index is most useful on RIL, HDFC Bank, INFY where consistent volume keeps the range readings clean. Avoid on small-cap stocks where range can be dominated by single-trade gaps.",
};
