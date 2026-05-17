import type { MarketingTemplate } from "../_types";

export const LAUNCH_THREAD: MarketingTemplate = {
  slug: "twitter-launch-thread",
  platform: "twitter",
  use_case: "5-tweet launch announcement thread",
  audience: "general",

  content_en: `1/5 🇮🇳 TradeTri is live today.

A systematic trading platform for Indian retail traders. No code required. NSE F&O. Read-only broker connection (Zerodha, Dhan, Upstox, ICICI, Angel One).

What that means in plain English 👇

2/5 You pick a strategy template. Or build your own from 70+ indicators.

You paper-trade it for as long as you want. Free, unlimited.

When you're ready, you flip it to live and our engine places real orders through your broker. Funds never touch us.

3/5 Why we built this:

Hedge funds run systematic strategies. Retail traders watch screens.

The gap isn't intelligence — it's execution infrastructure. TradeTri is the execution layer for Indian retail, calibrated for NSE F&O specifically.

4/5 What we WON'T do:

❌ Guarantee returns (ignore anyone who does)
❌ Hold your money (it stays with your broker)
❌ Front-run your orders (you can audit every signal and order in real time — Glass Box)

5/5 Live trading is fee-flat ₹{{monthly_fee}}/month. No per-trade, no profit share.

Paper is free forever.

60-day money-back.

Start: {{landing_url}}

— Jayesh, founder (L&T engineer, 14 months on this)
`,
  content_hi: `1/5 🇮🇳 TradeTri aaj live ho gaya.

Indian retail traders ke liye systematic trading platform. Code nahi chahiye. NSE F&O. Read-only broker connection (Zerodha, Dhan, Upstox, ICICI, Angel One).

Iska plain matlab 👇

2/5 Aap strategy template choose karte. Ya 70+ indicators se khud banate.

Jab tak chaaho paper-trade karo. Free, unlimited.

Ready ho jaao to live kar do — hamara engine aapke broker se real orders place karta. Funds hamein kabhi touch nahi karte.

3/5 Kyun banaya:

Hedge funds systematic strategies chalaate. Retail traders screen dekhte rehte.

Gap intelligence ka nahi — execution infrastructure ka hai. TradeTri Indian retail ka execution layer hai, NSE F&O ke liye specifically calibrated.

4/5 Hum kya NAHI karenge:

❌ Returns guarantee (jo karta hai usse door raho)
❌ Aapka paisa rakhna (broker ke paas rehta)
❌ Aapke orders front-run karna (har signal aur order aap real time mein audit kar sakte — Glass Box)

5/5 Live trading fee flat ₹{{monthly_fee}}/mahina. Per-trade nahi, profit share nahi.

Paper hamesha free.

60-day money-back.

Start: {{landing_url}}

— Jayesh, founder (L&T engineer, 14 mahine is pe lage)
`,

  required_vars: ["monthly_fee", "landing_url"],
  cta: "Start at {{landing_url}}",
  estimated_chars: 1400,
  visuals_suggested: [
    "Tweet 1: TradeTri logo on Tiranga gradient",
    "Tweet 2: Short product GIF of strategy template clone",
    "Tweet 3: Comparison table — Hedge Fund vs TradeTri user",
    "Tweet 4: 'Glass Box' visual showing audit log preview",
    "Tweet 5: Pricing card with all numbers",
  ],
};
