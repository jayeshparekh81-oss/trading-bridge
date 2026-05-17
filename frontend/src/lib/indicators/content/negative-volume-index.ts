import type { IndicatorContent } from "./_types";

export const NEGATIVE_VOLUME_INDEX: IndicatorContent = {
  slug: "negative-volume-index",
  name: "NVI (Negative Volume Index)",
  category: "volume",
  complexity: "advanced",

  one_liner_en:
    "Cumulative line that only updates on low-volume (down-volume) days. Theory: tracks 'smart money' that buys quietly.",
  one_liner_hi:
    "Cumulative line jo sirf low-volume (down-volume) days pe update hoti. Theory: 'smart money' track karta jo quietly buy karta.",

  description_en:
    "NVI (Paul Dysart 1936, popularised by Norman Fosback) is built on a contrarian hypothesis: 'smart money' (institutions) trades on QUIET days when retail isn't moving the tape; retail 'dumb money' trades on noisy high-volume days. Therefore tracking what price does on LOW-volume days reveals what informed traders are doing.\n\nMechanics: NVI starts at 1000 (arbitrary). Each bar where today's volume < yesterday's volume: NVI updates by today's percent price change. On bars where volume INCREASED (the noisy retail bars), NVI stays UNCHANGED.\n\nThe canonical read: NVI above its 255-day (1-year) EMA is a strong bull-regime signal — smart money has been net buying on quiet days. Fosback's research showed >95% probability of a bull market when this condition holds, historically.\n\nWorks well for long-term positional / investment-style decisions. Useless for intraday because the volume-comparison resolution is too coarse.",
  description_hi:
    "NVI (Paul Dysart 1936, Norman Fosback ne popularise kiya) contrarian hypothesis pe built: 'smart money' (institutions) QUIET days pe trade karta jab retail tape nahi move kar raha; retail 'dumb money' noisy high-volume days pe trade karta. Therefore LOW-volume days pe price kya karta usse pata chalta informed traders kya kar rahe.\n\nMechanics: NVI 1000 pe start (arbitrary). Har bar jahan today's volume < yesterday's volume: NVI today's percent price change se update. Volume INCREASED wale bars pe (noisy retail bars), NVI UNCHANGED rehta.\n\nCanonical read: NVI apni 255-day (1-year) EMA ke upar = strong bull-regime signal — smart money quiet days pe net buying kar raha. Fosback ki research ne >95% probability bull market dikhayi historically jab yeh condition hold.\n\nLong-term positional / investment-style decisions ke liye well kaam karta. Intraday ke liye useless kyunki volume-comparison resolution too coarse.",

  formula_explanation:
    "NVI[0] = 1000 (seed). For each subsequent bar: if volume[i] < volume[i-1]: NVI[i] = NVI[i-1] × (1 + (close[i] - close[i-1]) / close[i-1]). Else: NVI[i] = NVI[i-1]. Output unbounded, anchored at 1000.",

  default_period: null,
  period_range: null,
  common_periods: [],

  use_cases: [
    {
      scenario: "Long-term bull-regime detector",
      what_to_do: "Long-only on indices when daily NVI > NVI's 255-day EMA",
      why: "Fosback's >95% historical bull-market probability when this holds. Slow-moving filter for long-term positional / SIP-style decisions.",
    },
    {
      scenario: "Sector-rotation read",
      what_to_do: "On weekly sector index data, compute NVI for each sector. Rotating leadership = NVI flipping from below-EMA to above-EMA",
      why: "Smart-money sector rotation often shows up in NVI before broad price acceleration.",
    },
  ],

  common_signals: [
    {
      signal: "NVI > 255-day EMA",
      condition: "NVI crosses above its 1-year EMA",
      action: "Long-term bull regime activated — favour long-only strategies.",
    },
    {
      signal: "NVI flat for many weeks",
      condition: "NVI hasn't updated meaningfully (volume keeps rising bar-after-bar)",
      action: "Distribution / retail-dominated regime — caution.",
    },
  ],

  pitfalls: [
    "Slow. NVI's signal frequency is months, not days. Useless for active trading.",
    "Volume comparison only — doesn't factor in magnitude. A 0.01% volume drop counts the same as a 50% drop.",
    "Historical 95%-probability figures are US-equity-data-derived. Indian market data may produce different probabilities.",
    "Anchored to an arbitrary 1000 seed; absolute values aren't comparable across symbols or time periods.",
  ],

  works_well_with: ["positive-volume-index", "ema", "obv"],
  works_poorly_with: ["volume-spike", "vwap"],

  example_strategies: [
    "NVI Bull-Regime Filter (monthly NIFTY-50 SIP)",
    "NVI + PVI Confluence (positional long-only)",
  ],

  indian_context:
    "NVI on weekly NIFTY data is a slow but reliable bull-regime detector for SIP-style investors who want quantitative confirmation that 'smart money' is participating. On individual NSE F&O stocks, NVI's slow cadence makes it less useful — daily-trader audiences typically prefer faster signals like Force Index or MFI. Most useful in conjunction with PVI to confirm both 'smart' and 'dumb' money are aligned bullish.",
};
