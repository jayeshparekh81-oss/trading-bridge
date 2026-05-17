import type { MarketingTemplate } from "../_types";

export const ALGOMITRA_INTRODUCTION: MarketingTemplate = {
  slug: "twitter-algomitra-introduction",
  platform: "twitter",
  use_case: "Tweet introducing AlgoMitra — the in-product AI trading assistant",
  audience: "general",

  content_en: `Meet AlgoMitra — TradeTri's in-product trading assistant.

Powered by Claude. Speaks English, Hindi, Hinglish, Gujarati.

Ask it:
• "Yaar, RSI 70 ke upar kya hota hai?"
• "What's wrong with my paper P&L?"
• "Banknifty Thursday strategy suggest kar"

It explains. It doesn't pump tips. It doesn't claim 99% accuracy. It tells you when a setup is risky.

{{algomitra_url}}
`,
  content_hi: `Miliye AlgoMitra se — TradeTri ka in-product trading assistant.

Claude se powered. English, Hindi, Hinglish, Gujarati — sab samajhta.

Pucho:
• "Yaar, RSI 70 ke upar kya hota hai?"
• "Mere paper P&L mein kya gadbad hai?"
• "Banknifty Thursday strategy suggest kar"

Wo explain karta. Tips nahi deta. 99% accuracy ka jhooth nahi bolta. Setup risky ho to seedha bolta.

{{algomitra_url}}
`,

  required_vars: ["algomitra_url"],
  cta: "Chat with AlgoMitra at {{algomitra_url}}",
  estimated_chars: 480,
  visuals_suggested: [
    "Screen recording of AlgoMitra answering one Hinglish question end-to-end",
    "Static screenshot of chat with example Q&A",
  ],
};
