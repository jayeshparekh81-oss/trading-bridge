import type { TutorialScript } from "./_types";

export const UNDERSTANDING_PAPER_MODE: TutorialScript = {
  topic: "understanding-paper-mode",
  duration_target_seconds: 280,

  hindi_script: {
    intro:
      "Namaste, Jayesh hu. Aaj baat karte hain Paper Mode pe — kya hai, kyu zaroori hai, aur kab live jaana sahi hai. Ye sabse important tutorial hai pehli strategy clone karne ke baad. Kripya pura dekhein.",
    sections: [
      {
        time_start: 15,
        time_end: 75,
        narration:
          "Paper Mode ka matlab — aapki strategy real NSE prices pe chalti hai, real signals generate karti hai, real entry-exit timestamps hote — but actual paisa kahin nahi jaata. Sab kuch simulated hota. Aap NIFTY ka real-time data dekhte ho. Wahi minute pe wahi signal jo live mein milta. Sirf order broker pe nahi place hota.",
        screen_action:
          "Split screen: left side shows Kite chart with real NIFTY data, right side shows TradeTri paper signal on the same candle. Synchronized timestamps highlighted.",
        b_roll_suggested:
          "Animation of a 'fake money' badge floating around the order panel; real-time clock ticking",
      },
      {
        time_start: 75,
        time_end: 145,
        narration:
          "Kyu zaroori hai? Teen reasons. Pehla — aapki strategy markets mein kaise behave karti, ye dekhne ka 4-12 hafte ka real-world test. Backtest historical hota; paper future-facing hai. Doosra — emotional preparation. Paper mein bhi pehla loss dekh ke pet mein dard hota. Live mein wo dard 10 guna hota. Tisra — aapke discipline ka test — kya aap rules follow karte ho ya manually override karte? Paper se honest pata chal jaata.",
        screen_action:
          "3-column layout: Real-world Test (4-12 weeks calendar), Emotional Prep (heart-rate graph animation), Discipline Check (override count badge).",
        b_roll_suggested:
          "Photo of someone watching screen with intense focus; transition to relaxed face after 4 weeks of paper",
      },
      {
        time_start: 145,
        time_end: 220,
        narration:
          "Kab live jaayein? Honestly — 8 to 12 hafte paper pe stable performance ke baad. 'Stable' ka matlab: positive P&L, max drawdown 15% se kam, aur aap ne 20% se zyada signals manually override nahi kiye. Agar override 20% se upar hai to aap paper-trading discretion kar rahe, strategy nahi. Pehle wo theek karein.",
        screen_action:
          "Checklist appears: Positive P&L (✓), Max DD < 15% (✓), Manual overrides < 20% (✓). Each item ticks in sequence. 'Ready for live' badge appears.",
        b_roll_suggested:
          "Calendar showing 8-12 week range highlighted, with a small graph of equity curve overlaid",
      },
      {
        time_start: 220,
        time_end: 270,
        narration:
          "Live jaane ke baad bhi paper account band mat karein — parallel chalayein same strategy ka. Wo aapka benchmark hai. Agar live aur paper P&L mein 25% se zyada gap aaye to ya slippage problem hai ya execution mein bug — investigation start kar dein. Hum yahi advice apne dosto ko dete hain — code mein bhi yahi enforce kiya hai.",
        screen_action:
          "Dual-pane comparison view: Paper P&L 12%, Live P&L 9%, gap indicator showing 25% as the alert threshold. A warning icon appears when gap crosses threshold.",
        b_roll_suggested:
          "Whiteboard sketch of slippage causes — order delay, queue, partial fill",
      },
    ],
    outro:
      "Paper Mode aapki sabse important learning tool hai. Hedge funds isse 'walk-forward testing' kehte; hum simple shabd mein 'paper' bolte. Bina paper ke live jaana matlab parachute ke bina jump karna. 4 hafte minimum — sabse short rule jo hum customers ko dete hain. Subscribe karein — agla tutorial chart par indicators samjhne pe.",
    total_word_count: 320,
  },

  english_script: {
    intro:
      "Hi, Jayesh here. Today we're talking about Paper Mode — what it is, why it matters, and when going live is right. This is the most important tutorial to watch after cloning your first strategy. Please watch all of it.",
    sections: [
      {
        time_start: 14,
        time_end: 72,
        narration:
          "Paper Mode means: your strategy runs on real NSE prices, generates real signals, real entry-exit timestamps — but no actual money moves. Everything is simulated. You see real-time NIFTY data. Same minute, same signal you'd get in live. The only difference: no order placed on the broker.",
        screen_action:
          "Split screen: real Kite chart on left, TradeTri paper signal on same candle on right. Timestamps synced.",
        b_roll_suggested: "'Fake money' badge floating around the order panel",
      },
      {
        time_start: 72,
        time_end: 140,
        narration:
          "Why it matters — three reasons. First: a 4-to-12 week real-world test of how your strategy behaves. Backtests are historical; paper is forward-facing. Second: emotional preparation. The first loss in paper hurts; in live it hurts ten times more. Third: discipline test — are you following your own rules or overriding manually? Paper tells you honestly.",
        screen_action:
          "3-column layout: Real-world Test (calendar), Emotional Prep (heart-rate animation), Discipline Check (override badge).",
        b_roll_suggested:
          "Photo: intense screen-watching; transition to a relaxed face after 4 weeks",
      },
      {
        time_start: 140,
        time_end: 215,
        narration:
          "When should you go live? Honestly — after 8 to 12 weeks of stable paper performance. 'Stable' means: positive P&L, max drawdown under 15%, and manual overrides under 20%. If your override rate is above 20%, you're paper-trading your discretion, not the strategy. Fix that first.",
        screen_action:
          "Checklist appearing: Positive P&L (✓), Max DD < 15% (✓), Overrides < 20% (✓). 'Ready for live' badge.",
        b_roll_suggested:
          "Calendar with 8-12 week range, equity curve overlay",
      },
      {
        time_start: 215,
        time_end: 265,
        narration:
          "After going live, don't close your paper account — run it in parallel for the same strategy. It's your benchmark. If live and paper P&L diverge by more than 25%, you either have a slippage problem or an execution bug. Investigate. This is the same advice I give friends, and it's the same threshold we enforce in the dashboard alerts.",
        screen_action:
          "Dual-pane view: Paper P&L vs Live P&L, gap indicator. Warning icon if gap > 25%.",
        b_roll_suggested:
          "Whiteboard sketch of slippage causes — order delay, queue, partial fill",
      },
    ],
    outro:
      "Paper Mode is your most important learning tool. Hedge funds call it 'walk-forward testing' — we just call it paper. Going live without it is jumping without a parachute. Four weeks minimum — that's the shortest rule we give customers. Subscribe — next tutorial is reading chart indicators.",
    total_word_count: 305,
  },

  thumbnail_text_options: [
    "Paper Mode Explained",
    "Why we don't rush to Live",
    "8-12 Weeks Paper Rule",
  ],
  hashtags: [
    "#PaperTrading",
    "#TradeTri",
    "#TradingDiscipline",
    "#WalkForwardTesting",
    "#IndianStockMarket",
    "#RiskManagement",
  ],
  target_audience:
    "New users who have a paper strategy running and want to understand the discipline before live",
  prerequisites: ["At least one strategy cloned in paper mode"],
};
