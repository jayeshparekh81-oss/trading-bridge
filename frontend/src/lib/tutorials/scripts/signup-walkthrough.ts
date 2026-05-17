import type { TutorialScript } from "./_types";

export const SIGNUP_WALKTHROUGH: TutorialScript = {
  topic: "signup-walkthrough",
  duration_target_seconds: 240,

  hindi_script: {
    intro:
      "Namaste, main Jayesh. Aaj main aapko dikhata hu ki TradeTri pe signup kaise karte hain — 60 second mein. Phone ya laptop, dono pe same process. Chaliye start karte hain.",
    sections: [
      {
        time_start: 15,
        time_end: 50,
        narration:
          "Sabse pehle tradetri.com pe jaayein. Top right corner pe Sign Up button hai — usse click karein. Aapko email, password, aur phone number maangega. Indian number daalein kyunki OTP wahin pe aayega. Password 8 character minimum, ek capital, ek number — standard requirements.",
        screen_action:
          "Browser shows tradetri.com homepage. Cursor moves to top-right Sign Up button, clicks. Signup form appears. Type sample email, type password, type 10-digit phone.",
        b_roll_suggested:
          "Indian smartphone close-up showing the SMS app icon, hint that OTP is coming",
      },
      {
        time_start: 50,
        time_end: 100,
        narration:
          "OTP aaya? 6-digit number daalein. Verify ho jaayega. Ab aap account ke andar hain. Pehle dashboard pe hi compliance disclaimer dikhega — usse padhein, kyunki ye SEBI ke rules ke under important hai. 'I understand' click karein.",
        screen_action:
          "Phone shows incoming SMS with 6-digit OTP. Cut back to laptop, OTP being typed. Verification success animation. Dashboard loads, compliance modal appears.",
        b_roll_suggested:
          "Slow-mo of OTP being entered, then a check-mark verification animation",
      },
      {
        time_start: 100,
        time_end: 160,
        narration:
          "Ab aapka account paper trading mode mein hai. Default. Real paisa nahi. Yahan se aap strategy templates dekh sakte ho — left sidebar pe Strategies tab pe click karein. 50+ templates dikhenge. Aapki style ke hisaab se filter kar sakte — beginner, intermediate, advanced. EMA Crossover begineers ke liye sabse simple hai.",
        screen_action:
          "Click left sidebar Strategies. List of strategy templates loads. Hover over filter chips. Click 'Beginner' filter. Cards re-arrange showing beginner-friendly templates.",
        b_roll_suggested:
          "Quick close-up of card details — difficulty score, win rate, capital efficiency",
      },
      {
        time_start: 160,
        time_end: 220,
        narration:
          "Koi bhi template choose karke 'Clone to my account' click karein. Strategy ab aapki ho gayi. Settings adjust kar sakte ho — capital allocation, max position size, stop loss. Save karke 'Start Paper Trade' click karein. Bas! Strategy ab live signals generate karegi paper mode mein.",
        screen_action:
          "Click EMA Crossover card. Detail page. Click 'Clone'. Settings form. Adjust capital ₹1L, max position 10%. Save. Click 'Start Paper Trade'. Confirmation modal.",
        b_roll_suggested:
          "Side-by-side comparison of paper-mode banner vs (greyed out) live-mode banner",
      },
    ],
    outro:
      "Bas. 60 second mein TradeTri pe account ban gaya, strategy clone ho gayi, paper trading start ho gayi. Koi bhi sawaal ho to comments mein puchein — main personally reply karta hu. Aur agar useful laga to subscribe karein, hum har hafta naya tutorial daalte hain.",
    total_word_count: 290,
  },

  english_script: {
    intro:
      "Hi, I'm Jayesh. Today I'll show you how to sign up on TradeTri in 60 seconds. Phone or laptop, same process either way. Let's get into it.",
    sections: [
      {
        time_start: 12,
        time_end: 48,
        narration:
          "First, go to tradetri.com. Top right corner has the Sign Up button — click it. You'll need to enter your email, a password, and your phone number. Use an Indian number because the OTP goes there. Password is 8 characters minimum, one capital letter, one number — standard rules.",
        screen_action:
          "Browser shows tradetri.com. Cursor moves to top-right Sign Up button, clicks. Signup form appears. Sample email, password, 10-digit phone entered.",
        b_roll_suggested: "Close-up of Indian phone screen showing SMS app icon",
      },
      {
        time_start: 48,
        time_end: 95,
        narration:
          "OTP arrived? Enter the 6-digit code. You're verified. You're now inside the account. The first thing you'll see is a compliance disclaimer — read it. It's important under SEBI rules and we don't bury it. Click 'I understand' to continue.",
        screen_action:
          "Phone shows incoming SMS with 6-digit OTP. Cut to laptop, OTP entered. Verified animation. Dashboard loads with compliance modal.",
        b_roll_suggested:
          "Slow zoom on the OTP entry field, then a green check-mark animation",
      },
      {
        time_start: 95,
        time_end: 155,
        narration:
          "Your account is in paper-trading mode by default. No real money. From here you can browse strategy templates — click Strategies in the left sidebar. You'll see 50-plus templates. Filter by your style: beginner, intermediate, advanced. EMA Crossover is the simplest one to start with.",
        screen_action:
          "Click left sidebar Strategies. Template list loads. Hover filter chips. Click 'Beginner'. Cards rearrange.",
        b_roll_suggested:
          "Quick close-up of one card's stats: difficulty, win rate, capital efficiency",
      },
      {
        time_start: 155,
        time_end: 215,
        narration:
          "Pick any template and click 'Clone to my account'. The strategy is now yours. Adjust the settings — capital allocation, max position size, stop loss. Save, click 'Start Paper Trade'. That's it. The strategy will now generate live signals in paper mode.",
        screen_action:
          "Click EMA Crossover. Detail page. Click Clone. Settings form. Adjust capital ₹1L, max position 10%. Save. Start Paper Trade. Confirmation modal.",
        b_roll_suggested:
          "Side-by-side: paper-mode banner vs (greyed out) live-mode banner",
      },
    ],
    outro:
      "That's it. In 60 seconds you've created an account, cloned a strategy, and started paper trading. If you have any questions, drop them in comments — I personally reply. And if this was useful, subscribe — we drop a new tutorial every week.",
    total_word_count: 270,
  },

  thumbnail_text_options: [
    "Signup in 60 seconds",
    "TradeTri Pehla Step",
    "Account → Strategy → Paper Trade",
  ],
  hashtags: [
    "#TradeTri",
    "#PaperTrading",
    "#NSEFO",
    "#IndianStockMarket",
    "#AlgoTrading",
    "#StockMarketIndia",
  ],
  target_audience: "First-time TradeTri visitors who haven't signed up yet",
  prerequisites: ["Indian phone number (for OTP)", "Email address"],
};
