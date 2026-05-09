/**
 * Static Hinglish coaching tips for the Always-On AlgoMitra panel.
 *
 * Phase 1 (locked May-18 launch plan): pre-defined tips per
 * (builder mode, builder section). Phase 2 wires per-field triggers
 * + dynamic context awareness.
 *
 * Schema:
 *
 *   COACHING_TIPS[mode][section] = { title, tips: string[] }
 *
 * Sections deliberately mirror the Expert builder's tabs
 * (indicators / entry / exit / risk / json) so the same tip surface
 * works across all three builder tiers — Beginner just collapses
 * indicator + entry into "setup", Intermediate keeps everything,
 * Expert adds the JSON section.
 *
 * Tip writing rules:
 *
 *   * Hinglish — Hindi sentence structure with English trading
 *     vocabulary (RSI, EMA, stop loss). Same voice as the existing
 *     ChatWidget messages.
 *   * Each tip is one sentence, ≤ 90 chars.
 *   * 3 tips per section — enough to be useful, not so many that
 *     the panel becomes a wall of text.
 */

export type BuilderMode = "beginner" | "intermediate" | "expert";

export type BuilderSection =
  | "indicators"
  | "entry"
  | "exit"
  | "risk"
  | "robustness"
  | "json";

export interface CoachingSection {
  title: string;
  tips: string[];
}

export type CoachingTipsForMode = Partial<Record<BuilderSection, CoachingSection>>;

export const COACHING_TIPS: Record<BuilderMode, CoachingTipsForMode> = {
  beginner: {
    indicators: {
      title: "Indicators Kya Hain?",
      tips: [
        "Indicators charts ke patterns dikhate hain — jaise EMA trend dikhata hai.",
        "Beginner ke liye 1-2 indicators kaafi hain — zyada confusion karte hain.",
        "Popular: RSI (overbought/oversold), EMA (trend), MACD (momentum).",
      ],
    },
    entry: {
      title: "Entry Conditions",
      tips: [
        "Entry condition decide karta hai trade kab open ho.",
        "Simple: 'EMA 20 cross EMA 50' = trend change signal.",
        "Beginner: 1-2 conditions chahiye, AND logic se simple rakho.",
      ],
    },
    exit: {
      title: "Exit Strategy",
      tips: [
        "Exit decide karta hai profit/loss kab book ho.",
        "Stop Loss: maximum loss tolerate kar sakte ho.",
        "Target: profit kab book karna — greedy mat bano.",
      ],
    },
    risk: {
      title: "Risk Management",
      tips: [
        "Position size capital ka 2–5 % se zyada nahi.",
        "Stop Loss hamesha mandatory hai — bina nahi trade karo.",
        "Daily loss limit set karo — apne aap ko bachao.",
      ],
    },
  },
  intermediate: {
    indicators: {
      title: "Indicators Combine Karna",
      tips: [
        "2–4 indicators ka mix sweet spot hai — over-fitting avoid hota hai.",
        "Trend (EMA / MACD) + momentum (RSI) ka combo strong base hai.",
        "Same family ke indicators (RSI + Stochastic) avoid karo — redundant hain.",
      ],
    },
    entry: {
      title: "Multi-Condition Entries",
      tips: [
        "AND logic strict hai — sab conditions match honi chahiye.",
        "OR logic relaxed — koi ek match ho jaaye toh trade.",
        "Confirmation indicators (volume, ADX) entry ko strong banaate hain.",
      ],
    },
    exit: {
      title: "Smart Exits",
      tips: [
        "Trailing stop loss profit lock karta hai jaise price upar jaata hai.",
        "Partial exit: half qty target pe close, baaki trail karo.",
        "Time-based exit: intraday strategy 15:15 IST tak square off karo.",
      ],
    },
    risk: {
      title: "Position Sizing & Risk",
      tips: [
        "Lot size strategy + capital + stop-loss distance se decide hota hai.",
        "Per-trade risk: capital ka 1 % se 2 % maximum.",
        "Max trades/day cap karo — over-trading mein loss aata hai.",
      ],
    },
  },
  expert: {
    indicators: {
      title: "Advanced Indicator Tuning",
      tips: [
        "Indicator periods ko sensitivity-test karo — robust values pick karo.",
        "Custom params experiment-kar sakte ho, par walk-forward ke saath validate karo.",
        "Experimental indicators (Donchian, ATR-based) Robustness tab ke baad use karo.",
      ],
    },
    entry: {
      title: "Complex Entry Logic",
      tips: [
        "Indicator + candle + price + time conditions sab combine kar sakte ho.",
        "AND/OR top-level operator — nested grouping ke liye JSON tab use karo.",
        "Reverse-signal entry: same condition opposite side trigger karta hai.",
      ],
    },
    exit: {
      title: "Multi-Stage Exits",
      tips: [
        "Partial exits + trailing + indicator-driven exits ek saath use kar sakte ho.",
        "Square-off time intraday strategies ke liye must hai.",
        "Reverse-signal exit position flip karta hai — directional strategies ke liye.",
      ],
    },
    risk: {
      title: "Risk Caps & Override",
      tips: [
        "Daily loss + max trades + capital-per-trade — three lines of defence.",
        "Max loss streak strategy auto-pause trigger karta hai.",
        "Robustness toggle on karo — sensitivity sweep extra confidence deta hai.",
      ],
    },
    robustness: {
      title: "Walk-Forward + Sensitivity",
      tips: [
        "Walk-forward 5 alag time windows mein test karta hai — out-of-sample check.",
        "Sensitivity ±10 % parameter perturbation se overfitting detect karta hai.",
        "Dono enable karna ideal — slow but high-confidence verdict deta hai.",
      ],
    },
    json: {
      title: "Raw JSON Editing",
      tips: [
        "JSON tab read+write — Apply ke baad builder state overwrite ho jaata hai.",
        "Validate-on-blur catches schema errors before submission.",
        "Sync button text ko builder state se refresh karta hai — manual edits ke baad.",
      ],
    },
  },
};

export const WELCOME_MESSAGES: Record<BuilderMode, string> = {
  beginner:
    "Namaste! Strategy banane mein madad karu? Step-by-step le chalunga. 👋",
  intermediate:
    "Namaste! Saari sections ek saath visible hain — kahin bhi shuru kar sakte ho. 👋",
  expert:
    "Namaste! Expert mode mein full control hai. Tips dekho jab kahin doubt ho. 👋",
};
