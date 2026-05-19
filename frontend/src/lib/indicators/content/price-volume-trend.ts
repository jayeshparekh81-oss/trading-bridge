import type { IndicatorContent } from "./_types";

export const PRICE_VOLUME_TREND: IndicatorContent = {
  slug: "price-volume-trend",
  name: "Price Volume Trend (PVT)",
  category: "volume",
  complexity: "intermediate",

  one_liner_en:
    "Volume-flow indicator that weights each bar's volume by its percentage price change — more sensitive than OBV.",
  one_liner_hi:
    "Volume-flow indicator jo har bar ka volume uske percentage price change se weight karta — OBV se more sensitive.",

  description_en:
    "Price Volume Trend (PVT) is similar in spirit to On-Balance Volume but uses a more nuanced calculation: instead of adding the entire bar's volume to a running total (OBV's approach), PVT adds a fraction of volume proportional to the bar's percentage price change. A 2% up-move with 1 lakh volume contributes 2,000 to PVT; a 0.2% up-move contributes only 200.\n\nThis weighting solves OBV's biggest blind spot: OBV treats a 0.1% up-bar the same as a 5% up-bar, which is clearly wrong. PVT correctly weights bigger moves more. The cumulative line that results responds more proportionally to real conviction shifts.\n\nThe interpretation rules are similar to OBV: rising PVT alongside rising price confirms the trend; PVT failing to make new highs while price does = bearish divergence; PVT rising while price falls = bullish divergence.\n\nFor Indian retail, PVT is preferred over OBV on stocks with frequent small-move bars because OBV's binary treatment loses information. On stocks that make big moves with light volume on small-move days, PVT gives a cleaner picture of where conviction lies.",
  description_hi:
    "Price Volume Trend (PVT) On-Balance Volume jaisi spirit mein hai but more nuanced calculation use karta: pure bar ka volume running total mein add karne ke bajaye (OBV ka approach), PVT volume ka ek fraction add karta jo bar ke percentage price change ke proportional hota. 2% up-move 1 lakh volume ke saath PVT mein 2,000 contribute karta; 0.2% up-move sirf 200.\n\nIs weighting se OBV ka biggest blind spot solve hota: OBV 0.1% up-bar ko 5% up-bar ke same treat karta, jo clearly wrong hai. PVT correctly bigger moves ko more weight karta. Resulting cumulative line real conviction shifts pe zyada proportionally respond karti.\n\nInterpretation rules OBV ke similar: rising PVT alongside rising price trend confirm karta; PVT new highs nahi banata price banati = bearish divergence; PVT rise ho rahi price fall ho rahi = bullish divergence.\n\nIndian retail ke liye PVT OBV se preferred hai un stocks pe jo frequent small-move bars karte kyunki OBV ka binary treatment information lose karta. Jo stocks bigger moves big volume pe karte aur small-move days pe light volume — PVT cleaner picture deta where conviction lies.",

  formula_explanation:
    "Step 1: Percentage change = (Close[today] - Close[yesterday]) / Close[yesterday]. Step 2: Volume contribution = Volume[today] × Percentage change. Step 3: PVT[today] = PVT[yesterday] + Volume contribution. No period parameter — PVT is cumulative from inception. Common modification: apply a 14-period EMA to smooth the line for clearer trend reads.",

  default_period: null,
  period_range: null,
  common_periods: [],

  use_cases: [
    {
      scenario: "Detecting subtle accumulation/distribution that OBV misses",
      what_to_do: "When OBV is flat but PVT is trending, the percentage-weighted reading is showing what binary OBV misses",
      why: "PVT's proportional weighting catches conviction in stocks that make many small moves with varying volume.",
    },
    {
      scenario: "Divergence confirmation at key price levels",
      what_to_do: "Use PVT divergence (price higher high, PVT lower high) at known resistance for short setups",
      why: "Volume-weighted divergence at structural levels has higher reliability than at random levels.",
    },
    {
      scenario: "Distinguishing accumulation from retail FOMO",
      what_to_do: "If PVT is rising slowly but price has a sudden spike, the spike is retail FOMO not institutional accumulation",
      why: "Institutional accumulation shows as steady PVT growth; FOMO shows as price spikes without proportional PVT rise.",
    },
  ],

  common_signals: [
    {
      signal: "Trend confirmation",
      condition: "PVT and price both rising in lockstep",
      action: "Hold longs; momentum is genuine.",
    },
    {
      signal: "Bearish divergence",
      condition: "Price higher high, PVT lower high",
      action: "Tighten longs / consider short.",
    },
    {
      signal: "Bullish divergence",
      condition: "Price lower low, PVT higher low",
      action: "Long entry candidate at support.",
    },
    {
      signal: "Accumulation phase",
      condition: "Price sideways, PVT trending up",
      action: "Bullish positional setup forming.",
    },
  ],

  pitfalls: [
    "Like all cumulative indicators, absolute PVT value is meaningless; only direction and divergence matter.",
    "Gap-heavy stocks distort the percentage-change calculation on gap days.",
    "On illiquid small-caps, single trades can produce big PVT swings — limit use to liquid F&O names.",
    "PVT divergence can persist for many bars before resolving — it's a heads-up, not a precise entry trigger.",
    "Don't compare PVT values across different stocks; only its trend within a single stock matters.",
  ],

  works_well_with: ["obv", "mfi", "rsi", "supports-resistances"],
  works_poorly_with: ["volume-profile"],

  example_strategies: [
    "PVT divergence reversal trading on NIFTY F&O cash equity",
    "PVT-confirmed pullback entry on trending stocks",
    "Accumulation scanner using PVT across NIFTY 100",
  ],

  indian_context:
    "PVT on NIFTY F&O cash equities — especially RIL, HDFC Bank, INFY, TCS — gives a cleaner read of institutional positioning than OBV because these stocks have many small-move days alongside occasional big-move days. During FII inflow weeks (typically when DXY weakens or India's bond yields fall), PVT often turns positive across large-cap pharma and IT names 1-2 weeks before price confirms. Avoid PVT on NIFTY/BANKNIFTY futures themselves — hedging volume distorts percentage-weighted reads. For mid-cap F&O, PVT works on Tata Steel and JSW Steel where commodity-cycle moves show clean accumulation patterns.",
};
