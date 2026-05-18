import type { TutorialScript } from "./_types";

export const BACKTEST_INTERPRETATION: TutorialScript = {
  topic: "backtest-interpretation",
  duration_target_seconds: 320,

  hindi_script: {
    intro:
      "Namaste, Jayesh hu. Backtest results dekhna ek skill hai — naye traders aksar gumrah ho jaate hain '95% win rate' jaise numbers se. Aaj hum sikhenge ki backtest panel pe asli kya dekhna chahiye aur kya skip karna chahiye.",
    sections: [
      {
        time_start: 12,
        time_end: 75,
        narration:
          "Pehle TradeTri pe koi bhi strategy template kholein. Detail page mein scroll karein backtest section tak. Aapko 6 numbers dikhenge: Win Rate, Average Return, Max Drawdown, Sharpe Ratio, Total Trades, Profit Factor. Inhi par focus karenge.",
        screen_action:
          "TradeTri strategy detail page open. Scroll down to backtest section. Six numbers prominent in stat cards.",
        b_roll_suggested:
          "Slow tracking shot across the six stat cards, each briefly enlarged as introduced",
      },
      {
        time_start: 75,
        time_end: 145,
        narration:
          "Win Rate aur Risk-Reward Ratio dono dekhna ZAROORI hai. 90% win rate dikhayi de to bhi paise lose ho sakte agar har win ₹100 ka aur har loss ₹2000 ka ho. Always check kya R:R ratio worth-it hai. Hum 1:1.5 minimum recommend karte; 1:2 ya better best.",
        screen_action:
          "Highlight Win Rate and R:R cards together. Animation showing a 90% win + bad R:R losing money vs a 45% win + good R:R making money.",
        b_roll_suggested:
          "Whiteboard math: 9 × ₹100 - 1 × ₹2000 = -₹1100. Common-sense calculation.",
      },
      {
        time_start: 145,
        time_end: 215,
        narration:
          "Max Drawdown — sabse important number jo log skip karte. Ye batata ki peak se trough tak loss kitna hua. 15% se zyada drawdown ho to live trading mein wo emotionally bear karna mushkil hai. Agar drawdown 25% hai aur aapne backtest mein bhi nahi observe kiya, to live mein wo trade aap skip kar denge — strategy band ho jaayegi.",
        screen_action:
          "Equity curve animation with red shaded drawdown periods highlighted. Tooltip showing 15% threshold line.",
        b_roll_suggested:
          "Photo of someone looking at a phone with concerned expression — emotional reality of drawdown",
      },
      {
        time_start: 215,
        time_end: 270,
        narration:
          "Sharpe Ratio — risk-adjusted return. Above 1 = decent. Above 1.5 = good. Above 2 = very rare. 5 se upar Sharpe dikhe to backtest mein bug hai ya overfitting hai — verify karein. Total trades 30 se kam ho to sample size statistically meaningful nahi hai — usse trust mat karein.",
        screen_action:
          "Sharpe ratio card with band colors: <1 red, 1-1.5 yellow, 1.5+ green, >2 starred. Then Total Trades card with sample-size warning if < 30.",
        b_roll_suggested:
          "Quick visual: 5 trades vs 100 trades scatter plot — showing variance reduction",
      },
      {
        time_start: 270,
        time_end: 310,
        narration:
          "Profit Factor — gross profits divided by gross losses. Above 1.5 = healthy. Above 2 = excellent. Below 1.2 = barely scrapes by; emotional toll usually not worth it. Ye number alone se decide mat karein; combine karein Sharpe aur Max DD ke saath.",
        screen_action:
          "Profit Factor card highlighted. Decision matrix overlay: PF + Sharpe + Max DD combined into a 'go/no-go' visual.",
        b_roll_suggested:
          "Animated decision flowchart: 3 checkpoints leading to 'Use strategy' or 'Skip strategy'",
      },
    ],
    outro:
      "Backtest historical hai, future ki guarantee nahi. Hamesha paper trading se confirm karein — minimum 4 hafte. Aur honest baat: TradeTri ka backtest realistic hai — hum slippage aur fees include karte hain. Doosre platforms aksar pure 'theoretical' returns dikhate. Subscribe karein — agla tutorial risk management basics pe.",
    total_word_count: 350,
  },

  english_script: {
    intro:
      "Hi, Jayesh here. Reading backtest results is a skill — new traders often get fooled by '95% win rate' numbers. Today we'll learn what to actually look at on a backtest panel and what to skip.",
    sections: [
      {
        time_start: 11,
        time_end: 72,
        narration:
          "Open any strategy template on TradeTri. Scroll to the backtest section. You'll see six numbers: Win Rate, Average Return, Max Drawdown, Sharpe Ratio, Total Trades, Profit Factor. We'll focus on these.",
        screen_action:
          "Strategy detail page open. Scroll to backtest section. Six stat cards prominent.",
        b_roll_suggested: "Slow tracking shot across the six cards",
      },
      {
        time_start: 72,
        time_end: 140,
        narration:
          "Win Rate and Risk-Reward Ratio must be checked together. Even a 90% win rate can lose money if each win is ₹100 and each loss is ₹2000. Always check if R:R is worth it. We recommend 1:1.5 minimum; 1:2 or better is ideal.",
        screen_action:
          "Highlight Win Rate and R:R cards together. Math animation: 90% win × bad R:R = losing money.",
        b_roll_suggested: "Whiteboard math: 9 × ₹100 - 1 × ₹2000 = -₹1100",
      },
      {
        time_start: 140,
        time_end: 210,
        narration:
          "Max Drawdown — the most important number people skip. It tells you peak-to-trough loss. Drawdown above 15% is emotionally hard to bear in live trading. If a strategy backtested at 25% drawdown, you probably won't be in the trade when the recovery happens — you'll have already paused it.",
        screen_action:
          "Equity curve with red-shaded drawdown periods. 15% threshold line.",
        b_roll_suggested: "Photo: concerned face looking at phone",
      },
      {
        time_start: 210,
        time_end: 265,
        narration:
          "Sharpe Ratio — risk-adjusted return. Above 1 is decent. Above 1.5 is good. Above 2 is rare. If Sharpe is above 5, the backtest has a bug or overfitting — verify. Total Trades below 30 isn't statistically meaningful — don't trust it.",
        screen_action:
          "Sharpe card with band colors. Total Trades card with sample-size warning.",
        b_roll_suggested: "Visual: 5 trades vs 100 trades scatter — variance reduction",
      },
      {
        time_start: 265,
        time_end: 305,
        narration:
          "Profit Factor — gross profits divided by gross losses. Above 1.5 is healthy. Above 2 is excellent. Below 1.2 barely scrapes by; emotional toll usually not worth it. Don't decide on this alone; combine with Sharpe and Max DD.",
        screen_action:
          "Profit Factor card. Decision matrix overlay combining PF + Sharpe + Max DD.",
        b_roll_suggested:
          "Decision flowchart leading to 'Use strategy' or 'Skip'",
      },
    ],
    outro:
      "Backtest is historical, not a future guarantee. Always confirm with paper trading — 4 weeks minimum. Honest note: TradeTri's backtest is realistic — we include slippage and fees. Many platforms show pure theoretical returns. Subscribe — next tutorial is risk management basics.",
    total_word_count: 340,
  },

  thumbnail_text_options: [
    "Read Backtest Like a Pro",
    "6 Numbers You Must Check",
    "Don't Get Fooled by 95% Win Rate",
  ],
  hashtags: [
    "#Backtest",
    "#TradingStrategy",
    "#TradeTri",
    "#WinRate",
    "#MaxDrawdown",
    "#SharpeRatio",
    "#IndianStockMarket",
  ],
  target_audience:
    "Traders evaluating strategy templates before cloning to their paper account",
  prerequisites: ["TradeTri free account", "Basic familiarity with strategy templates"],
};
