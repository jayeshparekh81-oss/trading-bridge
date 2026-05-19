import type { IndicatorContent } from "./_types";

export const ACCELERATOR_OSCILLATOR: IndicatorContent = {
  slug: "accelerator-oscillator",
  name: "Accelerator Oscillator (AC)",
  category: "momentum",
  complexity: "intermediate",

  one_liner_en:
    "Measures the rate of momentum change — fires earlier than momentum oscillators by reading acceleration, not velocity.",
  one_liner_hi:
    "Momentum change ki rate measure karta — velocity nahi, acceleration read karke momentum oscillators se earlier fire karta.",

  description_en:
    "The Accelerator Oscillator was created by Bill Williams as part of his trading-chaos toolkit. Its core idea: most momentum indicators read VELOCITY (how fast price is moving). AC reads ACCELERATION (how fast that velocity is changing). Just like a car accelerating, the rate of speedup turns negative BEFORE velocity itself peaks — which means AC reverses BEFORE price momentum reverses.\n\nMechanically, AC subtracts a 5-period SMA from a 5-period median price, then subtracts the 5-SMA of that. The double-difference structure isolates the second derivative of price — pure acceleration.\n\nReadings: AC plots as bars above and below zero. Bars are GREEN when AC is rising and RED when falling. The trading rules use COLOR and POSITION together. Williams' two-bar entry rule: long entry on three consecutive green bars above zero (or two if AC is below zero and turning up). The color-flip is the earlier momentum-shift signal.\n\nFor Indian retail, AC is most useful as a 'momentum is fading even though price is still up' early warning. Its acceleration framing catches the inflection point before price-based oscillators do.",
  description_hi:
    "Accelerator Oscillator Bill Williams ne apne trading-chaos toolkit ka part banaya. Core idea: zyadatar momentum indicators VELOCITY read karte (price kitni tezi se move ho rahi). AC ACCELERATION read karta (wo velocity kitni tezi se change ho rahi). Jaise car accelerate ho rahi, speedup ki rate negative ho jaati velocity peak hone se PEHLE — matlab AC price momentum reverse hone se PEHLE reverse hota.\n\nMechanically, AC 5-period SMA ko 5-period median price se subtract karta, phir us 5-SMA subtract karta. Double-difference structure price ke second derivative ko isolate karta — pure acceleration.\n\nReadings: AC zero ke upar-neeche bars ke roop mein plot hota. AC rising ho to bars GREEN, falling ho to RED. Trading rules COLOR aur POSITION dono use karte. Williams ka two-bar entry rule: long entry teen consecutive green bars zero ke upar (ya do agar AC zero ke neeche aur turning up). Color-flip earlier momentum-shift signal hai.\n\nIndian retail ke liye AC sabse useful 'price abhi up but momentum fade ho raha' early warning ke roop mein hai. Iska acceleration framing inflection point pakadta price-based oscillators se pehle.",

  formula_explanation:
    "Step 1: Awesome Oscillator (AO) = 5-period SMA of median price - 34-period SMA of median price. Step 2: AC = AO - 5-period SMA of AO. The output is the second-derivative-like 'change in change' signal. Median price = (High + Low) / 2.",

  default_period: 5,
  period_range: [3, 8],
  common_periods: [5],

  use_cases: [
    {
      scenario: "Early-warning exit on long positions in extended uptrends",
      what_to_do: "When AC bars turn red while still above zero, tighten stops or take partial profits",
      why: "Acceleration turning negative is a leading indicator of momentum failure; price often follows 2-5 bars later.",
    },
    {
      scenario: "Catching the very start of new trends",
      what_to_do: "AC crosses above zero with rising green bars = early trend entry candidate",
      why: "AC's earliness gives entries before price-based momentum indicators confirm; pairs well with a trend filter.",
    },
    {
      scenario: "Confirming momentum is genuinely fading (not just consolidating)",
      what_to_do: "If AC color stays green but bars are shrinking, momentum is decelerating but not yet reversing — hold longs cautiously",
      why: "Subtle distinction between 'pause' and 'reversal' — AC color-and-size combined reads it.",
    },
  ],

  common_signals: [
    {
      signal: "Williams long entry (above zero)",
      condition: "AC above zero with 3 consecutive green bars",
      action: "Long entry candidate with strong acceleration.",
    },
    {
      signal: "Williams long entry (below zero)",
      condition: "AC below zero with 2 consecutive green bars (turning up)",
      action: "Long entry candidate; counter-trend setup with early reversal risk.",
    },
    {
      signal: "Color flip warning",
      condition: "Green bars flip to red while AC still above zero",
      action: "Acceleration fading — tighten longs, prepare for momentum exhaustion.",
    },
  ],

  pitfalls: [
    "AC is noisy on lower timeframes — most useful on 1h, daily, weekly.",
    "False signals around major news events distort the acceleration math.",
    "The color-flip alone is not an exit — combine with price action confirmation.",
    "Williams' specific bar-count entry rules are mechanical; some traders prefer slightly more discretionary use.",
    "AC requires both AO and AC to be visible — without seeing AO, the AC reading lacks context.",
  ],

  works_well_with: ["awesome-oscillator", "adx", "ema", "supertrend"],
  works_poorly_with: ["roc", "macd"],

  example_strategies: [
    "Williams' AC + AO momentum entry on NIFTY hourly",
    "Acceleration-fade exit overlay on EMA crossover longs",
    "Early trend catcher on F&O daily charts",
  ],

  indian_context:
    "AC on NIFTY hourly during trend days catches momentum exhaustion 1-3 bars before VWAP-based exits do — useful for intraday F&O traders managing partial profit-taking. BANKNIFTY's higher beta means AC swings are larger and more reliable signals. During expiry week, AC produces too many color flips due to OI-driven volatility; use with caution. For cash equity day-trading, AC works best on liquid mid-caps where the second-derivative math has enough data depth to be meaningful.",
};
