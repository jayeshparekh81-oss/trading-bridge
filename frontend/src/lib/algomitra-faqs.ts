/**
 * AlgoMitra FAQ knowledge base.
 *
 * 50+ Q&A pairs grouped by category. Each entry has keywords used by a
 * dumb keyword-match scorer (Phase 1A). Phase 1B will swap this for an
 * embedding-based retriever and feed Claude as context.
 */

export type FaqCategory =
  | "broker_setup"
  | "webhooks"
  | "strategies"
  | "orders"
  | "kill_switch"
  | "positions"
  | "errors"
  | "education"
  | "indian_market"
  | "tradetri"
  | "account";

export interface Faq {
  id: string;
  category: FaqCategory;
  question: string;
  answer: string;
  /** Lowercase keywords for the simple keyword-scorer. */
  keywords: readonly string[];
}

export const ALGOMITRA_FAQS: readonly Faq[] = [
  // ─── Broker setup ────────────────────────────────────────────────────
  {
    id: "fyers-connect",
    category: "broker_setup",
    question: "How do I connect my Fyers account?",
    answer:
      "Bhai, Fyers connect karne ke liye:\n1. Fyers Dashboard → My Apps mein jao\n2. Apna App ID copy kar (jaise VZCA6T6Z6O-100)\n3. Same row mein App Secret pe 'Show' click kar\n4. TRADETRI Brokers page → Add Broker → Fyers select kar\n5. Dono values paste kar de — bas itna hi.\n\nAgar 'My Apps' nahi dikh raha toh API access enable nahi hua hoga. Fyers KYC complete hai na?",
    keywords: ["fyers", "connect", "broker", "app id", "app secret", "credentials"],
  },
  {
    id: "dhan-connect",
    category: "broker_setup",
    question: "How to connect Dhan?",
    answer:
      "Dhan ke liye Personal Access Token chahiye:\n1. DhanHQ → My Profile → Access DhanHQ Trading APIs\n2. 'Generate Token' click kar\n3. Token aur Client ID copy kar\n4. TRADETRI mein Dhan select karke paste kar\n\nNote: Dhan ka token expire hota hai. Connection fail ho toh new token generate karna padega.",
    keywords: ["dhan", "connect", "access token", "client id"],
  },
  {
    id: "zerodha-connect",
    category: "broker_setup",
    question: "When will Zerodha be supported?",
    answer:
      "Zerodha Phase 2 mein aa raha hai (timeline: ~6-8 weeks). Kite Connect ka API key + secret use karenge. Tab tak agar tu Zerodha pe hai toh Fyers/Dhan pe paper trading start kar sakta hai — same TradingView setup chalega.",
    keywords: ["zerodha", "kite", "support", "when", "coming"],
  },
  {
    id: "shoonya-connect",
    category: "broker_setup",
    question: "Is Shoonya / Finvasia supported?",
    answer:
      "Shoonya integration roadmap pe hai but priority Phase 2 ke baad hai. Agar urgent zarurat hai toh founder ko WhatsApp kar — jaldi support add ho sakta hai.",
    keywords: ["shoonya", "finvasia", "support"],
  },
  {
    id: "angelone-connect",
    category: "broker_setup",
    question: "Can I use AngelOne / SmartAPI?",
    answer:
      "AngelOne SmartAPI Phase 3 mein planned hai. Currently Fyers aur Dhan production-ready hain. AngelOne use karna hai toh founder ko bata, queue mein priority de denge.",
    keywords: ["angelone", "angel", "smartapi", "support"],
  },
  {
    id: "broker-switch",
    category: "broker_setup",
    question: "Can I use multiple brokers at once?",
    answer:
      "Haan bhai, multiple brokers add kar sakte ho. Ek strategy ek broker se linked hoti hai — toh tu Nifty wala Fyers se aur BankNifty wala Dhan se chala sakta hai. Webhooks separate honge.",
    keywords: ["multiple", "brokers", "switch", "two", "accounts"],
  },
  {
    id: "credentials-secure",
    category: "broker_setup",
    question: "Are my broker credentials safe?",
    answer:
      "Bilkul. Fernet encryption use karte hain (AES-128). Database mein sirf encrypted blob hota hai, plaintext kabhi nahi. Encryption key server pe secure hai, code mein nahi. Agar database leak bhi ho jaye, attacker ko credentials nahi milengi.",
    keywords: ["secure", "safe", "encryption", "credentials", "privacy"],
  },

  // ─── Webhooks ─────────────────────────────────────────────────────────
  {
    id: "webhook-what",
    category: "webhooks",
    question: "What is a webhook URL?",
    answer:
      "Webhook ek URL hai jisko TradingView (ya koi bhi alert system) HTTP POST karta hai. POST mein order details hote hain (BUY NIFTY 25000CE etc.). TRADETRI us alert ko receive karke broker ko forward karta hai — sub-second latency mein.",
    keywords: ["webhook", "what", "url", "tradingview"],
  },
  {
    id: "webhook-create",
    category: "webhooks",
    question: "How do I create a webhook?",
    answer:
      "Webhooks page → 'Create Webhook' → label de (e.g., 'Nifty Scalper'). Tujhe ek unique URL milega aur HMAC secret. Dono copy karle — secret dobara nahi dikhega. URL ko TradingView alert mein paste kar dena.",
    keywords: ["webhook", "create", "new", "make"],
  },
  {
    id: "webhook-test",
    category: "webhooks",
    question: "How do I test my webhook?",
    answer:
      "Webhooks page → apna webhook select kar → 'Test' button. Sample BUY NIFTY payload bhejta hai. Status 200 aaye toh webhook reachable hai. Order actually broker ko bhejna ho toh strategy se link karna padega.",
    keywords: ["webhook", "test", "verify", "check"],
  },
  {
    id: "webhook-hmac",
    category: "webhooks",
    question: "What is HMAC and why do I need it?",
    answer:
      "HMAC (Hash-based Message Authentication Code) ek signature hai jo prove karta hai ki webhook tujhse hi aaya, kisi attacker se nahi. TradingView Pro+ mein HMAC support hai. Free plan mein bhi URL secret token use karke kaam chal jata hai, but HMAC zyada secure hai.",
    keywords: ["hmac", "security", "signature", "auth"],
  },
  {
    id: "webhook-tradingview",
    category: "webhooks",
    question: "How to set webhook in TradingView?",
    answer:
      "TradingView mein:\n1. Alert create kar (right-click chart → Add Alert)\n2. 'Webhook URL' enable kar — apna TRADETRI URL paste kar\n3. Message field mein JSON paste kar:\n{\n  \"action\": \"BUY\",\n  \"symbol\": \"NIFTY25000CE\",\n  \"exchange\": \"NSE\",\n  \"order_type\": \"MARKET\",\n  \"quantity\": 50\n}\n4. Save kar.\n\nAlert fire hone par order TRADETRI through broker pe jayega.",
    keywords: ["tradingview", "webhook", "setup", "alert"],
  },

  // ─── Strategies ───────────────────────────────────────────────────────
  {
    id: "strategy-what",
    category: "strategies",
    question: "What is a strategy in TRADETRI?",
    answer:
      "Strategy = ek webhook + ek broker + risk rules. Strategy webhook se signal leti hai aur broker pe order place karti hai. Tu daily loss limit, allowed symbols, max position size yahan set kar sakta hai.",
    keywords: ["strategy", "what", "definition"],
  },
  {
    id: "strategy-create",
    category: "strategies",
    question: "How do I create a strategy?",
    answer:
      "Strategies page → 'New Strategy'. Naam de (e.g. 'Nifty Scalper'), webhook select kar, broker pick kar, max position size de, allowed symbols list mein NIFTY/BANKNIFTY etc. add kar. Activate kar — bas.",
    keywords: ["strategy", "create", "new"],
  },
  {
    id: "strategy-backtest",
    category: "strategies",
    question: "How can I backtest a strategy?",
    answer:
      "TRADETRI execution layer hai, backtest engine nahi. Backtest TradingView pe Pine Script se kar — wahan se signal generate karke TRADETRI pe forward karna hai. Forward-test (paper mode) yahan possible hai.",
    keywords: ["backtest", "strategy", "test", "history"],
  },
  {
    id: "paper-trade",
    category: "strategies",
    question: "What is paper trading and how do I enable it?",
    answer:
      "Paper trading = real signals, fake orders. Strategy edit → 'Paper Mode' toggle on. Orders log mein dikhenge but broker pe nahi jayenge. 1-2 hafte paper mode mein chala, fir live kar — yeh 15 saal ka rule hai.",
    keywords: ["paper", "trade", "demo", "test"],
  },
  {
    id: "allowed-symbols",
    category: "strategies",
    question: "What are 'allowed symbols'?",
    answer:
      "Whitelist hai. Strategy sirf yeh symbols pe trade karegi. Agar tu sirf NIFTY pe scalper chala raha hai aur galti se RELIANCE ka signal aa gaya, strategy reject kar degi. Critical safety net.",
    keywords: ["allowed", "symbols", "whitelist", "filter"],
  },

  // ─── Orders ──────────────────────────────────────────────────────────
  {
    id: "order-failing",
    category: "orders",
    question: "Why is my order failing?",
    answer:
      "5 common reasons:\n1. Insufficient funds — broker mein paisa nahi\n2. Invalid symbol — symbol format galat (NIFTY25000CE expiry shayad galat hai)\n3. Session expired — broker token refresh kar\n4. Outside market hours — 9:15-15:30 ke baar order reject\n5. Kill switch tripped — daily loss limit hit ho gaya\n\nKaunsa error message dikh raha? Mujhe screenshot bhej, exact diagnose karta hoon.",
    keywords: ["order", "fail", "error", "rejected", "not working"],
  },
  {
    id: "order-types",
    category: "orders",
    question: "What's the difference between MARKET and LIMIT?",
    answer:
      "MARKET = best available price pe instant execute. Slippage ka risk hai but fill guaranteed.\nLIMIT = sirf tere price (ya better) pe execute. Slippage zero but fill nahi bhi ho sakta.\n\nScalping mein MARKET use kar (speed > price), positional mein LIMIT use kar (price > speed).",
    keywords: ["market", "limit", "order", "type", "difference"],
  },
  {
    id: "stop-loss",
    category: "orders",
    question: "What's the difference between SL and SL-M?",
    answer:
      "SL (Stop Loss Limit) — trigger price pe SL active hota hai, fir limit price pe execute. Slippage protected.\nSL-M (Stop Loss Market) — trigger pe market order trigger ho jata hai. Fast execution but slippage possible.\n\nVolatile market mein SL-M lagao (otherwise SL hit hi nahi hoga). Calm market mein SL theek hai.",
    keywords: ["stop loss", "sl", "sl-m", "trigger"],
  },
  {
    id: "square-off",
    category: "orders",
    question: "How do I square off all positions?",
    answer:
      "Positions page → 'Square Off All' button. Ya kill switch trigger kar de. Backend market orders bhejta hai, sab open positions close ho jaate hain. Use sirf emergency mein — slippage market mood pe depend karta hai.",
    keywords: ["square", "off", "close", "positions", "exit"],
  },
  {
    id: "trade-export",
    category: "orders",
    question: "Can I export my trade history?",
    answer:
      "Haan bhai. Trades page → Export button → CSV download ho jata hai. Tax calculation, audit, ya broker pe reconciliation ke liye useful hai.",
    keywords: ["export", "trades", "csv", "history", "download"],
  },

  // ─── Kill switch ─────────────────────────────────────────────────────
  {
    id: "killswitch-what",
    category: "kill_switch",
    question: "What is the kill switch?",
    answer:
      "Kill switch = automatic circuit breaker. Daily loss ya max trades hit ho toh:\n1. Sab pending orders cancel\n2. Sab open positions square off\n3. Naye orders block — agle din tak\n\n15 saal ka lesson: bina kill switch ke koi bhi algo trade nahi karna chahiye. Ek galat day account khaali kar sakta hai.",
    keywords: ["kill switch", "circuit", "stop", "what"],
  },
  {
    id: "killswitch-loss",
    category: "kill_switch",
    question: "How do I set my daily loss limit?",
    answer:
      "Settings → Kill Switch → Max Daily Loss field. Capital ka 2-3% se zyada mat rakh. Example: ₹1L capital pe ₹2-3K limit. Discipline ka sabse bada teacher yahi hai.",
    keywords: ["daily loss", "limit", "kill switch", "max loss"],
  },
  {
    id: "killswitch-trades",
    category: "kill_switch",
    question: "What is max trades per day?",
    answer:
      "Ek din mein max kitne trades execute honge. Overtrading = revenge trading. 15-20 quality trades ek scalper ke liye bahut hain. Settings mein 50 default hai but kam rakhna hi smart hai.",
    keywords: ["max trades", "limit", "overtrade"],
  },
  {
    id: "killswitch-reset",
    category: "kill_switch",
    question: "When does the kill switch reset?",
    answer:
      "Daily 9:00 AM IST pe automatic reset hota hai (market open se 15 min pehle). Manual reset bhi kar sakta hai — but nahi karna chahiye, woh emotional trading ka start hai.",
    keywords: ["reset", "kill switch", "when", "next day"],
  },

  // ─── Positions ───────────────────────────────────────────────────────
  {
    id: "position-size",
    category: "positions",
    question: "How big should my position size be?",
    answer:
      "Risk per trade = capital ka 1-2%. Position size = (Risk per trade) / (entry - stop loss).\nExample: ₹1L capital, 1% risk = ₹1000. Stop loss ₹10 hai. Toh quantity = 1000/10 = 100 units.\n\nSize hamesha SL ke base pe nikaal — gut feel pe kabhi nahi.",
    keywords: ["position size", "quantity", "lot", "how much"],
  },
  {
    id: "holdings-vs-positions",
    category: "positions",
    question: "What's the difference between holdings and positions?",
    answer:
      "Positions = aaj ke open trades (intraday + carry-forward F&O). End-of-day pe close ho sakte hain.\nHoldings = demat mein settled stocks (T+1 ke baad). Long-term store hai.\n\nIntraday ka P&L positions mein dikhta hai, delivery ka holdings mein.",
    keywords: ["positions", "holdings", "difference"],
  },
  {
    id: "pnl-calc",
    category: "positions",
    question: "How is P&L calculated?",
    answer:
      "Realized P&L = closed trades ka profit/loss.\nUnrealized P&L = open positions ka mark-to-market (LTP - avg buy).\nTotal = realized + unrealized.\n\nNote: brokerage + STT + GST nikalta hai gross se. Net P&L hamesha thoda kam dikhega.",
    keywords: ["pnl", "profit", "loss", "calculation"],
  },
  {
    id: "fees",
    category: "positions",
    question: "Are there any TRADETRI fees per trade?",
    answer:
      "TRADETRI fees flat subscription hai (per month). Per trade extra charge nahi. Brokerage broker apni leta hai (Fyers ₹20/order, Dhan ₹20/order intraday). STT, GST, exchange charges separate hain.",
    keywords: ["fees", "charges", "cost", "pricing"],
  },

  // ─── Errors ──────────────────────────────────────────────────────────
  {
    id: "err-session-expired",
    category: "errors",
    question: "Session expired error — what to do?",
    answer:
      "Broker ka access token expire ho gaya. Brokers page jao → broker ke saamne 'Reconnect' button click kar. Fyers ko OAuth login dobara karna padega, Dhan ko fresh access token paste karna hoga.",
    keywords: ["session expired", "expired", "token", "logout"],
  },
  {
    id: "err-insufficient-funds",
    category: "errors",
    question: "Insufficient funds error",
    answer:
      "Broker mein margin nahi hai. Check kar:\n1. Trading account mein paisa hai?\n2. Pending orders se margin block to nahi?\n3. F&O ke liye margin requirement zyada hota hai (specially weekly expiry pe)\n\nSettlement T+1 hota hai — selling ke baad next day funds milte hain.",
    keywords: ["insufficient funds", "margin", "balance"],
  },
  {
    id: "err-invalid-symbol",
    category: "errors",
    question: "Invalid symbol error",
    answer:
      "Symbol format broker ke spec se match nahi kar raha. Examples:\n- NSE equity: RELIANCE-EQ (Fyers), RELIANCE (Dhan)\n- F&O: NIFTY25APR25000CE (correct expiry month + strike + type)\n\nWebhook payload mein exact format match hona chahiye. Doubt ho toh exact symbol mujhe bhej, fix kar deta hoon.",
    keywords: ["invalid symbol", "symbol", "not found"],
  },
  {
    id: "err-rate-limit",
    category: "errors",
    question: "Rate limit error from broker",
    answer:
      "Broker ne 1 second mein bahut zyada orders bhej diye samjha. TRADETRI auto-retry karta hai 100ms-400ms backoff ke saath. Agar fir bhi fail ho raha:\n- Strategy ke webhook firing rate kam kar\n- Multiple strategies ek hi broker pe ho toh consolidate kar\n- 1 minute wait kar, fir try kar",
    keywords: ["rate limit", "throttle", "429", "too many"],
  },
  {
    id: "err-rejected",
    category: "errors",
    question: "Order rejected by broker — why?",
    answer:
      "Broker se order reject hone ke main reasons:\n1. Margin shortage\n2. Stock under ASM/GSM (regulator restrictions)\n3. Lot size galat (F&O lot multiple hona chahiye)\n4. Circuit limit hit (price upper/lower circuit pe hai)\n5. Pre-open / post-close mein market order\n\nReject reason exact dikhao toh fix bata sakta hoon.",
    keywords: ["rejected", "broker", "order", "denied"],
  },

  // ─── Education ───────────────────────────────────────────────────────
  {
    id: "edu-paper-trade",
    category: "education",
    question: "Should I paper trade first?",
    answer:
      "Bhai, MUST. 15 saal ka rule: koi bhi nayi strategy minimum 2 hafte paper mode pe chalao. Real money pe tab jaao jab paper mein consistent profit dikhe. Emotion test only real money pe hota hai but math test paper pe bhi pakka hota hai.",
    keywords: ["paper", "demo", "practice", "first"],
  },
  {
    id: "edu-risk-mgmt",
    category: "education",
    question: "What are the basic risk management rules?",
    answer:
      "🛡️ Risk Management — Trader's biggest weapon!\n\n15 saal me sikha — strategy 20% hai, risk management 80% hai trading me.\n\n3 golden rules:\n\n1. Per Trade Risk: Max 1-2% of capital\n   ₹50,000 capital = ₹500-1000 max risk per trade\n\n2. Daily Loss Limit: Max 5% of capital\n   Hit ho gaya = trading band, kal naya din\n\n3. Position Sizing: Calculate before entry\n   Risk amount ÷ Stop loss points = quantity\n\nYeh 3 rules follow karega toh 1 saal mein bhi blow up nahi karega. Iske bina Day 1 pe blow up possible hai.",
    keywords: ["risk", "management", "rules", "basics"],
  },
  {
    id: "edu-position-sizing",
    category: "education",
    question: "How do I do proper position sizing?",
    answer:
      "📏 Position Sizing — formula simple, discipline tough.\n\nFormula:\n  Quantity = (Capital × Risk%) / (Entry − Stop Loss)\n\nReal example, step-by-step:\n• Capital: ₹2,00,000\n• Per-trade risk: 1% = ₹2,000\n• Entry: ₹100, Stop Loss: ₹80\n• Risk per unit: ₹100 − ₹80 = ₹20\n• Quantity = ₹2,000 / ₹20 = 100 units\n\nWorst case (SL hit): −₹2,000 (1% of capital).\n50 baar lagatar SL hit ho toh bhi capital safe — discipline ka beauty yahi hai.\n\nGut feel pe size mat decide kar — math pe kar.",
    keywords: ["position", "sizing", "quantity"],
  },
  {
    id: "edu-lot-size",
    category: "education",
    question: "What is lot size in F&O?",
    answer:
      "Exchange ke pre-defined units. Tu lot ke multiples mein hi trade kar sakta hai.\nNIFTY: 25 (changes occasionally)\nBANKNIFTY: 15\nFINNIFTY: 25\nStocks: alag-alag (RELIANCE 250, TCS 175 etc.)\n\nLot size NSE site pe check kar — yeh exchange notifications se change hote rehte hain.",
    keywords: ["lot", "size", "fno", "options", "futures"],
  },
  {
    id: "edu-expiry",
    category: "education",
    question: "What is expiry day and weekly expiry?",
    answer:
      "Expiry = derivatives ka end date. Position close ya settle ho jaati hai.\nWeekly: NIFTY/BANKNIFTY/FINNIFTY/MIDCPNIFTY har Tuesday-Friday alag (rotating expiry).\nMonthly: stocks aur indexes ka last Thursday.\n\nExpiry day pe theta decay sabse fast hota hai — option sellers ka favourite, buyers ka enemy.",
    keywords: ["expiry", "weekly", "monthly", "options"],
  },

  // ─── Indian market ────────────────────────────────────────────────────
  {
    id: "ind-muhurat",
    category: "indian_market",
    question: "What is Muhurat trading?",
    answer:
      "Diwali ke din evening 1 hour ka special trading session. Symbolic — naya samvat year start. Bahut log token trade karte hain (1 share). Volatility kam, volume bhi kam. Algo strategies usually pause kar di jaati hain — risk-reward worth nahi hai.",
    keywords: ["muhurat", "diwali", "special"],
  },
  {
    id: "ind-btst",
    category: "indian_market",
    question: "What is BTST?",
    answer:
      "Buy Today Sell Tomorrow. Stock kharid ke next day demat aane se pehle bech do. Some brokers allow karte hain (delivery without T+1 wait). Risk: stock T+1 mein nahi aaye toh auction in delivery — penalty 20% tak.",
    keywords: ["btst", "buy today", "sell tomorrow"],
  },
  {
    id: "ind-t1",
    category: "indian_market",
    question: "What is T+1 settlement?",
    answer:
      "Trade Day + 1 = next working day pe settlement. India mein 2023 se T+1 lagu hai (most efficient global market!). Aaj khareeda toh kal demat mein. Aaj becha toh kal funds available.",
    keywords: ["t+1", "t1", "settlement"],
  },
  {
    id: "ind-mcx",
    category: "indian_market",
    question: "Does TRADETRI support MCX commodities?",
    answer:
      "Symbol-level haan, but practical mein Fyers/Dhan ka MCX feed enable hona chahiye. Most users equity + F&O karte hain. Commodities trade karna hai toh founder ko bata, custom guide bhej deta hoon.",
    keywords: ["mcx", "commodity", "gold", "crude"],
  },

  // ─── TRADETRI specific ───────────────────────────────────────────────
  {
    id: "tt-what",
    category: "tradetri",
    question: "What is TRADETRI?",
    answer:
      "TRADETRI = TradingView signals → Indian brokers ke beech ka bridge. TradingView pe alert fire kare toh sub-second mein broker pe order chala jaata hai. Kill switch, paper mode, multi-broker, audit trail — sab built-in.\n\nTagline: 'Automate without the chaos.'",
    keywords: ["tradetri", "what", "about", "platform"],
  },
  {
    id: "tt-pricing",
    category: "tradetri",
    question: "What does TRADETRI cost?",
    answer:
      "Pricing tiers founder ke saath finalize chal rahi hai (target Q3). Currently early access mein discounted hai. Calendly call book kar — actual numbers wahan share kar denge.",
    keywords: ["price", "cost", "subscription", "fees"],
  },
  {
    id: "tt-uptime",
    category: "tradetri",
    question: "What is the uptime guarantee?",
    answer:
      "Target 99.9% during market hours (9:15-15:30 IST). Infrastructure: AWS Mumbai region, redundant DB, Redis cache, Vercel edge. Real-time status page jaldi launch hoga. Outage ho toh founder ko WhatsApp pe ping kar — direct visibility hai.",
    keywords: ["uptime", "downtime", "reliability", "sla"],
  },
  {
    id: "tt-support",
    category: "tradetri",
    question: "How do I contact support?",
    answer:
      "Teen options:\n1. AlgoMitra (mujhse) — 24/7 yahan available\n2. WhatsApp founder — typical reply <2hrs market hours mein\n3. Calendly call book — 30 min direct slot\n\nUrgent (paisa stuck, order broke) ho toh WhatsApp use kar. Education ya planning ke liye Calendly best hai.",
    keywords: ["support", "contact", "help", "founder"],
  },

  // ─── Account ─────────────────────────────────────────────────────────
  {
    id: "acc-password",
    category: "account",
    question: "How do I change my password?",
    answer:
      "Settings → Profile → Change Password. Old + new password de. Strong password rakh — broker credentials yahan encrypted hain but TRADETRI password attacker ke haath laga toh wo full access pa sakta hai.",
    keywords: ["password", "change", "update"],
  },
  {
    id: "acc-forgot",
    category: "account",
    question: "I forgot my password",
    answer:
      "Login page → 'Forgot Password' link → email enter kar. Reset link 5 min mein aayega. Spam folder bhi check kar. Agar email hi nahi mil raha toh founder ko WhatsApp kar manual reset ke liye.",
    keywords: ["forgot", "password", "reset"],
  },
  {
    id: "acc-2fa",
    category: "account",
    question: "Is 2FA available?",
    answer:
      "TOTP-based 2FA roadmap mein hai (Phase 2). Currently strong password + JWT short expiry use karte hain. 2FA chahiye urgent toh founder ko bol — priority bump kar sakte hain.",
    keywords: ["2fa", "two factor", "totp", "auth"],
  },
  {
    id: "acc-delete",
    category: "account",
    question: "How do I delete my account?",
    answer:
      "Settings → Account → Delete Account. Confirmation ke baad data 30 din mein purge ho jaata hai (compliance window). Trade history CSV download karle pehle — wo dobara nahi milegi.",
    keywords: ["delete", "remove", "close", "account"],
  },
] as const;

/**
 * Cheap keyword scorer. Phase 1B will replace with embeddings.
 * Returns the best-matching FAQ or null if no question scores above 1.
 */
export function findBestFaq(query: string): Faq | null {
  const q = query.toLowerCase();
  let best: { faq: Faq; score: number } | null = null;
  for (const faq of ALGOMITRA_FAQS) {
    let score = 0;
    for (const kw of faq.keywords) {
      if (q.includes(kw)) score += 2;
    }
    // Bonus: substring of the canonical question.
    const qWords = faq.question.toLowerCase().split(/\W+/).filter((w) => w.length > 3);
    for (const w of qWords) if (q.includes(w)) score += 1;
    if (score > 0 && (!best || score > best.score)) best = { faq, score };
  }
  return best && best.score >= 2 ? best.faq : null;
}

export const FAQ_COUNT = ALGOMITRA_FAQS.length;
