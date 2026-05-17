import type { MarketingTemplate } from "../_types";

export const LIVE_TRADING_ANNOUNCEMENT: MarketingTemplate = {
  slug: "telegram-live-trading-announcement",
  platform: "telegram",
  use_case: "Live trading public availability announcement (July 2026)",
  audience: "general",

  content_en: `**Live trading is open** 🟢

Starting today, TradeTri supports live trading on Indian F&O via Zerodha, Dhan, Upstox, ICICI Direct, and Angel One.

HOW IT WORKS
• You connect your existing broker account (read+order permissions)
• You pick a strategy template (or build your own)
• You set capital limit, max position size, and weekly drawdown circuit-breaker
• TradeTri places orders through your broker — your funds never touch us

THE PRICING
• Paper trading: FREE forever
• Live trading: ₹{{monthly_fee}}/month flat. No per-trade, no profit share, no setup fee.
• 60-day money-back if it's not for you

THE HARD RULES (server-enforced, we will NOT override)
• Weekly drawdown circuit-breaker pauses all strategies at -5%
• You set your own capital ceiling per strategy
• Manual override of any signal is logged for your own future review

We waited 14 months and ran 6 months of paper testing across {{paper_user_count}} accounts before turning this on. The patience was deliberate.

Get started: {{onboarding_url}}

— Jayesh, founder
`,
  content_hi: `**Live trading khul gayi** 🟢

Aaj se TradeTri Indian F&O pe live trading support karta hai — Zerodha, Dhan, Upstox, ICICI Direct, aur Angel One ke through.

KAISE KAAM KARTA HAI
• Apna existing broker account connect karein (read+order permissions)
• Strategy template choose karein (ya khud banayein)
• Capital limit, max position size, aur weekly drawdown circuit-breaker set karein
• TradeTri aapke broker se orders place karta — funds hamein kabhi touch nahi karte

PRICING
• Paper trading: FREE hamesha
• Live trading: ₹{{monthly_fee}}/mahina flat. Per-trade nahi, profit share nahi, setup fee nahi.
• 60-day money-back agar pasand na aaye

HARD RULES (server-enforced, hum override NAHI karenge)
• Weekly drawdown circuit-breaker -5% pe sab strategies pause kar deta
• Aap apna capital ceiling khud set karte per strategy
• Manual signal override log hota aapke future review ke liye

Hum ne 14 mahine wait kiya aur {{paper_user_count}} accounts pe 6 mahine paper testing ke baad ye on kiya. Patience deliberate thi.

Start karein: {{onboarding_url}}

— Jayesh, founder
`,

  required_vars: ["monthly_fee", "paper_user_count", "onboarding_url"],
  cta: "Start at {{onboarding_url}}",
  estimated_chars: 1500,
  visuals_suggested: [
    "Founder video (90 sec) explaining 'why we waited so long'",
    "Hero image: TradeTri logo + 'LIVE' badge in tricolour",
    "Broker logos strip showing all 5 supported brokers",
  ],
};
