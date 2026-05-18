import type { TutorialScript } from "./_types";

export const LIVE_TRADING_PREP: TutorialScript = {
  topic: "live-trading-prep",
  duration_target_seconds: 320,

  hindi_script: {
    intro:
      "Namaste, Jayesh hu. July 2026 mein live trading khulta hai TradeTri pe — vetted accounts ke liye. Aaj batata hu ki tab tak kya prep karna chahiye. Sirf paper P&L positive hone se ready nahi hote. Discipline check karte.",
    sections: [
      {
        time_start: 14,
        time_end: 85,
        narration:
          "Checkpoint pehla — minimum 8 hafte paper trading. Backtest sirf historical hai. Aapki strategy aaj ke market mein kaisi behave karti, ye sirf forward-tested data se pata chalta. 4 hafte minimum, lekin 8-12 ideal. Is duration mein aap multiple market regimes dekhenge — trending, range, news-driven. Sirf trending market mein chali strategy live mein chop aane par fail hogi.",
        screen_action:
          "Calendar showing 8-week paper trading window. Highlight different market regimes within it: trending green, range yellow, choppy red. All three must be observed.",
        b_roll_suggested:
          "Time-lapse of NIFTY chart over 8 weeks showing regime changes",
      },
      {
        time_start: 85,
        time_end: 155,
        narration:
          "Checkpoint doosra — max drawdown 15% se kam. Drawdown means peak P&L se trough tak loss. Agar paper mein 20% drawdown dikha, to live mein wo emotional bear karna mushkil hai. Aap us recovery phase ke pehle hi strategy pause karoge — aur fir 'wo strategy chhod di' regret hoga. 15% threshold strict hai is reason se.",
        screen_action:
          "Equity curve with drawdown highlighted. Red zone if > 15%. Threshold line marked. 'Recommendation: pause this strategy, refine' badge.",
        b_roll_suggested: "Photo of stressed face during drawdown period — emotional reality",
      },
      {
        time_start: 155,
        time_end: 225,
        narration:
          "Checkpoint teesra — manual override rate. Dashboard mein ek 'overrides taken' counter hai. Kitne signals aapne manually skip kiye ya manually trade liya without rule. Agar ye 20% se zyada hai, aap strategy nahi, apni discretion paper-trade kar rahe. Iska matlab live mein bhi yahi karoge — aur fir result strategy ka nahi, aapki gut feel ka hoga. Yahi danger zone hai retail traders ke liye. Pehle wo theek karein.",
        screen_action:
          "Override counter dashboard widget. Showing percentage breakdown: 78% rule-followed, 22% overridden. Red warning indicator.",
        b_roll_suggested:
          "Behaviour pattern visualization — signals graph with overrides marked as red dots",
      },
      {
        time_start: 225,
        time_end: 285,
        narration:
          "Checkpoint chautha — capital plan. Live shuru kab? Hum recommend karte ₹25,000 se ₹50,000 max for the first 4 weeks live. Doesn't matter kya aapka paper P&L tha. Reason — aap live mein different person hote. Slippage real hota, fees real hote, FOMO real hota. Choti capital pe pehle mistakes dekho, fir scale karo. Hum ne 6 mahine paper testing ke baad ye threshold rakha — engineering decision hai.",
        screen_action:
          "Capital scaling roadmap: Month 1: ₹50K, Month 2-3: ₹1L, Month 4+: scale based on results. Graphical phased rollout.",
        b_roll_suggested:
          "Comparison: 'first-time live trader emotional graph' vs 'experienced systematic trader emotional graph'",
      },
      {
        time_start: 285,
        time_end: 310,
        narration:
          "Checkpoint paanchwa — pre-flight checklist. Live jaane se ek din pehle ye check karein: broker session token rotated, strategy settings reviewed, daily drawdown limit set, support contact saved. TradeTri ek 'Live Ready Checklist' deta hai — automatic checks. Pehle wo green ho, fir switch flip karein.",
        screen_action:
          "Live Ready Checklist UI: 5 checkpoints, all green checks. 'Enable Live Trading' button.",
        b_roll_suggested:
          "Pre-flight aviation checklist visual — adds gravity to the moment",
      },
    ],
    outro:
      "Live trading milestone hai, race nahi. Jab ye paanch checkpoints clear ho jaayein, hum aapko invite karenge beta cohort mein. July 2026. Tab tak paper-trade karein, journal likhein, AlgoMitra se baat karein. Subscribe karein — agle tutorials mein deeper strategies pe jaate.",
    total_word_count: 360,
  },

  english_script: {
    intro:
      "Hi, Jayesh here. Live trading opens on TradeTri in July 2026 — for vetted accounts. Today I'll show you what to prep before then. Positive paper P&L alone doesn't mean ready. We check discipline.",
    sections: [
      {
        time_start: 13,
        time_end: 82,
        narration:
          "Checkpoint one — minimum 8 weeks of paper trading. Backtest is historical. How your strategy behaves in today's market only shows in forward-tested data. 4 weeks is minimum, 8-12 is ideal. In that duration you'll see multiple regimes — trending, range, news-driven. A strategy that only ran in trending markets will fail in chop.",
        screen_action:
          "8-week calendar. Regimes coloured: trending green, range yellow, choppy red. Need all three.",
        b_roll_suggested: "Time-lapse NIFTY chart showing regime changes",
      },
      {
        time_start: 82,
        time_end: 150,
        narration:
          "Checkpoint two — max drawdown under 15%. Drawdown is peak-to-trough loss. If paper showed 20% drawdown, that's emotionally hard in live. You'll pause the strategy before the recovery happens, then regret quitting. The 15% threshold is strict for this reason.",
        screen_action:
          "Equity curve with drawdown. Red zone above 15%. Recommendation badge.",
        b_roll_suggested: "Photo of stressed face during drawdown",
      },
      {
        time_start: 150,
        time_end: 220,
        narration:
          "Checkpoint three — manual override rate. The dashboard has an 'overrides taken' counter. How many signals did you manually skip or trade outside the rules? If that's above 20%, you're not paper-trading the strategy — you're paper-trading your discretion. You'll do the same in live, and the result will reflect your gut feel, not the strategy. This is the danger zone for retail. Fix it first.",
        screen_action:
          "Override counter widget. 78% rule-followed, 22% overridden. Red warning.",
        b_roll_suggested: "Signals graph with overrides as red dots",
      },
      {
        time_start: 220,
        time_end: 280,
        narration:
          "Checkpoint four — capital plan. When you go live, how much? We recommend ₹25,000 to ₹50,000 for the first 4 weeks. No matter what your paper P&L showed. Reason — you're a different person in live. Slippage is real. Fees are real. FOMO is real. See your first mistakes on small capital, then scale. We set this threshold after 6 months of paper testing — engineering decision.",
        screen_action:
          "Capital scaling roadmap: Month 1 ₹50K, Months 2-3 ₹1L, Month 4+ scale by results.",
        b_roll_suggested:
          "Comparison: first-time vs experienced emotional graphs",
      },
      {
        time_start: 280,
        time_end: 305,
        narration:
          "Checkpoint five — pre-flight checklist. The day before going live, check: broker session token rotated, strategy settings reviewed, daily drawdown limit set, support contact saved. TradeTri provides a 'Live Ready Checklist' — automatic checks. Once all green, then flip the switch.",
        screen_action:
          "Live Ready Checklist UI: 5 checkpoints all green. Enable button.",
        b_roll_suggested: "Aviation pre-flight checklist visual",
      },
    ],
    outro:
      "Live trading is a milestone, not a race. When these five checkpoints clear, we invite you to the beta cohort. July 2026. Until then, paper-trade, journal, talk to AlgoMitra. Subscribe — next tutorials go deeper into strategies.",
    total_word_count: 345,
  },

  thumbnail_text_options: [
    "Live Trading Prep — 5 Checkpoints",
    "July 2026 — Are you Ready?",
    "Paper P&L ≠ Live Ready",
  ],
  hashtags: [
    "#LiveTrading",
    "#TradeTri",
    "#PaperToLive",
    "#TradingDiscipline",
    "#July2026",
    "#IndianRetailTraders",
  ],
  target_audience:
    "Active paper-trading users planning to transition to live in July 2026",
  prerequisites: [
    "Minimum 4 weeks of paper trading completed",
    "At least one strategy with positive cumulative P&L",
  ],
};
