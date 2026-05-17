import type { IndicatorContent } from "./_types";

export const SWING_INDEX: IndicatorContent = {
  slug: "swing-index",
  name: "Swing Index (SI)",
  category: "momentum",
  complexity: "advanced",

  one_liner_en:
    "Welles Wilder's bar-comparison oscillator that quantifies the 'true' strength of each price bar — single-bar input to other Wilder indicators.",
  one_liner_hi:
    "Welles Wilder ka bar-comparison oscillator jo har price bar ki 'true' strength quantify karta — dusre Wilder indicators ka single-bar input.",

  description_en:
    "Welles Wilder (creator of RSI, ADX, ATR) designed the Swing Index to give a single per-bar measurement of momentum strength. It compares the current bar's high, low, and close to the previous bar's, weighted by various range factors. The result tells you whether each bar represents a stronger up-move or down-move compared to the prior bar.\n\nThe Swing Index by itself is rarely traded — its outputs are noisy and bar-specific. Its primary use is as the INPUT to the Accumulative Swing Index (ASI), which sums Swing Index values cumulatively to produce a smoother trendable line.\n\nValues range roughly -100 to +100. Positive = upward swing strength; negative = downward swing strength. Magnitude depends on the bar's range relative to recent ranges, the gap between today's open and yesterday's close, and the directional close.\n\nFor Indian retail, Swing Index has limited direct use. It becomes useful as the building block for the Accumulative Swing Index (covered separately), or as a sanity check ('this bar's SI is strongly positive — confirmation of bullish momentum on this single bar').",
  description_hi:
    "Welles Wilder (RSI, ADX, ATR ke creator) ne Swing Index design kiya momentum strength ka single per-bar measurement dene ke liye. Current bar ka high, low, aur close previous bar ke saath compare karta, various range factors se weighted. Result batata har bar previous bar ke compared mein stronger up-move ya down-move represent karta.\n\nSwing Index khud rarely trade hota — uske outputs noisy aur bar-specific hote. Iska primary use Accumulative Swing Index (ASI) ka INPUT hai, jo Swing Index values cumulatively sum karke smoother trendable line produce karta.\n\nValues roughly -100 se +100 range mein. Positive = upward swing strength; negative = downward swing strength. Magnitude bar ke range, today ka open aur yesterday ka close gap, aur directional close pe depend karta.\n\nIndian retail ke liye Swing Index ka limited direct use hai. Accumulative Swing Index (separately covered) ka building block ke roop mein useful hota, ya sanity check ('is bar ka SI strongly positive — is single bar pe bullish momentum confirmation').",

  formula_explanation:
    "SI = 50 × ((Close[today] - Close[yesterday]) + 0.5 × (Close[today] - Open[today]) + 0.25 × (Close[yesterday] - Open[yesterday])) / R × (K / T). R = max range factor; K = max(|High[today]-Close[yesterday]|, |Low[today]-Close[yesterday]|); T = trading limit value (set per-instrument). Wilder's full formula has multiple conditional branches; modern implementations simplify slightly.",

  default_period: 1,
  period_range: null,
  common_periods: [1],

  use_cases: [
    {
      scenario: "Building block for the Accumulative Swing Index (ASI)",
      what_to_do: "Use Swing Index as the per-bar input to ASI (sum cumulatively)",
      why: "Swing Index alone is too noisy; ASI's cumulative smoothing is what makes the underlying math useful for trading.",
    },
    {
      scenario: "Confirming the 'strength' of a single key bar",
      what_to_do: "On a breakout bar, check Swing Index magnitude — high positive SI confirms genuine breakout strength",
      why: "Compared to just looking at the bar's color/size, SI quantifies strength relative to recent context.",
    },
    {
      scenario: "Filtering false breakouts",
      what_to_do: "Reject breakouts with low absolute Swing Index — the breakout lacks the momentum strength to follow through",
      why: "SI provides a numeric threshold for 'how strong is this single bar' beyond visual inspection.",
    },
  ],

  common_signals: [
    {
      signal: "Strong bullish bar",
      condition: "Swing Index > +50",
      action: "Single-bar bullish strength confirmation; combine with breakout / pattern entry.",
    },
    {
      signal: "Strong bearish bar",
      condition: "Swing Index < -50",
      action: "Single-bar bearish strength confirmation.",
    },
    {
      signal: "Trend continuation",
      condition: "Multiple consecutive positive (or negative) SI bars",
      action: "Sustained momentum; trend trades viable.",
    },
  ],

  pitfalls: [
    "Swing Index alone is noisy — not suitable as a standalone trading signal.",
    "The trading limit (T) parameter varies by instrument; ensure platform implementation uses correct T for NSE F&O.",
    "Gappy stocks distort SI readings because the formula assumes continuous trading.",
    "Default 1-bar lookback means no period parameter — SI is always 'today vs yesterday'.",
    "Don't confuse Swing Index (single-bar) with Accumulative Swing Index (cumulative trend indicator) — different uses.",
  ],

  works_well_with: ["accumulative-swing-index", "atr", "adx"],
  works_poorly_with: ["rsi", "stochastic"],

  example_strategies: [
    "Swing Index breakout confirmation filter",
    "Building block for ASI-based positional trades",
    "Single-bar momentum strength scanner",
  ],

  indian_context:
    "Swing Index direct utility on Indian markets is limited; its primary value is feeding the Accumulative Swing Index calculation. For NIFTY/BANKNIFTY F&O, SI > 50 on a breakout bar is a useful confirmation that the breakout has institutional weight (not retail FOMO). The trading limit T parameter should be calibrated for NSE — most platforms use intraday range max for T which works reasonably. For F&O equity, SI can help distinguish 'strong' green bars from 'lucky' green bars on technical breakouts.",
};
