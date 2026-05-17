import type { TutorialScript } from "./_types";

export const RISK_MANAGEMENT_BASICS: TutorialScript = {
  topic: "risk-management-basics",
  duration_target_seconds: 330,

  hindi_script: {
    intro:
      "Namaste, Jayesh hu. Aaj sabse important topic — risk management. Strategy kitni bhi achchhi ho, agar risk management galat hai to account zero hota. Ye 5 minute video aapke trading career ka sabse important hai. Pura dekhein.",
    sections: [
      {
        time_start: 14,
        time_end: 90,
        narration:
          "Pehla rule — 1% risk per trade. Iska matlab kya. Maan lo aapke pas ₹1 lakh capital hai. Ek trade mein aap maximum ₹1000 lose kar sakte ho. ₹1000 'risk' hai entry aur stop loss ke beech ka distance × kitne shares. Agar entry ₹500 hai aur stop ₹490 hai (₹10 risk per share), to aap 100 shares le sakte (₹1000 ÷ ₹10). Position size ye decide karta — gut feel nahi.",
        screen_action:
          "TradeTri position sizing calculator. ₹1L capital, 1% risk = ₹1000. Entry 500, stop 490. Position size auto-calculates 100. Slider changes parameters, position size updates live.",
        b_roll_suggested: "Whiteboard math drawn out — 1% rule formula",
      },
      {
        time_start: 90,
        time_end: 165,
        narration:
          "Doosra rule — stop loss hamesha pehle set karein, entry ke saath. Trade mein jaane ke baad stop nahi sochna. Aapke brain mein loss aversion bias hai — open trade pe aap stop loosen kar dete ho. Yahi 'main thoda aur wait karta hu' ka start hai aur ₹10K loss ka end. Pre-commit on stop.",
        screen_action:
          "Strategy clone form open. Stop loss field highlighted with red ring. Tooltip: 'Pre-commit. Don't change after entry.' Then animation showing a 'tempting' moment to widen stop, with a big X over it.",
        b_roll_suggested:
          "Photo of someone staring at a losing position late at night — emotional reality",
      },
      {
        time_start: 165,
        time_end: 230,
        narration:
          "Teesra — Target/Take Profit. Risk: Reward ratio minimum 1:1.5 hona chahiye, ideally 1:2 ya better. Iska matlab: ₹1000 risk pe minimum ₹1500 ka target. Kyun? Kyunki 50% win rate pe bhi profitable rahoge ratio 1:2 ke saath. Math: 50 wins × ₹2000 = ₹1L profit, 50 losses × ₹1000 = ₹50K loss, net ₹50K. Win rate se zyada ratio matter karta.",
        screen_action:
          "Risk-Reward calculator. Adjusting ratio slider 1:1, 1:1.5, 1:2. Profit/loss visualization updates. At 1:2, even 45% win rate shows positive net.",
        b_roll_suggested: "Animated coin flip showing 50% odds with different R:R outcomes",
      },
      {
        time_start: 230,
        time_end: 290,
        narration:
          "Chautha — Daily aur weekly drawdown limits. Hum recommend karte: daily -3% ya weekly -5% hit ho jaaye to sab strategies pause. TradeTri server-side enforce karta — aap chahein bhi to override nahi kar sakte. Kyun zaroori? Kyunki trading ke baad emotional state mein 'revenge trades' lete log, aur wo account zero karte. Circuit breaker zaroori hai.",
        screen_action:
          "Settings page showing daily/weekly drawdown sliders set at -3% and -5%. 'Server enforced' lock icon. Then a simulation showing strategies auto-pausing when threshold hits.",
        b_roll_suggested: "Calendar showing a bad week, then a pause icon, then recovery",
      },
      {
        time_start: 290,
        time_end: 320,
        narration:
          "Paanchwa — diversification. Ek hi strategy pe poora capital mat lagao. 3-5 strategies parallel chalao different market conditions ke liye. Ek mean-reversion, ek trend-following, ek breakout. Jab ek strategy struggle kare to doosri compensate karti. Indian market mein ye principle bahut zaroori — regimes badalte rehte.",
        screen_action:
          "Portfolio view with 5 strategy cards, each in different style. Allocation pie chart showing balanced distribution.",
        b_roll_suggested: "Sector rotation visualization showing different strategies winning in different months",
      },
    ],
    outro:
      "1% risk, hard stops, 1:2 minimum R:R, drawdown circuit-breakers, diversification — yahi paanch rules aapko 95% retail traders se aage rakhenge. Skill nahi, discipline matter karta. TradeTri pe ye sab built-in hai. Subscribe karein — agla tutorial AlgoMitra introduction pe.",
    total_word_count: 410,
  },

  english_script: {
    intro:
      "Hi, Jayesh here. The most important topic — risk management. No matter how good your strategy is, if your risk management is wrong, the account goes to zero. This 5-minute video is the most important one in your trading career. Watch all of it.",
    sections: [
      {
        time_start: 13,
        time_end: 85,
        narration:
          "Rule one — 1% risk per trade. What does that mean? Say you have ₹1L capital. On one trade you can lose at maximum ₹1000. ₹1000 'risk' is the distance between entry and stop loss times the number of shares. If entry is ₹500 and stop is ₹490 (₹10 risk per share), you can take 100 shares (₹1000 ÷ ₹10). Position sizing decides this — not gut feel.",
        screen_action:
          "TradeTri position sizing calculator. ₹1L cap, 1% risk. Entry/stop fields. Size auto-calculates. Slider updates live.",
        b_roll_suggested: "Whiteboard math of the 1% rule",
      },
      {
        time_start: 85,
        time_end: 160,
        narration:
          "Rule two — set the stop loss before entry, never after. Once in the trade, don't reconsider the stop. Your brain has loss-aversion bias — you'll loosen the stop on an open trade. That's how 'let me wait a bit more' becomes a ₹10K loss. Pre-commit to the stop.",
        screen_action:
          "Strategy clone form. Stop loss field with red ring. Tooltip: 'Pre-commit. Don't change after entry.' Animation showing the temptation to widen.",
        b_roll_suggested: "Photo: late-night losing position",
      },
      {
        time_start: 160,
        time_end: 225,
        narration:
          "Rule three — target / take profit. Risk:Reward ratio must be at least 1:1.5, ideally 1:2 or better. Meaning: for ₹1000 risk, minimum ₹1500 target. Why? At 1:2, even a 50% win rate is profitable. Math: 50 wins × ₹2000 = ₹1L, 50 losses × ₹1000 = ₹50K, net ₹50K. Ratio matters more than win rate.",
        screen_action:
          "R:R calculator. Adjusting slider 1:1, 1:1.5, 1:2. P/L visualization. At 1:2, even 45% win rate is positive net.",
        b_roll_suggested: "Animated coin flip with different R:R outcomes",
      },
      {
        time_start: 225,
        time_end: 285,
        narration:
          "Rule four — daily and weekly drawdown limits. We recommend: pause all strategies if daily hits -3% or weekly hits -5%. TradeTri enforces this server-side — you can't override even if you want to. Why? Because after a bad day, traders take 'revenge trades' in an emotional state, and that's how accounts go to zero. Circuit breakers are not optional.",
        screen_action:
          "Settings page with sliders set -3% / -5%. Server-enforced lock icon. Simulation of auto-pause.",
        b_roll_suggested: "Calendar showing a bad week, then a pause icon, then recovery",
      },
      {
        time_start: 285,
        time_end: 315,
        narration:
          "Rule five — diversification. Don't put all capital on one strategy. Run 3-5 strategies in parallel for different market regimes. One mean-reversion, one trend-following, one breakout. When one struggles, another compensates. In Indian markets this is critical — regimes shift often.",
        screen_action:
          "Portfolio view with 5 strategies. Allocation pie chart balanced.",
        b_roll_suggested: "Sector rotation visualization — different strategies winning in different months",
      },
    ],
    outro:
      "1% risk, hard stops, 1:2 minimum R:R, drawdown circuit-breakers, diversification — these five rules put you ahead of 95% of retail traders. It's discipline, not skill, that matters. TradeTri builds these in. Subscribe — next tutorial is AlgoMitra introduction.",
    total_word_count: 395,
  },

  thumbnail_text_options: [
    "Risk Management = Survival",
    "5 Rules → 95% Edge",
    "1% Rule explained",
  ],
  hashtags: [
    "#RiskManagement",
    "#TradeTri",
    "#PositionSizing",
    "#StopLoss",
    "#IndianRetailTraders",
    "#TradingDiscipline",
  ],
  target_audience: "All TradeTri users — especially before going live",
  prerequisites: ["TradeTri account"],
};
