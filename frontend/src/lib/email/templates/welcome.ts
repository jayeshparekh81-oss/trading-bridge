import type { EmailTemplate } from "./_types";

export const WELCOME: EmailTemplate = {
  slug: "welcome",
  name: "Welcome (signup confirmation)",
  category: "welcome",

  subject_en: "Welcome to TradeTri, {{user_name}} — start with paper trading",
  subject_hi: "TradeTri mein swagat hai, {{user_name}} — paper trading se start karein",

  body_en: `Hi {{user_name}},

Welcome to TradeTri. We built this for retail traders who want to run real strategies systematically — without spending years coding execution.

Here's what to do this week:

1. Connect your broker (we support Zerodha, Dhan, Upstox, ICICI Direct, Angel One). Connection is read-only first.
2. Pick a strategy template that matches your style. We recommend EMA Crossover or RSI Oversold Bounce for beginners.
3. Paper-trade for at least 4 weeks before going live. Paper is FREE and simulates fills using the same Pine signals you'd act on in live — close-of-bar pricing, realistic but not tick-level.

We won't push you to go live early. Markets reward patience, and so does our product.

If you get stuck, reply to this email and a human will respond within 24 hours.

— Team TradeTri
{{support_email}}
`,
  body_hi: `Namaste {{user_name}},

TradeTri mein swagat hai. Hum ne ye retail traders ke liye banaya jo real strategies systematically run karna chahte hain — bina execution coding karne mein saalon waste kiye.

Is hafte kya karein:

1. Apna broker connect karein (Zerodha, Dhan, Upstox, ICICI Direct, Angel One support karte hain). Connection pehle read-only hota hai.
2. Apni style ke hisaab se strategy template choose karein. Beginners ke liye EMA Crossover ya RSI Oversold Bounce recommend karte hain.
3. Live jaane se pehle kam se kam 4 hafte paper-trade karein. Paper FREE hai aur Pine signals ke saath fills simulate karta — close-of-bar pricing, realistic but tick-level nahi.

Hum aapko jaldi live nahi karayenge. Markets patience ko reward karte hain — aur hamara product bhi.

Stuck ho jaayein to is email ka reply kar dein, ek insaan 24 hours mein response dega.

— Team TradeTri
{{support_email}}
`,

  required_vars: ["user_name", "support_email"],
};
