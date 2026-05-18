import type { MarketingTemplate } from "../_types";

export const FEATURE_CAROUSEL_1: MarketingTemplate = {
  slug: "instagram-feature-carousel-1",
  platform: "instagram",
  use_case: "10-slide carousel introducing TradeTri's main features",
  audience: "general",

  content_en: `Caption:
"Indian retail traders deserve the same tools hedge funds use. We built TradeTri to close that gap. Swipe through 👉

#TradeTri #IndianStockMarket #NSEFO #TradingTools #SystematicTrading #PaperTrading"

Slide-by-slide content:

SLIDE 1 (Cover): "10 things you didn't know retail traders could do"
SLIDE 2: "Run systematic strategies. No code required."
SLIDE 3: "70+ indicators. Glass Box — every calculation auditable."
SLIDE 4: "50+ ready-to-clone templates calibrated for Indian markets"
SLIDE 5: "Paper-trade unlimited. Free forever."
SLIDE 6: "Secure OAuth broker integration. Your funds stay with your broker."
SLIDE 7: "AlgoMitra: ask questions in Hindi/English/Hinglish/Gujarati"
SLIDE 8: "Flat pricing: ₹{{monthly_fee}}/month live. No per-trade, no profit share."
SLIDE 9: "Brokers: Zerodha, Dhan, Upstox, ICICI Direct, Angel One"
SLIDE 10 (CTA): "Start free at tradetri.com — paper account in 60 seconds"
`,
  content_hi: `Caption:
"Indian retail traders ko bhi wahi tools deserve karte jo hedge funds use karte. Hum ne TradeTri banaya yahi gap close karne ke liye. Swipe karein 👉

#TradeTri #IndianStockMarket #NSEFO #TradingTools #SystematicTrading #PaperTrading"

Slide-by-slide:

SLIDE 1 (Cover): "Retail traders 10 cheezein kar sakte jo unhe nahi pata"
SLIDE 2: "Systematic strategies chalao. Code nahi chahiye."
SLIDE 3: "70+ indicators. Glass Box — har calculation auditable."
SLIDE 4: "50+ ready-to-clone templates Indian markets ke liye calibrated"
SLIDE 5: "Paper-trade unlimited. Hamesha free."
SLIDE 6: "Secure OAuth broker integration. Funds broker ke paas hi rehte."
SLIDE 7: "AlgoMitra: Hindi/English/Hinglish/Gujarati mein puchein"
SLIDE 8: "Flat pricing: ₹{{monthly_fee}}/mahina live. Per-trade nahi, profit share nahi."
SLIDE 9: "Brokers: Zerodha, Dhan, Upstox, ICICI Direct, Angel One"
SLIDE 10 (CTA): "Free start tradetri.com pe — paper account 60 second mein"
`,

  required_vars: ["monthly_fee"],
  cta: "Start free at tradetri.com",
  estimated_chars: 1500,
  visuals_suggested: [
    "Consistent visual: Tiranga gradient on top stripe, white slide body, brand logo bottom-right",
    "Slide 7 (AlgoMitra): screenshot of chat in Hindi",
    "Slide 9: 5 broker logos arranged horizontally",
    "Slide 10: large CTA button visual + URL",
  ],
};
