import type { MarketingTemplate } from "../_types";

export const EDUCATIONAL_REEL_SCRIPTS: MarketingTemplate = {
  slug: "instagram-educational-reel-scripts",
  platform: "instagram",
  use_case: "5 short reel scripts (30-45 sec each) explaining one trading concept each",
  audience: "general",

  content_en: `REEL 1 — "What is paper trading? (30s)"
Hook (0-3s): "₹0 risk, real market data, unlimited practice."
Body (3-25s): "Paper trading means your strategy runs on real NSE prices but with fake money. You see the same signals you'd see live. You see the same losses. You feel the same FOMO. But your bank account is untouched. On TradeTri, paper is unlimited and free forever."
CTA (25-30s): "Start paper-trading at tradetri.com"

REEL 2 — "Why win rate is overrated (40s)"
Hook (0-3s): "A 90% win rate strategy can still lose money. Here's why."
Body (3-35s): "Imagine you win 9 of 10 trades, each making ₹100. The 10th trade loses ₹1500. Net: -₹600. The math problem isn't WIN RATE — it's RISK/REWARD RATIO. A 45% win rate strategy with R:R 1:3 makes more money than 90% win rate with R:R 1:0.2. We teach customers to look at BOTH on every strategy."
CTA: "TradeTri shows both for every template. Free to explore."

REEL 3 — "RSI in 30 seconds"
Hook: "RSI explained without a single equation."
Body: "RSI = how strong is the recent move? Scale: 0 to 100. Above 70 = lots of buying recently (overbought). Below 30 = lots of selling recently (oversold). Common mistake: 'overbought' doesn't mean 'short it.' Strong trends stay overbought for many days. RSI is one input, not a tip."
CTA: "Learn 70 more indicators with full audit at tradetri.com"

REEL 4 — "Why we won't guarantee returns (35s)"
Hook: "Other platforms claim 95% accuracy. We don't. Here's why."
Body: "Anyone guaranteeing returns is either lying, illegal (SEBI bans return-guarantee claims), or both. Markets are stochastic — even the best strategy has losing months. What we DO promise: transparent calculations, no profit share, no per-trade fee, your funds stay with your broker. Honesty over hype."
CTA: "TradeTri, calmly. tradetri.com"

REEL 5 — "How brokers connect to TradeTri (40s)"
Hook: "Will TradeTri see my bank balance? No. Here's how."
Body: "When you connect Zerodha/Dhan/Upstox/ICICI/Angel One, you grant TradeTri an API permission. We can see: your positions, P&L, place orders. We CANNOT see: your bank, your funds movement, your other accounts. You can revoke permission from your broker side anytime. Your money never leaves your broker. We are a tools provider, not a custodian."
CTA: "Read-only by default. tradetri.com"
`,
  content_hi: `REEL 1 — "Paper trading kya hai? (30s)"
Hook (0-3s): "₹0 risk, real market data, unlimited practice."
Body (3-25s): "Paper trading ka matlab aapki strategy real NSE prices pe chalti hai but fake paise se. Wahi signals dekhoge jo live mein dikhte. Wahi losses dikhte. Wahi FOMO feel hota. But bank account untouched. TradeTri pe paper unlimited aur hamesha free."
CTA (25-30s): "Paper start karein tradetri.com pe"

REEL 2 — "Win rate overrated kyun (40s)"
Hook (0-3s): "90% win rate strategy bhi paise lose kar sakti. Kyun batata hu."
Body (3-35s): "Maan lo 10 mein se 9 trades jeete, har ek ₹100 ka. 10wa trade ₹1500 lose. Net: -₹600. Math problem WIN RATE ki nahi — RISK/REWARD RATIO ki hai. 45% win rate R:R 1:3 ke saath 90% win rate R:R 1:0.2 se zyada paisa banata. Hum customers ko dono dikhana sikhate har strategy pe."
CTA: "TradeTri har template ke liye dono dikhata. Free to explore."

REEL 3 — "RSI 30 second mein"
Hook: "RSI samjhao bina equation ke."
Body: "RSI = recent move kitna strong hai? Scale: 0 se 100. 70 ke upar = recently bahut buying (overbought). 30 ke neeche = recently bahut selling (oversold). Common galti: 'overbought' ka matlab 'short maaro' nahi. Strong trends overbought rehte hain kai din tak. RSI ek input hai, tip nahi."
CTA: "Aur 70 indicators full audit ke saath tradetri.com pe"

REEL 4 — "Hum returns guarantee kyun nahi karte (35s)"
Hook: "Doosre platforms 95% accuracy claim karte. Hum nahi. Kyun batata hu."
Body: "Jo returns guarantee karta wo ya jhooth bol raha ya illegal hai (SEBI return-guarantee claims ban karta) ya dono. Markets stochastic hain — best strategy ke bhi losing months hote. Hum kya PROMISE karte: transparent calculations, profit share nahi, per-trade fee nahi, paisa broker ke paas. Hype se zyada honesty."
CTA: "TradeTri, shanti se. tradetri.com"

REEL 5 — "Brokers TradeTri se kaise connect hote (40s)"
Hook: "TradeTri mera bank balance dekh paayega? Nahi. Yahan dekho."
Body: "Jab Zerodha/Dhan/Upstox/ICICI/Angel One connect karte, aap TradeTri ko API permission dete. Hum dekh sakte: aapki positions, P&L, orders place karna. Hum NAHI dekh sakte: bank, funds movement, doosre accounts. Permission broker side se kabhi bhi revoke kar sakte. Paisa broker se kabhi nahi nikalta. Hum tools provider hain, custodian nahi."
CTA: "Read-only by default. tradetri.com"
`,

  required_vars: [],
  cta: "tradetri.com",
  estimated_chars: 3200,
  visuals_suggested: [
    "Each reel: vertical 9:16, founder voice-over, captions burned in (auto-read sound-off)",
    "REEL 2: animated bar chart showing the win-rate math live",
    "REEL 3: RSI scale graphic with the 30/70 zones colour-coded",
    "REEL 5: animated diagram of permission flow user → TradeTri → broker",
  ],
};
