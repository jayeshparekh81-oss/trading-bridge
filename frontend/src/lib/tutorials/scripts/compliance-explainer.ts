import type { TutorialScript } from "./_types";

export const COMPLIANCE_EXPLAINER: TutorialScript = {
  topic: "compliance-explainer",
  duration_target_seconds: 290,

  hindi_script: {
    intro:
      "Namaste, Jayesh hu. Aaj baat karte hain SEBI compliance aur Glass Box AI ke baare mein. Ye boring lag sakta but ye dono concepts ka samajh aapko safe trading platforms aur scams ke beech farak karne mein help karenge. Pura dekhein.",
    sections: [
      {
        time_start: 14,
        time_end: 90,
        narration:
          "SEBI — Securities and Exchange Board of India. India ke share market ka regulator. SEBI ki kuch rules jo TradeTri jaise platforms pe lagti hain. Pehla — return guarantee dene wali claims illegal hain. Koi bhi platform jo '99% accuracy' ya 'guaranteed monthly returns' bole, wo SEBI rules tod raha. Doosra — investment advice dene ke liye RIA (Registered Investment Advisor) license chahiye. TradeTri RIA nahi hai — hum tools provider hain, advice nahi dete. Yahi reason hai jo AlgoMitra tips nahi deta.",
        screen_action:
          "SEBI logo and website screenshot. Then a 'red flag' montage: examples of common scam claims like '99% accuracy' with red X overlay.",
        b_roll_suggested:
          "Slow pan over actual SEBI circular text on screen — shows we read the rules",
      },
      {
        time_start: 90,
        time_end: 165,
        narration:
          "Teesra rule — fund handling. TradeTri kabhi bhi customer ke paise apne paas nahi rakhta. Aapke funds aapke broker ke paas rehte. Hum sirf API permissions use karke aapke broker ko order bhejte. Iska matlab agar TradeTri kal band ho jaaye, aapke paise safe rehte — kyunki wo Dhan ya Zerodha ke pas hain, hamare pas nahi. Custody risk zero hai.",
        screen_action:
          "Flow diagram: User → Broker (funds stay here) ← API permission ← TradeTri (just sends orders). Highlight 'NO FUND CUSTODY' badge.",
        b_roll_suggested:
          "Animation showing money flowing only between user and broker, never touching TradeTri server icon",
      },
      {
        time_start: 165,
        time_end: 235,
        narration:
          "Ab Glass Box AI ki baat. Doosre platforms 'AI signals' bechte — input do, signal lo, kaise nikla wo nahi pata. Black box. Hum is approach ko reject karte. Glass Box ka matlab — har calculation, har indicator value, har signal aap audit kar sakte. Click karein RSI = 65 pe, aapko formula dikhega, kaunse bars use hue, exact timestamps. Aap apne Kite chart pe verify kar sakte same number. Transparency optional nahi, default hai.",
        screen_action:
          "TradeTri chart with RSI indicator. Click on RSI value. Audit panel opens showing formula (RS calculation), input bars (last 14), output value. Side-by-side with Kite chart showing same RSI value.",
        b_roll_suggested:
          "Split screen: Black Box (mysterious gears) vs Glass Box (clear formula). Visually striking contrast.",
      },
      {
        time_start: 235,
        time_end: 275,
        narration:
          "Kyun ye important hai? Kyunki Indian retail trading ka bad reputation mostly is wajah se aaya — black-box signal sellers, unverifiable claims, scams. Hum is industry mein viswas wapas laana chahte. Iska matlab harder engineering hamare side, but cleaner conscience. Hum customers ko illusion nahi bechenge.",
        screen_action:
          "Stats panel: # of audit log views per day, # of strategy formulas opened. Then a quote on screen: 'We owe customers transparency, not magic.'",
        b_roll_suggested:
          "Photo of TradeTri team or engineer at desk — adds authenticity",
      },
    ],
    outro:
      "SEBI rules ko hum 'restriction' nahi 'protection' samajhte. Glass Box AI hamara ethical foundation hai — code level pe baked. Agar kabhi koi platform aapko 'guaranteed returns' ka offer de, yad rakhein: illegal hai. TradeTri kabhi nahi karega. Subscribe karein — agla tutorial July 2026 live trading prep pe.",
    total_word_count: 340,
  },

  english_script: {
    intro:
      "Hi, Jayesh here. Today we discuss SEBI compliance and Glass Box AI. This may sound boring, but understanding these two concepts helps you tell safe trading platforms apart from scams. Watch all of it.",
    sections: [
      {
        time_start: 13,
        time_end: 85,
        narration:
          "SEBI — Securities and Exchange Board of India. India's stock-market regulator. A few SEBI rules apply to TradeTri-like platforms. First — return-guarantee claims are illegal. Any platform claiming '99% accuracy' or 'guaranteed monthly returns' is breaking SEBI rules. Second — to give investment advice you need a RIA license. TradeTri is not an RIA — we're a tools provider, not an advisor. That's why AlgoMitra refuses tips.",
        screen_action:
          "SEBI logo and website screenshot. Red-flag montage: scam claims with red X overlay.",
        b_roll_suggested: "Slow pan over actual SEBI circular text",
      },
      {
        time_start: 85,
        time_end: 160,
        narration:
          "Third rule — fund handling. TradeTri never holds customer money. Your funds stay with your broker. We only use API permissions to send orders. If TradeTri shut down tomorrow, your money is safe — because it's at Dhan or Zerodha, not us. Custody risk is zero.",
        screen_action:
          "Flow diagram: User → Broker (funds) ← API permission ← TradeTri (orders only). 'NO FUND CUSTODY' badge.",
        b_roll_suggested:
          "Money animation flowing only user ↔ broker, never touching TradeTri",
      },
      {
        time_start: 160,
        time_end: 230,
        narration:
          "Now Glass Box AI. Other platforms sell 'AI signals' — input goes in, signal comes out, you don't know how. Black box. We reject this approach. Glass Box means every calculation, every indicator value, every signal is auditable. Click on RSI = 65 and you see the formula, the bars used, the exact timestamps. Verify it against your Kite chart. Transparency isn't optional, it's the default.",
        screen_action:
          "TradeTri chart with RSI. Click value. Audit panel: formula, input bars, timestamps. Side-by-side Kite chart with same number.",
        b_roll_suggested:
          "Split screen: Black Box (gears) vs Glass Box (formula)",
      },
      {
        time_start: 230,
        time_end: 270,
        narration:
          "Why does this matter? Because Indian retail trading's bad reputation mostly comes from this — black-box signal sellers, unverifiable claims, scams. We want to bring trust back to this industry. That means harder engineering on our side and a cleaner conscience. We will not sell customers an illusion.",
        screen_action:
          "Stats: daily audit log views, formula opens. Quote: 'We owe customers transparency, not magic.'",
        b_roll_suggested: "Photo of TradeTri team/engineer",
      },
    ],
    outro:
      "We treat SEBI rules as protection, not restriction. Glass Box AI is our ethical foundation — baked into the code. If a platform ever offers you 'guaranteed returns', remember: illegal. TradeTri will never do it. Subscribe — next tutorial is July 2026 live-trading prep.",
    total_word_count: 325,
  },

  thumbnail_text_options: [
    "SEBI + Glass Box explained",
    "Why we'll never offer Tips",
    "Compliance > Hype",
  ],
  hashtags: [
    "#SEBI",
    "#Compliance",
    "#GlassBoxAI",
    "#TradeTri",
    "#IndianStockMarket",
    "#NoTips",
    "#Transparency",
  ],
  target_audience:
    "Indian retail traders trying to understand which platforms to trust",
  prerequisites: [],
};
