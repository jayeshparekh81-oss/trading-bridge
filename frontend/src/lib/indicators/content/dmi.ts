import type { IndicatorContent } from "./_types";

export const DMI: IndicatorContent = {
  slug: "dmi",
  name: "DMI (Directional Movement Index)",
  category: "trend",
  complexity: "intermediate",

  one_liner_en:
    "Two lines (DI+ and DI-) that show which side has directional momentum. Paired with ADX as the trend-direction half of Wilder's system.",
  one_liner_hi:
    "Do lines (DI+ aur DI-) jo dikhati hain konsi side mein directional momentum hai. ADX ke saath paired hota hai — trend-direction half hai Wilder ke system ka.",

  description_en:
    "DMI is the direction half of Wilder's two-indicator package; ADX is the strength half (same author, same paper). DI+ measures upward directional movement strength; DI- measures downward. When DI+ is above DI-, the prevailing direction is up; when DI- is above DI+, down.\n\nThe classic trade is the DI cross: DI+ crosses above DI- = bullish bias, opposite = bearish bias. But DI crosses alone are notoriously noisy in chop. The standard pro recipe is to ALSO require ADX > 25 — only take DI-cross signals when the trend-strength side confirms a trend is present.\n\nDI+ and DI- are individually bounded 0-100 like ADX, but they usually live in the 10-40 range. The 'spread' between them (DI+ minus DI-) is what matters more than absolute values.\n\nMost charting tools show all three lines (DI+, DI-, ADX) together — that's the textbook DMI chart. Reading 'DMI' loosely often means 'DI+/DI- pair without the ADX line', but strictly it's the full three-line package.",
  description_hi:
    "DMI Wilder ke two-indicator package ka direction half hai; ADX strength half hai (same author, same paper). DI+ upward directional movement strength measure karta; DI- downward. DI+ DI- ke upar hai = prevailing direction up; DI- DI+ ke upar = down.\n\nClassic trade DI cross hai: DI+ DI- ke upar cross kare = bullish bias, ulta = bearish. But DI crosses akele chop mein notoriously noisy hote hain. Standard pro recipe: bhi require karo ADX > 25 — DI-cross signals tabhi lo jab trend-strength side trend confirm kare.\n\nDI+ aur DI- individually 0-100 bounded hain ADX ki tarah, but usually 10-40 range mein rehte hain. 'Spread' between them (DI+ minus DI-) absolute values se zyada matter karta hai.\n\nMost charting tools teen lines saath dikhate hain (DI+, DI-, ADX) — textbook DMI chart yahi hai. 'DMI' loosely use karne pe often 'DI+/DI- pair bina ADX' matlab hota hai, but strictly poora three-line package hai.",

  formula_explanation:
    "Directional Movement (DM+): today's high - yesterday's high, when positive AND larger than (yesterday's low - today's low). DM-: mirror. Smooth DM+/- via Wilder's recursive average over `period`. DI+ = 100 × smoothed_DM+ / smoothed_TR. DI- = 100 × smoothed_DM- / smoothed_TR. Default period: 14.",

  default_period: 14,
  period_range: [5, 50],
  common_periods: [10, 14, 20],

  use_cases: [
    {
      scenario: "Trend-direction filter for momentum strategies",
      what_to_do: "Only take longs when DI+ > DI- AND ADX > 25",
      why: "Two-condition gate eliminates most counter-trend longs while preserving setups that have both direction + strength.",
    },
    {
      scenario: "DI-cross entry trigger with ADX confirmation",
      what_to_do: "Enter on DI+ crossing above DI-, but only if ADX is already above 20",
      why: "DI cross alone is noisy; pairing with ADX gates filters out most chop-induced false crosses.",
    },
  ],

  common_signals: [
    {
      signal: "Bullish DI cross",
      condition: "DI+ crosses above DI-",
      action: "Long entry candidate (confirm with ADX > 20).",
    },
    {
      signal: "Bearish DI cross",
      condition: "DI- crosses above DI+",
      action: "Exit longs / short candidate (confirm with ADX > 20).",
    },
    {
      signal: "DI spread expanding",
      condition: "DI+ pulling away from DI- (or vice versa)",
      action: "Trend strengthening on the current side — hold positions.",
    },
  ],

  pitfalls: [
    "DI crosses without ADX confirmation are notoriously unreliable. The 'DMI strategy without ADX' is the most common reason traders blow up on this indicator.",
    "Default period 14 lags noticeably. Faster periods amplify noise; the trade-off is hard.",
    "DI+ and DI- can both be flat and crossing near each other in chop — those crosses mean nothing.",
    "Loose terminology: 'DMI' sometimes means just DI+/DI-, sometimes means the full three-line ADX+DI package. Be precise when reading other people's analysis.",
  ],

  works_well_with: ["adx", "ema", "supertrend", "atr"],
  works_poorly_with: ["rsi", "stochastic"],

  example_strategies: [
    "DI Cross + ADX > 25 (daily NIFTY F&O stocks)",
    "DMI Direction Filter on Top of MACD (1h indices)",
  ],

  indian_context:
    "DMI is less commonly discussed standalone in Indian retail than its sibling ADX is — most communities use ADX > 20 as a filter and pick direction from other indicators (price > EMA, Supertrend colour). When DMI IS used, it's typically on daily charts for swing-trade direction in F&O stocks. Sector-rotation traders watch DI+ / DI- on sector indices (NIFTY IT, NIFTY METAL) to time when leadership rotates between sectors — a fresh DI+ cross above DI- on a sector with ADX rising is a classic 'rotate INTO this sector' signal.",
};
