import type { TutorialScript } from "./_types";

export const FIRST_STRATEGY_TEMPLATE: TutorialScript = {
  topic: "first-strategy-template",
  duration_target_seconds: 300,

  hindi_script: {
    intro:
      "Namaste, Jayesh hu. Aaj ka tutorial: pehli strategy template ko clone karke paper trade mein run karna. Hum EMA Crossover use karenge — beginners ke liye sabse simple aur reliable setup.",
    sections: [
      {
        time_start: 12,
        time_end: 65,
        narration:
          "Dashboard pe login karein. Left sidebar mein 'Strategies' tab. 'Browse Strategy Templates' card pe click karein. Aapko 50+ templates dikhenge. Top mein filter chips hain — Difficulty, Capital Required, Style. Hum 'Beginner' aur 'Trend Following' select karte hain. EMA Crossover (9/21) sabse upar dikhega.",
        screen_action:
          "Click Strategies sidebar. Browse Strategy Templates page. Filter chips: select Beginner, select Trend Following. Card grid re-arranges with EMA Crossover top-left.",
        b_roll_suggested:
          "Close-up of EMA Crossover card showing difficulty 1/5, win rate ~52%, capital efficiency 4/5",
      },
      {
        time_start: 65,
        time_end: 135,
        narration:
          "EMA Crossover card pe click karein. Detail page khulta hai. Yahan poori explanation hai — kya karta, kab kaam karta, kab nahi karta, common mistakes. Scroll karein. Backtest section dikhega — last 3 mahine ke NIFTY pe simulated results. Win rate, average return, max drawdown. Padhein dhyan se.",
        screen_action:
          "Click EMA Crossover card. Detail page loads. Scroll through what-it-does, best/worst conditions, mistakes list, then backtest section with charts.",
        b_roll_suggested:
          "Animated equity curve from backtest section, with drawdown highlighted in red",
      },
      {
        time_start: 135,
        time_end: 210,
        narration:
          "Top right pe 'Clone to my account' button hai. Click karein. Settings form khulta hai. Capital allocation — ₹1L default. Max position size — 10% (₹10K per trade). Stop loss — 2 ATR. Take profit — 3 ATR. These are templates ki recommended values; aap adjust kar sakte ho. Beginner ke liye defaults se start karein.",
        screen_action:
          "Top-right Clone button. Settings form. Capital field ₹100000. Max position 10%. Stop 2 ATR. Take profit 3 ATR. Each value briefly highlighted as narrator mentions.",
        b_roll_suggested:
          "Quick animated tooltip explaining ATR — 'volatility-based stop sizing'",
      },
      {
        time_start: 210,
        time_end: 270,
        narration:
          "Save click karein. Strategy ab aapki ho gayi — 'My Strategies' page pe dikhegi. 'Start Paper Trade' button pe click karein. Confirmation modal — paper mode confirm karein. Strategy ab live signals generate karegi. Pehla signal aane mein 1-2 din lag sakte hain — market conditions pe depend karta hai.",
        screen_action:
          "Click Save. Redirect to My Strategies. New EMA Crossover card with 'Paper Pending' badge. Click Start Paper Trade. Confirmation modal. Click Confirm. Badge changes to 'Paper Active'.",
        b_roll_suggested:
          "Calendar showing 1-2 day waiting period, with a notification animation for 'first signal generated'",
      },
    ],
    outro:
      "Bas. Aapki pehli strategy paper trade mein run kar rahi hai. 4 hafte tak observe karein — har trade ka entry, exit, reason. Notes likhein. Yahi habit aapko discretionary trader se systematic trader banayegi. Agla tutorial: Paper Mode kya hai, kyu zaroori hai — wahin milte hain.",
    total_word_count: 315,
  },

  english_script: {
    intro:
      "Hi, this is Jayesh. Today's tutorial: cloning your first strategy template and running it in paper trade. We'll use EMA Crossover — the simplest and most reliable beginner setup.",
    sections: [
      {
        time_start: 11,
        time_end: 62,
        narration:
          "Log in to your dashboard. Click Strategies in the left sidebar, then click Browse Strategy Templates. You'll see over 50 templates. The filter chips at the top let you narrow down by Difficulty, Capital Required, and Style. We'll filter Beginner plus Trend Following. EMA Crossover 9/21 will be at the top.",
        screen_action:
          "Click Strategies sidebar. Browse Strategy Templates. Filter Beginner + Trend Following. Cards re-arrange.",
        b_roll_suggested: "Close-up of EMA Crossover card stats",
      },
      {
        time_start: 62,
        time_end: 130,
        narration:
          "Click the EMA Crossover card. The detail page opens. Here you'll find a full explanation — what it does, when it works, when it doesn't, common mistakes. Scroll down. There's a backtest section — three months of simulated NIFTY results. Win rate, average return, max drawdown. Read carefully.",
        screen_action:
          "Click card. Detail page. Scroll through sections, then backtest with charts.",
        b_roll_suggested:
          "Animated equity curve with drawdown band highlighted in red",
      },
      {
        time_start: 130,
        time_end: 205,
        narration:
          "Top-right has a 'Clone to my account' button. Click it. Settings form opens. Capital allocation — ₹1L by default. Max position size — 10%, so ₹10K per trade. Stop loss — 2 ATR. Take profit — 3 ATR. These are the template's recommended values; you can adjust. For beginners, start with the defaults.",
        screen_action:
          "Clone button. Settings form. Each field highlighted as narrator speaks.",
        b_roll_suggested:
          "Animated tooltip explaining ATR — 'volatility-based stop sizing'",
      },
      {
        time_start: 205,
        time_end: 265,
        narration:
          "Click Save. The strategy is now yours — visible in My Strategies. Click 'Start Paper Trade'. Confirm in the modal. The strategy will start generating live signals. First signal may take 1-2 days depending on market conditions — don't worry, it's working.",
        screen_action:
          "Save → My Strategies → new card with Paper Pending → Start Paper Trade → confirm → badge changes to Paper Active.",
        b_roll_suggested:
          "Calendar showing 1-2 day wait, notification animation for first signal",
      },
    ],
    outro:
      "That's it. Your first strategy is running in paper trade. Watch it for 4 weeks. Note every entry, exit, and reason. That note-keeping habit is what turns a discretionary trader into a systematic one. Next tutorial: what paper mode is and why it matters. See you there.",
    total_word_count: 295,
  },

  thumbnail_text_options: [
    "Pehli Strategy in 3 mins",
    "Clone → Configure → Paper Trade",
    "Beginner's First Template",
  ],
  hashtags: [
    "#TradeTri",
    "#StrategyTemplate",
    "#EMACrossover",
    "#PaperTrading",
    "#IndianRetailTraders",
    "#AlgoTrading",
  ],
  target_audience:
    "TradeTri users who have signed up and want to launch their first strategy",
  prerequisites: ["TradeTri account", "Signed in to dashboard"],
};
