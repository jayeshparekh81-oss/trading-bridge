import type { IndicatorContent } from "./_types";

export const COMPARATIVE_RELATIVE_STRENGTH: IndicatorContent = {
  slug: "comparative-relative-strength",
  name: "Comparative Relative Strength (CRS)",
  category: "trend",
  complexity: "intermediate",

  one_liner_en:
    "Ratio of one instrument's price to another's — identifies relative outperformance, used for sector rotation and pair-trading.",
  one_liner_hi:
    "Ek instrument ke price ka dusre ke ratio — relative outperformance identify karta, sector rotation aur pair-trading mein use hota.",

  description_en:
    "Comparative Relative Strength (CRS, not to be confused with RSI) measures how one instrument is performing relative to another. It's simply: CRS = Price[instrument A] / Price[instrument B]. The resulting line goes UP when A outperforms B, DOWN when B outperforms A. Direction of CRS is direction of OUTperformance — not direction of A's price.\n\nThis is a fundamentally different question from 'is this stock going up?'. CRS asks 'is this stock STRONGER than its benchmark?'. A stock can be falling while CRS rises (it's falling LESS than the benchmark) or rising while CRS falls (rising LESS than the benchmark). Both situations matter for portfolio decisions.\n\nThree common uses: (1) Stock vs Index — compare RELIANCE / NIFTY to see if RIL outperforms; (2) Sector vs Index — compare BANKNIFTY / NIFTY to identify banking sector strength; (3) Cross-stock — compare HDFC / ICICI to determine which to favor in pair trades.\n\nFor Indian retail building positional baskets, CRS is the most useful tool for stock SELECTION (after deciding on direction). 'Buy banks' becomes specific via CRS: pick the bank with rising CRS, not falling.",
  description_hi:
    "Comparative Relative Strength (CRS, RSI se confuse mat karo) measure karta ki ek instrument dusre ke relative kaisa perform kar raha. Bas: CRS = Price[instrument A] / Price[instrument B]. Resulting line UP jaata jab A B se outperform kare, DOWN jab B A se outperform. CRS ki direction OUTperformance ki direction hai — A ke price ki direction nahi.\n\nYe fundamentally different question hai 'ye stock upar ja raha?' se. CRS poochta 'kya ye stock apne benchmark se STRONGER hai?'. Stock fall ho raha aur CRS rise (benchmark se kam fall) ya rise ho raha aur CRS fall (benchmark se kam rise). Dono situations portfolio decisions ke liye matter karte.\n\nTeen common uses: (1) Stock vs Index — RELIANCE / NIFTY compare karke dekho ki RIL outperform karta hai; (2) Sector vs Index — BANKNIFTY / NIFTY compare karke banking sector strength identify; (3) Cross-stock — HDFC / ICICI compare karke decide karo pair trades mein kis ko favor karna.\n\nIndian retail jo positional baskets bana raha, CRS stock SELECTION ke liye most useful tool hai (direction decide karne ke baad). 'Buy banks' CRS se specific ho jaata: rising CRS wala bank pick karo, falling wala nahi.",

  formula_explanation:
    "CRS[today] = Close[A][today] / Close[B][today]. No period parameter. To normalize across different price scales, multiply by 100 / CRS[start_of_period] to express as a 'CRS = 100 at start' ratio that compounds upward when A outperforms. Common modification: take 14-period or 20-period EMA of CRS to smooth the line. Direction of CRS slope is the key signal; absolute CRS value is meaningless without context.",

  default_period: null,
  period_range: null,
  common_periods: [],

  use_cases: [
    {
      scenario: "Sector rotation: identifying leading sectors",
      what_to_do: "Plot CRS of major sector indices (BANKNIFTY/NIFTY, NIFTY IT/NIFTY, NIFTY PHARMA/NIFTY) — buy the leaders",
      why: "Sector rotation is one of the most reliable repeating patterns in Indian markets; CRS quantifies which sector is winning right now.",
    },
    {
      scenario: "Stock selection within a sector",
      what_to_do: "Within banking, compare HDFC/BANKNIFTY, ICICI/BANKNIFTY, SBI/BANKNIFTY — buy the one with rising CRS",
      why: "Even within a winning sector, individual stocks vary; CRS picks the right horse.",
    },
    {
      scenario: "Pair trading setup",
      what_to_do: "Find historically correlated pairs where CRS has diverged from its mean — long the lagger, short the leader",
      why: "Mean-reversion in CRS gives clean pair-trading setups; the directional risk cancels out.",
    },
  ],

  common_signals: [
    {
      signal: "Outperformance starting",
      condition: "CRS turns up from a trough",
      action: "Long entry candidate; the instrument is starting to outperform.",
    },
    {
      signal: "Outperformance fading",
      condition: "CRS turns down from a peak",
      action: "Profit-taking signal on long; switch to a stronger CRS instrument.",
    },
    {
      signal: "Sector leadership",
      condition: "Sector CRS / NIFTY in sustained uptrend",
      action: "Allocate capital to that sector's stocks; relative-strength-rank within sector.",
    },
    {
      signal: "Pair divergence",
      condition: "CRS reaches statistical extreme (e.g., 2σ from mean)",
      action: "Pair trade: long the underperformer, short the outperformer.",
    },
  ],

  pitfalls: [
    "CRS direction doesn't tell you ABSOLUTE direction — both instruments could be falling, CRS rising just means A is falling less.",
    "Pair-trading mean-reversion requires the pair to actually mean-revert; in regime changes, CRS trends without reverting.",
    "Different price scales make raw CRS hard to read — normalize to a starting value (e.g., CRS=100 at start of year).",
    "Be careful with dividend/split-adjusted prices — un-adjusted prices can produce false CRS moves on ex-div days.",
    "Don't compare CRS across unrelated instruments (e.g., gold vs IT stocks) — no economic linkage means CRS movements are noise.",
  ],

  works_well_with: ["ema", "linear-regression", "supports-resistances", "macd"],
  works_poorly_with: ["rsi", "stochastic"],

  example_strategies: [
    "Sector rotation across NIFTY sectoral indices",
    "Stock selection within winning sectors",
    "Pair-trading on historically correlated F&O stocks",
  ],

  indian_context:
    "Comparative Relative Strength is well-suited to Indian retail running sector-rotation strategies. NIFTY's sectoral indices (BANKNIFTY, NIFTY IT, NIFTY PHARMA, NIFTY AUTO, NIFTY METAL) tend to show rotation patterns that can persist for several weeks — measure your own CRS series rather than relying on a fixed cadence claim. For pair trading, commonly cited Indian pairs include HDFC/ICICI, INFY/TCS, M&M/Tata Motors, but correlation and mean-reversion behaviour change over time; back-test the pair on a recent window before sizing. CRS is also useful for index futures decisions: when BANKNIFTY/NIFTY is rising, BANKNIFTY futures' higher beta tends to amplify the directional move on a leveraged basis.",
};
