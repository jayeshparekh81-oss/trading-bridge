import type { MarketingTemplate } from "../_types";

export const LAUNCH_ANNOUNCEMENT: MarketingTemplate = {
  slug: "telegram-launch-announcement",
  platform: "telegram",
  use_case: "Official channel launch announcement on Phase C go-live day",
  audience: "waitlist",

  content_en: `**TradeTri is LIVE.** 🇮🇳

After 14 months of building, we're opening the doors to Indian retail traders.

What TradeTri does:
• Run systematic strategies on NSE F&O without writing code
• 70+ technical indicators in our Glass Box engine (every calculation auditable)
• 50+ ready-to-clone strategy templates calibrated for Indian markets
• Paper-trade unlimited; pay only when you go live
• OAuth-authorized broker connection with full audit trail — your funds stay with your broker

What TradeTri does NOT do:
• Guarantee returns (no one can, ignore anyone who claims they can)
• Take custody of your money
• Front-run your orders

Brokers supported: Zerodha, Dhan, Upstox, ICICI Direct, Angel One.

Live trading opens to vetted accounts in July 2026. Paper is unlimited and free today.

{{landing_url}}

— Jayesh, founder
`,
  content_hi: `**TradeTri LIVE ho gaya.** 🇮🇳

14 mahine ki mehnat ke baad, hum Indian retail traders ke liye doors open kar rahe hain.

TradeTri kya karta hai:
• NSE F&O pe systematic strategies bina code likhe chala sakte ho
• 70+ technical indicators hamare Glass Box engine mein (har calculation auditable)
• 50+ ready-to-clone strategy templates jo Indian markets ke liye calibrated hain
• Unlimited paper-trade karo; paise tabhi do jab live jaao
• OAuth-authorized broker connection full audit trail ke saath — paisa aapke broker ke paas hi rehta hai

TradeTri kya NAHI karta:
• Returns guarantee (koi nahi kar sakta, jo karta hai usse door raho)
• Aapke paise apne paas nahi rakhte
• Aapke orders front-run nahi karte

Brokers: Zerodha, Dhan, Upstox, ICICI Direct, Angel One — sab support.

Live trading July 2026 mein vetted accounts ke liye khulta hai. Paper aaj se unlimited aur free.

{{landing_url}}

— Jayesh, founder
`,

  required_vars: ["landing_url"],
  cta: "Sign up free at {{landing_url}}",
  estimated_chars: 1450,
  visuals_suggested: [
    "TradeTri logo on Tiranga gradient background",
    "Short 15-sec founder video saying 'TradeTri live ho gaya, aaiye'",
    "Screenshot of strategy templates list overlay",
  ],
};
