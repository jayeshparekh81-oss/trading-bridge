import type { TutorialScript } from "./_types";

export const ALGOMITRA_INTRO: TutorialScript = {
  topic: "algomitra-intro",
  duration_target_seconds: 260,

  hindi_script: {
    intro:
      "Namaste, Jayesh hu. Aaj mil te hain AlgoMitra se — TradeTri ka in-product AI assistant. Claude pe based, English/Hindi/Hinglish/Gujarati samajhta. Iska role kya, kaise use karein, aur kya NAHI poochna chahiye — ye dikhata hu.",
    sections: [
      {
        time_start: 12,
        time_end: 70,
        narration:
          "Dashboard pe bottom right corner mein floating button hai 'AlgoMitra'. Click karein. Chat window khulta. Pehli baar khologe to wo apna intro deta — naam, kya kar sakta hai, language preference. Aap Hindi mein chat shuru karein to wo Hindi mein hi respond karta. Mixed Hinglish bhi samajhta — 'yaar mera RSI kyu confused hai' wala questions.",
        screen_action:
          "Dashboard with bottom-right floating AlgoMitra button. Click. Chat window slides up. Greeting message in EN. User types 'namaste, hindi mein baat karte hain'. AlgoMitra switches to Hindi.",
        b_roll_suggested:
          "Multi-language chat bubbles floating — EN, HI, Hinglish, Gujarati — to show range",
      },
      {
        time_start: 70,
        time_end: 145,
        narration:
          "Kya pooch sakte ho? Teen categories. Concept questions — 'RSI 70 ke upar kya hota hai', 'breakout kya hota hai'. Strategy questions — 'meri current strategy ka P&L kyu negative hai', 'BANKNIFTY ke liye konsi template recommend karoge'. Workflow questions — 'paper trade kaise start karu', 'Dhan disconnect kaise karu'. Sab teeno mein wo accha kaam karta.",
        screen_action:
          "Three example chats side by side. First: 'RSI > 70 means?' with explanation. Second: 'Why is my P&L negative?' with analysis. Third: 'How to disconnect Dhan?' with step-by-step.",
        b_roll_suggested: "Quick-cut montage of AlgoMitra answering each type",
      },
      {
        time_start: 145,
        time_end: 215,
        narration:
          "Kya NAHI poochna chahiye? Sabse important baat — TIPS mat poochain. 'Kal NIFTY kahaan jaayega' poochoge to wo seedha mana kar dega. Hum AlgoMitra ko explicit instruct kiya hai — koi price prediction nahi, koi 'buy this now' nahi. Wo strategy explain kar sakta, mistakes point out kar sakta, but tips deny karta. Yahi ethical line hai jo hum kabhi cross nahi karenge.",
        screen_action:
          "User types: 'Kal NIFTY 22500 cross karega?'. AlgoMitra response: 'Main price predict nahi karta. But agar aap kal ke liye setup banana chahte to ye 3 strategies useful ho sakti...'",
        b_roll_suggested:
          "On-screen text: 'No tips. No predictions. Only explanations.' in bold",
      },
      {
        time_start: 215,
        time_end: 250,
        narration:
          "AlgoMitra free tier sab users ke liye available hai with daily limit. Heavy usage ke liye Pro mein unlimited. Conversation history saved rehti tumhare account mein — wapas kabhi bhi reference kar sakte. Yahi tutorial baad mein bhi yaad reh sakta agar AlgoMitra se bola 'remind me what we discussed about EMA'.",
        screen_action:
          "Conversation history panel. Past chats listed by date. Click one — full thread loads.",
        b_roll_suggested:
          "Calendar-style chat history UI with searchable past topics",
      },
    ],
    outro:
      "AlgoMitra aapka trading companion hai, financial advisor nahi. Use it for learning, debugging, workflow help — not for tips. Subscribe karein, agla tutorial SEBI compliance aur Glass Box AI explainer hai.",
    total_word_count: 310,
  },

  english_script: {
    intro:
      "Hi, Jayesh here. Today we meet AlgoMitra — TradeTri's in-product AI assistant. Built on Claude, understands English, Hindi, Hinglish, Gujarati. What it does, how to use it, and what NOT to ask — let me show you.",
    sections: [
      {
        time_start: 13,
        time_end: 70,
        narration:
          "Bottom-right corner of the dashboard has a floating AlgoMitra button. Click it. Chat window opens. First time you open it, it introduces itself — name, capabilities, language preference. Start chatting in Hindi and it responds in Hindi. Mixed Hinglish works too — 'yaar mera RSI kyu confused hai' style questions.",
        screen_action:
          "Dashboard, click AlgoMitra. Chat opens in EN. User types 'namaste, hindi mein baat karte hain'. Switches to Hindi.",
        b_roll_suggested: "Multi-language chat bubbles floating",
      },
      {
        time_start: 70,
        time_end: 145,
        narration:
          "What can you ask? Three categories. Concept questions — 'what does RSI above 70 mean', 'what's a breakout'. Strategy questions — 'why is my P&L negative', 'recommend a template for BANKNIFTY'. Workflow questions — 'how to start paper trade', 'how to disconnect Dhan'. AlgoMitra handles all three well.",
        screen_action:
          "Three example chats. RSI explanation. P&L analysis. Dhan disconnect steps.",
        b_roll_suggested: "Quick-cut montage of each type answered",
      },
      {
        time_start: 145,
        time_end: 215,
        narration:
          "What NOT to ask — and this is critical — no TIPS. Ask 'where will NIFTY go tomorrow' and AlgoMitra will refuse. We explicitly instruct it: no price predictions, no 'buy this now' calls. It will explain strategies, point out mistakes, but it denies tips. That's the ethical line we will never cross.",
        screen_action:
          "User asks: 'Will NIFTY cross 22500 tomorrow?'. AlgoMitra: 'I don't predict prices. But if you're building a setup for tomorrow, these 3 strategies may help…'",
        b_roll_suggested:
          "On-screen bold text: 'No tips. No predictions. Only explanations.'",
      },
      {
        time_start: 215,
        time_end: 250,
        narration:
          "AlgoMitra free tier is available to all users with a daily limit. Pro gives unlimited. Your conversation history is saved on your account — you can always go back. Even this tutorial later: just say 'remind me what we discussed about EMA' and AlgoMitra recalls it.",
        screen_action:
          "Conversation history panel. Past chats. Click one — full thread loads.",
        b_roll_suggested: "Searchable chat history UI",
      },
    ],
    outro:
      "AlgoMitra is your trading companion — not a financial advisor. Use it for learning, debugging, workflow help — never for tips. Subscribe — next tutorial is SEBI compliance and Glass Box AI.",
    total_word_count: 300,
  },

  thumbnail_text_options: [
    "Meet AlgoMitra",
    "AI Assistant — No Tips",
    "Hindi/EN/Gujarati Trading Help",
  ],
  hashtags: [
    "#AlgoMitra",
    "#TradeTri",
    "#AIAssistant",
    "#ClaudeAI",
    "#IndianStockMarket",
    "#NoTipsHere",
  ],
  target_audience: "All TradeTri users discovering in-product help features",
  prerequisites: ["TradeTri account"],
};
