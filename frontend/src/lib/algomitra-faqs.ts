/**
 * AlgoMitra FAQ knowledge base.
 *
 * 50+ Q&A pairs grouped by category. Each entry has keywords used by a
 * dumb keyword-match scorer, plus per-language answers. Free tier
 * supports 4 languages: en / hi (Devanagari) / gu (Gujarati script) /
 * hinglish. Hinglish is the required default — all entries have it.
 *
 * The 15 highest-volume FAQs (broker setup, common errors, kill
 * switch, risk basics, TRADETRI intro, support) carry full en + hi +
 * gu translations. Lower-volume entries fall back to Hinglish — the
 * universal Indian middle-ground we've validated. Phase 1B Pro tier
 * (Claude Sonnet 4.6) will cover the long tail dynamically.
 *
 * Translation quality note: Hindi and Gujarati translations were
 * produced by Claude. They read naturally but are not native-edited.
 * Items flagged ``// REVIEW:`` need a native-speaker pass before they
 * land in customer-facing copy at scale. Tag a native reviewer when
 * shipping the multi-language announcement.
 */

import type { Language } from "./language-detector";

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

export interface FaqAnswers {
  /** Required default — used when a translation is missing. */
  hinglish: string;
  en?: string;
  hi?: string;
  gu?: string;
}

export interface Faq {
  id: string;
  category: FaqCategory;
  question: string;
  answers: FaqAnswers;
  /** Lowercase keywords for the simple keyword-scorer. */
  keywords: readonly string[];
}

/** Pick the best answer for the detected language with Hinglish fallback. */
export function getFaqAnswer(faq: Faq, lang: Language): string {
  return faq.answers[lang] ?? faq.answers.hinglish;
}

export const ALGOMITRA_FAQS: readonly Faq[] = [
  // ─── Broker setup ────────────────────────────────────────────────────
  {
    id: "fyers-connect",
    category: "broker_setup",
    question: "How do I connect my Fyers account?",
    answers: {
      hinglish:
        "Bhai, Fyers connect karne ke liye:\n1. Fyers Dashboard → My Apps mein jao\n2. Apna App ID copy kar (jaise VZCA6T6Z6O-100)\n3. Same row mein App Secret pe 'Show' click kar\n4. TRADETRI Brokers page → Add Broker → Fyers select kar\n5. Dono values paste kar de — bas itna hi.\n\nAgar 'My Apps' nahi dikh raha toh API access enable nahi hua hoga. Fyers KYC complete hai na?",
      en: "To connect Fyers:\n1. Go to Fyers Dashboard → My Apps\n2. Copy your App ID (e.g. VZCA6T6Z6O-100)\n3. Click 'Show' on App Secret in the same row\n4. TRADETRI Brokers page → Add Broker → select Fyers\n5. Paste both values. Done.\n\nIf 'My Apps' isn't visible, API access isn't enabled — confirm your Fyers KYC is complete.",
      hi: "Fyers जोड़ने के लिए:\n1. Fyers Dashboard → My Apps में जाओ\n2. अपना App ID copy करो (जैसे VZCA6T6Z6O-100)\n3. उसी row में App Secret पर 'Show' click करो\n4. TRADETRI Brokers page → Add Broker → Fyers select करो\n5. दोनों values paste कर दो — बस इतना ही।\n\nअगर 'My Apps' नहीं दिख रहा तो API access enable नहीं हुआ होगा। Fyers KYC complete है ना?",
      gu: "Fyers જોડવા માટે:\n1. Fyers Dashboard → My Apps માં જાવ\n2. તમારી App ID copy કરો (જેમ કે VZCA6T6Z6O-100)\n3. એ જ row માં App Secret પર 'Show' click કરો\n4. TRADETRI Brokers page → Add Broker → Fyers select કરો\n5. બંને values paste કરી દો — બસ આટલું જ.\n\nજો 'My Apps' નથી દેખાતું તો API access enable નથી થયું. Fyers KYC પૂરી થઈ છે ને?",
    },
    keywords: ["fyers", "connect", "broker", "app id", "app secret", "credentials", "जोड़", "ફાયર્સ", "જોડ"],
  },
  {
    id: "dhan-connect",
    category: "broker_setup",
    question: "How to connect Dhan?",
    answers: {
      hinglish:
        "Dhan ke liye Personal Access Token chahiye:\n1. DhanHQ → My Profile → Access DhanHQ Trading APIs\n2. 'Generate Token' click kar\n3. Token aur Client ID copy kar\n4. TRADETRI mein Dhan select karke paste kar\n\nNote: Dhan ka token expire hota hai. Connection fail ho toh new token generate karna padega.",
      en: "Dhan needs a Personal Access Token:\n1. DhanHQ → My Profile → Access DhanHQ Trading APIs\n2. Click 'Generate Token'\n3. Copy the Token + Client ID\n4. In TRADETRI, select Dhan and paste both\n\nNote: Dhan tokens expire. If the connection fails, generate a new token.",
      hi: "Dhan के लिए Personal Access Token चाहिए:\n1. DhanHQ → My Profile → Access DhanHQ Trading APIs\n2. 'Generate Token' click करो\n3. Token और Client ID copy करो\n4. TRADETRI में Dhan select करके paste करो\n\nNote: Dhan का token expire होता है। Connection fail हो तो नया token generate करना पड़ेगा।",
      gu: "Dhan માટે Personal Access Token જોઈએ:\n1. DhanHQ → My Profile → Access DhanHQ Trading APIs\n2. 'Generate Token' click કરો\n3. Token અને Client ID copy કરો\n4. TRADETRI માં Dhan select કરીને paste કરો\n\nNote: Dhan નો token expire થાય છે. Connection fail થાય તો નવો token generate કરવો પડશે.",
    },
    keywords: ["dhan", "connect", "access token", "client id"],
  },
  {
    id: "zerodha-connect",
    category: "broker_setup",
    question: "When will Zerodha be supported?",
    answers: {
      hinglish:
        "Zerodha Phase 2 mein aa raha hai (timeline: ~6-8 weeks). Kite Connect ka API key + secret use karenge. Tab tak agar tu Zerodha pe hai toh Fyers/Dhan pe paper trading start kar sakta hai — same TradingView setup chalega.",
    },
    keywords: ["zerodha", "kite", "support", "when", "coming"],
  },
  {
    id: "shoonya-connect",
    category: "broker_setup",
    question: "Is Shoonya / Finvasia supported?",
    answers: {
      hinglish:
        "Shoonya integration roadmap pe hai but priority Phase 2 ke baad hai. Agar urgent zarurat hai toh founder ko WhatsApp kar — jaldi support add ho sakta hai.",
    },
    keywords: ["shoonya", "finvasia", "support"],
  },
  {
    id: "angelone-connect",
    category: "broker_setup",
    question: "Can I use AngelOne / SmartAPI?",
    answers: {
      hinglish:
        "AngelOne SmartAPI Phase 3 mein planned hai. Currently Fyers aur Dhan production-ready hain. AngelOne use karna hai toh founder ko bata, queue mein priority de denge.",
    },
    keywords: ["angelone", "angel", "smartapi", "support"],
  },
  {
    id: "broker-switch",
    category: "broker_setup",
    question: "Can I use multiple brokers at once?",
    answers: {
      hinglish:
        "Haan bhai, multiple brokers add kar sakte ho. Ek strategy ek broker se linked hoti hai — toh tu Nifty wala Fyers se aur BankNifty wala Dhan se chala sakta hai. Webhooks separate honge.",
    },
    keywords: ["multiple", "brokers", "switch", "two", "accounts"],
  },
  {
    id: "credentials-secure",
    category: "broker_setup",
    question: "Are my broker credentials safe?",
    answers: {
      hinglish:
        "Bilkul. Fernet encryption use karte hain (AES-128). Database mein sirf encrypted blob hota hai, plaintext kabhi nahi. Encryption key server pe secure hai, code mein nahi. Agar database leak bhi ho jaye, attacker ko credentials nahi milengi.",
      en: "Yes. We use Fernet encryption (AES-128). The database stores only encrypted blobs — never plaintext. The encryption key lives on the server, not in the code. Even if the database leaked, an attacker couldn't read the credentials.",
      hi: "बिल्कुल। Fernet encryption use करते हैं (AES-128). Database में सिर्फ encrypted blob होता है, plaintext कभी नहीं। Encryption key server पर secure है, code में नहीं। अगर database leak भी हो जाए, attacker को credentials नहीं मिलेंगी।",
      gu: "બિલકુલ. Fernet encryption use કરીએ છીએ (AES-128). Database માં ફક્ત encrypted blob હોય છે, plaintext ક્યારેય નહીં. Encryption key server પર secure છે, code માં નહીં. Database leak થઈ જાય તો પણ attacker ને credentials મળશે નહીં.",
    },
    keywords: ["secure", "safe", "encryption", "credentials", "privacy", "सुरक्षित", "સુરક્ષિત"],
  },

  // ─── Webhooks ─────────────────────────────────────────────────────────
  {
    id: "webhook-what",
    category: "webhooks",
    question: "What is a webhook URL?",
    answers: {
      hinglish:
        "Webhook ek URL hai jisko TradingView (ya koi bhi alert system) HTTP POST karta hai. POST mein order details hote hain (BUY NIFTY 25000CE etc.). TRADETRI us alert ko receive karke broker ko forward karta hai — sub-second latency mein.",
      en: "A webhook is a URL that TradingView (or any alert system) HTTP POSTs to. The POST carries order details (BUY NIFTY 25000CE, etc.). TRADETRI receives the alert and forwards it to your broker — sub-second latency.",
      hi: "Webhook एक URL है जिसको TradingView (या कोई भी alert system) HTTP POST करता है। POST में order details होते हैं (BUY NIFTY 25000CE etc.). TRADETRI उस alert को receive करके broker को forward करता है — sub-second latency में।",
      gu: "Webhook એક URL છે જેને TradingView (કે કોઈ પણ alert system) HTTP POST કરે છે. POST માં order details હોય છે (BUY NIFTY 25000CE etc.). TRADETRI એ alert ને receive કરીને broker ને forward કરે છે — sub-second latency માં.",
    },
    keywords: ["webhook", "what", "url", "tradingview"],
  },
  {
    id: "webhook-create",
    category: "webhooks",
    question: "How do I create a webhook?",
    answers: {
      hinglish:
        "Webhooks page → 'Create Webhook' → label de (e.g., 'Nifty Scalper'). Tujhe ek unique URL milega aur HMAC secret. Dono copy karle — secret dobara nahi dikhega. URL ko TradingView alert mein paste kar dena.",
    },
    keywords: ["webhook", "create", "new", "make"],
  },
  {
    id: "webhook-test",
    category: "webhooks",
    question: "How do I test my webhook?",
    answers: {
      hinglish:
        "Webhooks page → apna webhook select kar → 'Test' button. Sample BUY NIFTY payload bhejta hai. Status 200 aaye toh webhook reachable hai. Order actually broker ko bhejna ho toh strategy se link karna padega.",
    },
    keywords: ["webhook", "test", "verify", "check"],
  },
  {
    id: "webhook-hmac",
    category: "webhooks",
    question: "What is HMAC and why do I need it?",
    answers: {
      hinglish:
        "HMAC (Hash-based Message Authentication Code) ek signature hai jo prove karta hai ki webhook tujhse hi aaya, kisi attacker se nahi. TradingView Pro+ mein HMAC support hai. Free plan mein bhi URL secret token use karke kaam chal jata hai, but HMAC zyada secure hai.",
    },
    keywords: ["hmac", "security", "signature", "auth"],
  },
  {
    id: "webhook-tradingview",
    category: "webhooks",
    question: "How to set webhook in TradingView?",
    answers: {
      hinglish:
        "TradingView mein:\n1. Alert create kar (right-click chart → Add Alert)\n2. 'Webhook URL' enable kar — apna TRADETRI URL paste kar\n3. Message field mein JSON paste kar:\n{\n  \"action\": \"BUY\",\n  \"symbol\": \"NIFTY25000CE\",\n  \"exchange\": \"NSE\",\n  \"order_type\": \"MARKET\",\n  \"quantity\": 50\n}\n4. Save kar.\n\nAlert fire hone par order TRADETRI through broker pe jayega.",
      en: "In TradingView:\n1. Create an alert (right-click chart → Add Alert)\n2. Enable 'Webhook URL' and paste your TRADETRI URL\n3. In the Message field, paste this JSON:\n{\n  \"action\": \"BUY\",\n  \"symbol\": \"NIFTY25000CE\",\n  \"exchange\": \"NSE\",\n  \"order_type\": \"MARKET\",\n  \"quantity\": 50\n}\n4. Save.\n\nWhen the alert fires, the order flows through TRADETRI to your broker.",
      hi: "TradingView में:\n1. Alert create करो (right-click chart → Add Alert)\n2. 'Webhook URL' enable करो — अपना TRADETRI URL paste करो\n3. Message field में यह JSON paste करो:\n{\n  \"action\": \"BUY\",\n  \"symbol\": \"NIFTY25000CE\",\n  \"exchange\": \"NSE\",\n  \"order_type\": \"MARKET\",\n  \"quantity\": 50\n}\n4. Save करो।\n\nAlert fire होने पर order TRADETRI से broker पर चला जाएगा।",
      gu: "TradingView માં:\n1. Alert create કરો (right-click chart → Add Alert)\n2. 'Webhook URL' enable કરો — તમારી TRADETRI URL paste કરો\n3. Message field માં આ JSON paste કરો:\n{\n  \"action\": \"BUY\",\n  \"symbol\": \"NIFTY25000CE\",\n  \"exchange\": \"NSE\",\n  \"order_type\": \"MARKET\",\n  \"quantity\": 50\n}\n4. Save કરો.\n\nAlert fire થાય ત્યારે order TRADETRI થી broker પર જશે.",
    },
    keywords: ["tradingview", "webhook", "setup", "alert"],
  },

  // ─── Strategies ───────────────────────────────────────────────────────
  {
    id: "strategy-what",
    category: "strategies",
    question: "What is a strategy in TRADETRI?",
    answers: {
      hinglish:
        "Strategy = ek webhook + ek broker + risk rules. Strategy webhook se signal leti hai aur broker pe order place karti hai. Tu daily loss limit, allowed symbols, max position size yahan set kar sakta hai.",
    },
    keywords: ["strategy", "what", "definition"],
  },
  {
    id: "strategy-create",
    category: "strategies",
    question: "How do I create a strategy?",
    answers: {
      hinglish:
        "Strategies page → 'New Strategy'. Naam de (e.g. 'Nifty Scalper'), webhook select kar, broker pick kar, max position size de, allowed symbols list mein NIFTY/BANKNIFTY etc. add kar. Activate kar — bas.",
    },
    keywords: ["strategy", "create", "new"],
  },
  {
    id: "strategy-backtest",
    category: "strategies",
    question: "How can I backtest a strategy?",
    answers: {
      hinglish:
        "TRADETRI execution layer hai, backtest engine nahi. Backtest TradingView pe Pine Script se kar — wahan se signal generate karke TRADETRI pe forward karna hai. Forward-test (paper mode) yahan possible hai.",
    },
    keywords: ["backtest", "strategy", "test", "history"],
  },
  {
    id: "paper-trade",
    category: "strategies",
    question: "What is paper trading and how do I enable it?",
    answers: {
      hinglish:
        "Paper trading = real signals, fake orders. Strategy edit → 'Paper Mode' toggle on. Orders log mein dikhenge but broker pe nahi jayenge. 1-2 hafte paper mode mein chala, fir live kar — yeh 15 saal ka rule hai.",
      en: "Paper trading = real signals, simulated orders. Edit your strategy → toggle 'Paper Mode' on. Orders show up in the log but never reach the broker. Run paper mode for 1-2 weeks, then go live. That's the 15-year veteran rule.",
      hi: "Paper trading = real signals, fake orders। Strategy edit → 'Paper Mode' toggle on करो। Orders log में दिखेंगे लेकिन broker पे नहीं जाएंगे। 1-2 हफ्ते paper mode में चलाओ, फिर live करो — यह 15 साल का rule है।",
      gu: "Paper trading = real signals, fake orders. Strategy edit → 'Paper Mode' toggle on કરો. Orders log માં દેખાશે પણ broker પર નહીં જાય. 1-2 અઠવાડિયા paper mode માં ચલાવો, પછી live કરો — એ 15 વર્ષ નો rule છે.",
    },
    keywords: ["paper", "trade", "demo", "test"],
  },
  {
    id: "allowed-symbols",
    category: "strategies",
    question: "What are 'allowed symbols'?",
    answers: {
      hinglish:
        "Whitelist hai. Strategy sirf yeh symbols pe trade karegi. Agar tu sirf NIFTY pe scalper chala raha hai aur galti se RELIANCE ka signal aa gaya, strategy reject kar degi. Critical safety net.",
    },
    keywords: ["allowed", "symbols", "whitelist", "filter"],
  },

  // ─── Orders ──────────────────────────────────────────────────────────
  {
    id: "order-failing",
    category: "orders",
    question: "Why is my order failing?",
    answers: {
      hinglish:
        "5 common reasons:\n1. Insufficient funds — broker mein paisa nahi\n2. Invalid symbol — symbol format galat (NIFTY25000CE expiry shayad galat hai)\n3. Session expired — broker token refresh kar\n4. Outside market hours — 9:15-15:30 ke baar order reject\n5. Kill switch tripped — daily loss limit hit ho gaya\n\nKaunsa error message dikh raha? Mujhe screenshot bhej, exact diagnose karta hoon.",
      en: "5 common reasons:\n1. Insufficient funds — no margin in broker\n2. Invalid symbol — wrong format (NIFTY25000CE expiry might be off)\n3. Session expired — refresh the broker token\n4. Outside market hours — orders before 9:15 / after 15:30 IST get rejected\n5. Kill switch tripped — daily loss limit hit\n\nWhat's the exact error? Send a screenshot and I'll diagnose.",
      hi: "5 common reasons:\n1. Insufficient funds — broker में पैसा नहीं\n2. Invalid symbol — symbol format गलत (NIFTY25000CE expiry शायद गलत है)\n3. Session expired — broker token refresh करो\n4. Outside market hours — 9:15-15:30 के बाहर order reject\n5. Kill switch tripped — daily loss limit hit हो गया\n\nकौनसा error message दिख रहा है? Screenshot भेजो, exact diagnose करता हूँ।",
      gu: "5 common reasons:\n1. Insufficient funds — broker માં પૈસા નથી\n2. Invalid symbol — symbol format ખોટું (NIFTY25000CE expiry કદાચ ખોટી છે)\n3. Session expired — broker token refresh કરો\n4. Outside market hours — 9:15-15:30 બહાર order reject\n5. Kill switch tripped — daily loss limit hit થઈ ગયું\n\nકયો error message દેખાય છે? Screenshot મોકલો, exact diagnose કરું.",
    },
    keywords: ["order", "fail", "error", "rejected", "not working", "नहीं", "નથી"],
  },
  {
    id: "order-types",
    category: "orders",
    question: "What's the difference between MARKET and LIMIT?",
    answers: {
      hinglish:
        "MARKET = best available price pe instant execute. Slippage ka risk hai but fill guaranteed.\nLIMIT = sirf tere price (ya better) pe execute. Slippage zero but fill nahi bhi ho sakta.\n\nScalping mein MARKET use kar (speed > price), positional mein LIMIT use kar (price > speed).",
    },
    keywords: ["market", "limit", "order", "type", "difference"],
  },
  {
    id: "stop-loss",
    category: "orders",
    question: "What's the difference between SL and SL-M?",
    answers: {
      hinglish:
        "SL (Stop Loss Limit) — trigger price pe SL active hota hai, fir limit price pe execute. Slippage protected.\nSL-M (Stop Loss Market) — trigger pe market order trigger ho jata hai. Fast execution but slippage possible.\n\nVolatile market mein SL-M lagao (otherwise SL hit hi nahi hoga). Calm market mein SL theek hai.",
    },
    keywords: ["stop loss", "sl", "sl-m", "trigger"],
  },
  {
    id: "square-off",
    category: "orders",
    question: "How do I square off all positions?",
    answers: {
      hinglish:
        "Positions page → 'Square Off All' button. Ya kill switch trigger kar de. Backend market orders bhejta hai, sab open positions close ho jaate hain. Use sirf emergency mein — slippage market mood pe depend karta hai.",
    },
    keywords: ["square", "off", "close", "positions", "exit"],
  },
  {
    id: "trade-export",
    category: "orders",
    question: "Can I export my trade history?",
    answers: {
      hinglish:
        "Haan bhai. Trades page → Export button → CSV download ho jata hai. Tax calculation, audit, ya broker pe reconciliation ke liye useful hai.",
    },
    keywords: ["export", "trades", "csv", "history", "download"],
  },

  // ─── Kill switch ─────────────────────────────────────────────────────
  {
    id: "killswitch-what",
    category: "kill_switch",
    question: "What is the kill switch?",
    answers: {
      hinglish:
        "Kill switch = automatic circuit breaker. Daily loss ya max trades hit ho toh:\n1. Sab pending orders cancel\n2. Sab open positions square off\n3. Naye orders block — agle din tak\n\n15 saal ka lesson: bina kill switch ke koi bhi algo trade nahi karna chahiye. Ek galat day account khaali kar sakta hai.",
      en: "The kill switch is an automatic circuit breaker. When daily loss or max-trades cap is hit:\n1. All pending orders are cancelled\n2. All open positions are squared off\n3. New orders are blocked until the next session\n\n15-year lesson: never run an algo without a kill switch. One bad day can wipe out an account.",
      hi: "Kill switch = automatic circuit breaker। Daily loss या max trades hit हो तो:\n1. सब pending orders cancel\n2. सब open positions square off\n3. नए orders block — अगले दिन तक\n\n15 साल का lesson: बिना kill switch के कोई भी algo trade नहीं करना चाहिए। एक गलत दिन account खाली कर सकता है।",
      gu: "Kill switch = automatic circuit breaker. Daily loss કે max trades hit થાય તો:\n1. બધા pending orders cancel\n2. બધી open positions square off\n3. નવા orders block — બીજા દિવસ સુધી\n\n15 વર્ષ નો lesson: kill switch વગર કોઈ પણ algo trade ન કરવો જોઈએ. એક ખોટો દિવસ account ખાલી કરી શકે છે.",
    },
    keywords: ["kill switch", "circuit", "stop", "what"],
  },
  {
    id: "killswitch-loss",
    category: "kill_switch",
    question: "How do I set my daily loss limit?",
    answers: {
      hinglish:
        "Settings → Kill Switch → Max Daily Loss field. Capital ka 2-3% se zyada mat rakh. Example: ₹1L capital pe ₹2-3K limit. Discipline ka sabse bada teacher yahi hai.",
    },
    keywords: ["daily loss", "limit", "kill switch", "max loss"],
  },
  {
    id: "killswitch-trades",
    category: "kill_switch",
    question: "What is max trades per day?",
    answers: {
      hinglish:
        "Ek din mein max kitne trades execute honge. Overtrading = revenge trading. 15-20 quality trades ek scalper ke liye bahut hain. Settings mein 50 default hai but kam rakhna hi smart hai.",
    },
    keywords: ["max trades", "limit", "overtrade"],
  },
  {
    id: "killswitch-reset",
    category: "kill_switch",
    question: "When does the kill switch reset?",
    answers: {
      hinglish:
        "Daily 9:00 AM IST pe automatic reset hota hai (market open se 15 min pehle). Manual reset bhi kar sakta hai — but nahi karna chahiye, woh emotional trading ka start hai.",
    },
    keywords: ["reset", "kill switch", "when", "next day"],
  },

  // ─── Positions ───────────────────────────────────────────────────────
  {
    id: "position-size",
    category: "positions",
    question: "How big should my position size be?",
    answers: {
      hinglish:
        "Risk per trade = capital ka 1-2%. Position size = (Risk per trade) / (entry - stop loss).\nExample: ₹1L capital, 1% risk = ₹1000. Stop loss ₹10 hai. Toh quantity = 1000/10 = 100 units.\n\nSize hamesha SL ke base pe nikaal — gut feel pe kabhi nahi.",
    },
    keywords: ["position size", "quantity", "lot", "how much"],
  },
  {
    id: "holdings-vs-positions",
    category: "positions",
    question: "What's the difference between holdings and positions?",
    answers: {
      hinglish:
        "Positions = aaj ke open trades (intraday + carry-forward F&O). End-of-day pe close ho sakte hain.\nHoldings = demat mein settled stocks (T+1 ke baad). Long-term store hai.\n\nIntraday ka P&L positions mein dikhta hai, delivery ka holdings mein.",
    },
    keywords: ["positions", "holdings", "difference"],
  },
  {
    id: "pnl-calc",
    category: "positions",
    question: "How is P&L calculated?",
    answers: {
      hinglish:
        "Realized P&L = closed trades ka profit/loss.\nUnrealized P&L = open positions ka mark-to-market (LTP - avg buy).\nTotal = realized + unrealized.\n\nNote: brokerage + STT + GST nikalta hai gross se. Net P&L hamesha thoda kam dikhega.",
    },
    keywords: ["pnl", "profit", "loss", "calculation"],
  },
  {
    id: "fees",
    category: "positions",
    question: "Are there any TRADETRI fees per trade?",
    answers: {
      hinglish:
        "TRADETRI fees flat subscription hai (per month). Per trade extra charge nahi. Brokerage broker apni leta hai (Fyers ₹20/order, Dhan ₹20/order intraday). STT, GST, exchange charges separate hain.",
    },
    keywords: ["fees", "charges", "cost", "pricing"],
  },

  // ─── Errors ──────────────────────────────────────────────────────────
  {
    id: "err-session-expired",
    category: "errors",
    question: "Session expired error — what to do?",
    answers: {
      hinglish:
        "Broker ka access token expire ho gaya. Brokers page jao → broker ke saamne 'Reconnect' button click kar. Fyers ko OAuth login dobara karna padega, Dhan ko fresh access token paste karna hoga.",
      en: "Your broker's access token expired. Open the Brokers page → click 'Reconnect' next to the broker. Fyers needs a fresh OAuth login; Dhan needs a fresh personal access token pasted in.",
      hi: "Broker का access token expire हो गया। Brokers page जाओ → broker के सामने 'Reconnect' button click करो। Fyers का OAuth login दोबारा करना पड़ेगा, Dhan का fresh access token paste करना होगा।",
      gu: "Broker નો access token expire થઈ ગયો. Brokers page માં જાવ → broker ની સામે 'Reconnect' button click કરો. Fyers માટે OAuth login ફરી કરવો પડશે, Dhan માટે fresh access token paste કરવો પડશે.",
    },
    keywords: ["session expired", "expired", "token", "logout"],
  },
  {
    id: "err-insufficient-funds",
    category: "errors",
    question: "Insufficient funds error",
    answers: {
      hinglish:
        "Broker mein margin nahi hai. Check kar:\n1. Trading account mein paisa hai?\n2. Pending orders se margin block to nahi?\n3. F&O ke liye margin requirement zyada hota hai (specially weekly expiry pe)\n\nSettlement T+1 hota hai — selling ke baad next day funds milte hain.",
      en: "No margin available at the broker. Check:\n1. Is there cash in the trading account?\n2. Any pending orders blocking margin?\n3. F&O margin is higher (especially around weekly expiry)\n\nSettlement is T+1 — funds from a sell trade are usable the next working day.",
      hi: "Broker में margin नहीं है। Check करो:\n1. Trading account में पैसा है?\n2. Pending orders से margin block तो नहीं?\n3. F&O के लिए margin requirement ज़्यादा होती है (specially weekly expiry पर)\n\nSettlement T+1 होता है — selling के बाद अगले दिन funds मिलते हैं।",
      gu: "Broker માં margin નથી. Check કરો:\n1. Trading account માં પૈસા છે?\n2. Pending orders થી margin block તો નથી?\n3. F&O માટે margin requirement વધારે હોય છે (ખાસ કરીને weekly expiry પર)\n\nSettlement T+1 છે — selling પછી બીજા દિવસે funds મળે છે.",
    },
    keywords: ["insufficient funds", "margin", "balance"],
  },
  {
    id: "err-invalid-symbol",
    category: "errors",
    question: "Invalid symbol error",
    answers: {
      hinglish:
        "Symbol format broker ke spec se match nahi kar raha. Examples:\n- NSE equity: RELIANCE-EQ (Fyers), RELIANCE (Dhan)\n- F&O: NIFTY25APR25000CE (correct expiry month + strike + type)\n\nWebhook payload mein exact format match hona chahiye. Doubt ho toh exact symbol mujhe bhej, fix kar deta hoon.",
    },
    keywords: ["invalid symbol", "symbol", "not found"],
  },
  {
    id: "err-rate-limit",
    category: "errors",
    question: "Rate limit error from broker",
    answers: {
      hinglish:
        "Broker ne 1 second mein bahut zyada orders bhej diye samjha. TRADETRI auto-retry karta hai 100ms-400ms backoff ke saath. Agar fir bhi fail ho raha:\n- Strategy ke webhook firing rate kam kar\n- Multiple strategies ek hi broker pe ho toh consolidate kar\n- 1 minute wait kar, fir try kar",
    },
    keywords: ["rate limit", "throttle", "429", "too many"],
  },
  {
    id: "err-rejected",
    category: "errors",
    question: "Order rejected by broker — why?",
    answers: {
      hinglish:
        "Broker se order reject hone ke main reasons:\n1. Margin shortage\n2. Stock under ASM/GSM (regulator restrictions)\n3. Lot size galat (F&O lot multiple hona chahiye)\n4. Circuit limit hit (price upper/lower circuit pe hai)\n5. Pre-open / post-close mein market order\n\nReject reason exact dikhao toh fix bata sakta hoon.",
    },
    keywords: ["rejected", "broker", "order", "denied"],
  },

  // ─── Education ───────────────────────────────────────────────────────
  {
    id: "edu-paper-trade",
    category: "education",
    question: "Should I paper trade first?",
    answers: {
      hinglish:
        "Bhai, MUST. 15 saal ka rule: koi bhi nayi strategy minimum 2 hafte paper mode pe chalao. Real money pe tab jaao jab paper mein consistent profit dikhe. Emotion test only real money pe hota hai but math test paper pe bhi pakka hota hai.",
    },
    keywords: ["paper", "demo", "practice", "first"],
  },
  {
    id: "edu-risk-mgmt",
    category: "education",
    question: "What are the basic risk management rules?",
    answers: {
      hinglish:
        "🛡️ Risk Management — Trader's biggest weapon!\n\n15 saal me sikha — strategy 20% hai, risk management 80% hai trading me.\n\n3 golden rules:\n\n1. Per Trade Risk: Max 1-2% of capital\n   ₹50,000 capital = ₹500-1000 max risk per trade\n\n2. Daily Loss Limit: Max 5% of capital\n   Hit ho gaya = trading band, kal naya din\n\n3. Position Sizing: Calculate before entry\n   Risk amount ÷ Stop loss points = quantity\n\nYeh 3 rules follow karega toh 1 saal mein bhi blow up nahi karega. Iske bina Day 1 pe blow up possible hai.",
      en: "🛡️ Risk Management — your biggest weapon as a trader.\n\n15 years taught me: strategy is 20%, risk management is 80% of trading.\n\n3 golden rules:\n\n1. Per-trade risk: max 1-2% of capital\n   ₹50,000 capital → ₹500-1000 max risk per trade\n\n2. Daily loss limit: max 5% of capital\n   Hit it → stop trading, fresh day tomorrow.\n\n3. Position sizing: calculated before entry\n   Risk amount ÷ stop-loss points = quantity\n\nFollow these three and you won't blow up even in a year. Skip them and you can blow up on day one.",
      hi: "🛡️ Risk Management — Trader का सबसे बड़ा हथियार!\n\n15 साल में सीखा — trading में strategy 20% है, risk management 80% है।\n\n3 golden rules:\n\n1. Per Trade Risk: Max 1-2% of capital\n   ₹50,000 capital = ₹500-1000 max risk per trade\n\n2. Daily Loss Limit: Max 5% of capital\n   Hit हो गया = trading बंद, कल नया दिन।\n\n3. Position Sizing: Entry से पहले calculate करो\n   Risk amount ÷ Stop loss points = quantity\n\nयह 3 rules follow करोगे तो 1 साल में भी blow up नहीं होगा। इनके बिना Day 1 पर blow up possible है।",
      gu: "🛡️ Risk Management — Trader નું સૌથી મોટું હથિયાર!\n\n15 વર્ષ માં શીખ્યું — trading માં strategy 20% છે, risk management 80% છે.\n\n3 golden rules:\n\n1. Per Trade Risk: Max 1-2% of capital\n   ₹50,000 capital = ₹500-1000 max risk per trade\n\n2. Daily Loss Limit: Max 5% of capital\n   Hit થયું = trading બંધ, કાલે નવો દિવસ.\n\n3. Position Sizing: Entry પહેલા calculate કરો\n   Risk amount ÷ Stop loss points = quantity\n\nઆ 3 rules follow કરશો તો 1 વર્ષ માં પણ blow up નહીં થાય. એના વગર Day 1 પર blow up શક્ય છે.",
    },
    keywords: ["risk", "management", "rules", "basics", "जोखिम", "જોખમ"],
  },
  {
    id: "edu-position-sizing",
    category: "education",
    question: "How do I do proper position sizing?",
    answers: {
      hinglish:
        "📏 Position Sizing — formula simple, discipline tough.\n\nFormula:\n  Quantity = (Capital × Risk%) / (Entry − Stop Loss)\n\nReal example, step-by-step:\n• Capital: ₹2,00,000\n• Per-trade risk: 1% = ₹2,000\n• Entry: ₹100, Stop Loss: ₹80\n• Risk per unit: ₹100 − ₹80 = ₹20\n• Quantity = ₹2,000 / ₹20 = 100 units\n\nWorst case (SL hit): −₹2,000 (1% of capital).\n50 baar lagatar SL hit ho toh bhi capital safe — discipline ka beauty yahi hai.\n\nGut feel pe size mat decide kar — math pe kar.",
      en: "📏 Position Sizing — simple math, hard discipline.\n\nFormula:\n  Quantity = (Capital × Risk%) / (Entry − Stop Loss)\n\nWorked example:\n• Capital: ₹2,00,000\n• Per-trade risk: 1% = ₹2,000\n• Entry: ₹100, Stop Loss: ₹80\n• Risk per unit: ₹100 − ₹80 = ₹20\n• Quantity = ₹2,000 / ₹20 = 100 units\n\nWorst case (SL hit): −₹2,000 (1% of capital). Even 50 SL hits in a row leaves the account intact — that's the beauty of discipline.\n\nDon't size by gut feel. Size by math.",
      hi: "📏 Position Sizing — formula simple, discipline tough.\n\nFormula:\n  Quantity = (Capital × Risk%) / (Entry − Stop Loss)\n\nReal example, step-by-step:\n• Capital: ₹2,00,000\n• Per-trade risk: 1% = ₹2,000\n• Entry: ₹100, Stop Loss: ₹80\n• Risk per unit: ₹100 − ₹80 = ₹20\n• Quantity = ₹2,000 / ₹20 = 100 units\n\nWorst case (SL hit): −₹2,000 (1% of capital).\n50 बार लगातार SL hit हो तो भी capital safe — discipline की beauty यही है।\n\nGut feel पर size मत decide करो — math पर करो।",
      gu: "📏 Position Sizing — formula simple, discipline tough.\n\nFormula:\n  Quantity = (Capital × Risk%) / (Entry − Stop Loss)\n\nReal example, step-by-step:\n• Capital: ₹2,00,000\n• Per-trade risk: 1% = ₹2,000\n• Entry: ₹100, Stop Loss: ₹80\n• Risk per unit: ₹100 − ₹80 = ₹20\n• Quantity = ₹2,000 / ₹20 = 100 units\n\nWorst case (SL hit): −₹2,000 (1% of capital).\n50 વાર સતત SL hit થાય તો પણ capital safe — discipline ની beauty આ જ છે.\n\nGut feel પર size નક્કી ન કરો — math પર કરો.",
    },
    keywords: ["position", "sizing", "quantity"],
  },
  {
    id: "edu-lot-size",
    category: "education",
    question: "What is lot size in F&O?",
    answers: {
      hinglish:
        "Exchange ke pre-defined units. Tu lot ke multiples mein hi trade kar sakta hai.\nNIFTY: 25 (changes occasionally)\nBANKNIFTY: 15\nFINNIFTY: 25\nStocks: alag-alag (RELIANCE 250, TCS 175 etc.)\n\nLot size NSE site pe check kar — yeh exchange notifications se change hote rehte hain.",
    },
    keywords: ["lot", "size", "fno", "options", "futures"],
  },
  {
    id: "edu-expiry",
    category: "education",
    question: "What is expiry day and weekly expiry?",
    answers: {
      hinglish:
        "Expiry = derivatives ka end date. Position close ya settle ho jaati hai.\nWeekly: NIFTY/BANKNIFTY/FINNIFTY/MIDCPNIFTY har Tuesday-Friday alag (rotating expiry).\nMonthly: stocks aur indexes ka last Thursday.\n\nExpiry day pe theta decay sabse fast hota hai — option sellers ka favourite, buyers ka enemy.",
    },
    keywords: ["expiry", "weekly", "monthly", "options"],
  },

  // ─── Indian market ────────────────────────────────────────────────────
  {
    id: "ind-muhurat",
    category: "indian_market",
    question: "What is Muhurat trading?",
    answers: {
      hinglish:
        "Diwali ke din evening 1 hour ka special trading session. Symbolic — naya samvat year start. Bahut log token trade karte hain (1 share). Volatility kam, volume bhi kam. Algo strategies usually pause kar di jaati hain — risk-reward worth nahi hai.",
    },
    keywords: ["muhurat", "diwali", "special"],
  },
  {
    id: "ind-btst",
    category: "indian_market",
    question: "What is BTST?",
    answers: {
      hinglish:
        "Buy Today Sell Tomorrow. Stock kharid ke next day demat aane se pehle bech do. Some brokers allow karte hain (delivery without T+1 wait). Risk: stock T+1 mein nahi aaye toh auction in delivery — penalty 20% tak.",
    },
    keywords: ["btst", "buy today", "sell tomorrow"],
  },
  {
    id: "ind-t1",
    category: "indian_market",
    question: "What is T+1 settlement?",
    answers: {
      hinglish:
        "Trade Day + 1 = next working day pe settlement. India mein 2023 se T+1 lagu hai (most efficient global market!). Aaj khareeda toh kal demat mein. Aaj becha toh kal funds available.",
    },
    keywords: ["t+1", "t1", "settlement"],
  },
  {
    id: "ind-mcx",
    category: "indian_market",
    question: "Does TRADETRI support MCX commodities?",
    answers: {
      hinglish:
        "Symbol-level haan, but practical mein Fyers/Dhan ka MCX feed enable hona chahiye. Most users equity + F&O karte hain. Commodities trade karna hai toh founder ko bata, custom guide bhej deta hoon.",
    },
    keywords: ["mcx", "commodity", "gold", "crude"],
  },

  // ─── TRADETRI specific ───────────────────────────────────────────────
  {
    id: "tt-what",
    category: "tradetri",
    question: "What is TRADETRI?",
    answers: {
      hinglish:
        "TRADETRI = TradingView signals → Indian brokers ke beech ka bridge. TradingView pe alert fire kare toh sub-second mein broker pe order chala jaata hai. Kill switch, paper mode, multi-broker, audit trail — sab built-in.\n\nTagline: 'Automate without the chaos.'",
      en: "TRADETRI is the bridge between TradingView signals and Indian brokers. When a TradingView alert fires, the order reaches your broker in sub-second time. Kill switch, paper mode, multi-broker support, full audit trail — all built in.\n\nTagline: 'Automate without the chaos.'",
      hi: "TRADETRI = TradingView signals और Indian brokers के बीच का bridge। TradingView पर alert fire हो तो sub-second में broker पर order चला जाता है। Kill switch, paper mode, multi-broker, audit trail — सब built-in।\n\nTagline: 'Automate without the chaos.'",
      gu: "TRADETRI = TradingView signals અને Indian brokers વચ્ચેનો bridge. TradingView પર alert fire થાય તો sub-second માં broker પર order જાય. Kill switch, paper mode, multi-broker, audit trail — બધું built-in.\n\nTagline: 'Automate without the chaos.'",
    },
    keywords: ["tradetri", "what", "about", "platform"],
  },
  {
    id: "tt-pricing",
    category: "tradetri",
    question: "What does TRADETRI cost?",
    answers: {
      hinglish:
        "Pricing tiers founder ke saath finalize chal rahi hai (target Q3). Currently early access mein discounted hai. Calendly call book kar — actual numbers wahan share kar denge.",
      en: "Pricing tiers are being finalised (target Q3). Early access is discounted right now. Book a Calendly call with the founder — exact numbers shared there.",
      hi: "Pricing tiers founder के साथ finalize हो रही हैं (target Q3). फिलहाल early access में discount है। Calendly call book करो — actual numbers वहाँ share कर देंगे।",
      gu: "Pricing tiers founder સાથે finalize થઈ રહી છે (target Q3). હાલમાં early access માં discount છે. Calendly call book કરો — actual numbers ત્યાં share કરી દેશું.",
    },
    keywords: ["price", "cost", "subscription", "fees", "कीमत", "કિંમત"],
  },
  {
    id: "tt-uptime",
    category: "tradetri",
    question: "What is the uptime guarantee?",
    answers: {
      hinglish:
        "Target 99.9% during market hours (9:15-15:30 IST). Infrastructure: AWS Mumbai region, redundant DB, Redis cache, Vercel edge. Real-time status page jaldi launch hoga. Outage ho toh founder ko WhatsApp pe ping kar — direct visibility hai.",
    },
    keywords: ["uptime", "downtime", "reliability", "sla"],
  },
  {
    id: "algomitra-can-do",
    category: "tradetri",
    question: "What can AlgoMitra do?",
    answers: {
      hinglish:
        "Main aap ki help karta hu in cheezo me:\n\n✅ Abhi:\n- Broker setup (Fyers, Dhan)\n- Trading basics\n- Risk management\n- Common errors troubleshoot\n- Loss support, win celebration\n- 4 languages (Eng/Hindi/Gujarati/Hinglish)\n\n🔜 Jald aane wala:\n- Aur brokers (Upstox, Angel)\n- Tutorial videos\n- Tier 1 Free webhooks\n\n🎯 Future vision (6-12 mahine):\n- Real AI conversations\n- Saari 11 Indian languages\n- Photo help, voice notes\n- Trading psychology coach\n\nVision hai, time lagega. Aaj kya help chahiye?",
      en: "Here's what I can help with today:\n\n✅ Currently:\n- Broker setup (Fyers, Dhan)\n- Trading basics\n- Risk management\n- Common error troubleshooting\n- Loss support and win celebration\n- 4 languages (English / Hindi / Gujarati / Hinglish)\n\n🔜 Coming soon:\n- More brokers (Upstox, AngelOne)\n- Tutorial videos\n- Tier 1 Free webhooks\n\n🎯 Future vision (6-12 months):\n- Real AI conversations\n- All 11 Indian languages\n- Photo help, voice notes\n- Trading psychology coach\n\nVision is big, will take time. What do you need today?",
      // REVIEW: Hindi rendering — native check before launch announcement
      hi: "मैं आपकी इन चीज़ों में मदद करता हूँ:\n\n✅ अभी:\n- Broker setup (Fyers, Dhan)\n- Trading basics\n- Risk management\n- Common errors troubleshoot\n- भावनात्मक support\n- 4 languages (English/Hindi/Gujarati/Hinglish)\n\n🔜 जल्द आ रहा है:\n- और brokers (Upstox, Angel)\n- Tutorial videos\n- Tier 1 Free webhooks\n\n🎯 भविष्य की योजना (6-12 महीने):\n- Real AI conversations\n- सभी 11 भारतीय भाषाएं\n- Photo help, voice notes\n- Trading psychology coach\n\nVision है, time लगेगा। आज क्या help चाहिए?",
      // REVIEW: Gujarati rendering — native check before launch announcement
      gu: "હું તમને આ વસ્તુઓમાં મદદ કરું છું:\n\n✅ હાલમાં:\n- Broker setup (Fyers, Dhan)\n- Trading basics\n- Risk management\n- Common errors troubleshoot\n- Emotional support\n- 4 languages (English/Hindi/Gujarati/Hinglish)\n\n🔜 જલ્દી આવી રહ્યું છે:\n- વધારે brokers (Upstox, Angel)\n- Tutorial videos\n- Tier 1 Free webhooks\n\n🎯 Future vision (6-12 મહિના):\n- Real AI conversations\n- બધી 11 Indian languages\n- Photo help, voice notes\n- Trading psychology coach\n\nVision છે, time લાગશે. આજે શું help જોઈએ?",
    },
    keywords: [
      "can you do", "what can", "kya kar", "kya kar sakte", "capabilities",
      "क्या कर", "क्या कर सकते", "શું કરી", "શું કરો",
      "algomitra", "अल्गोमित्र",
    ],
  },
  {
    id: "algomitra-features",
    category: "tradetri",
    question: "What features are available right now?",
    answers: {
      hinglish:
        "Live features (abhi use kar sakte ho):\n\n🔌 Broker integration: Fyers + Dhan production-ready\n🛡️ Kill switch: daily loss limit, auto square-off, max trades cap\n📝 Paper trading: real signals, fake orders — validate karo phir live jao\n🎯 Webhooks: TradingView se sub-second order routing\n📊 Audit trail: har trade logged, CSV export available\n🤝 AlgoMitra: 24/7 chat support 4 languages mein\n\nSubscription tiers finalize ho rahi hain — pricing pucho toh founder ko WhatsApp pe ping kar.\n\n🔜 Coming: Upstox, AngelOne, tutorial videos.",
      en: "Live features (use right now):\n\n🔌 Broker integration: Fyers + Dhan production-ready\n🛡️ Kill switch: daily loss limit, auto square-off, max trades cap\n📝 Paper trading: real signals, simulated orders — validate before going live\n🎯 Webhooks: sub-second TradingView → broker order routing\n📊 Audit trail: every trade logged, CSV export\n🤝 AlgoMitra: 24/7 chat support in 4 languages\n\nPricing tiers being finalised — for specifics, WhatsApp the founder.\n\n🔜 Coming: Upstox, AngelOne, tutorial videos.",
      // REVIEW: Hindi rendering — native check before launch announcement
      hi: "Live features (अभी use कर सकते हो):\n\n🔌 Broker integration: Fyers + Dhan production-ready\n🛡️ Kill switch: daily loss limit, auto square-off, max trades cap\n📝 Paper trading: real signals, fake orders — validate करो फिर live जाओ\n🎯 Webhooks: TradingView से sub-second order routing\n📊 Audit trail: हर trade logged, CSV export available\n🤝 AlgoMitra: 24/7 chat support 4 languages में\n\nSubscription tiers finalize हो रही हैं — pricing पूछो तो founder को WhatsApp पर ping करो।\n\n🔜 Coming: Upstox, AngelOne, tutorial videos.",
      // REVIEW: Gujarati rendering — native check before launch announcement
      gu: "Live features (હાલમાં use કરી શકો છો):\n\n🔌 Broker integration: Fyers + Dhan production-ready\n🛡️ Kill switch: daily loss limit, auto square-off, max trades cap\n📝 Paper trading: real signals, fake orders — validate કરો પછી live જાવ\n🎯 Webhooks: TradingView થી sub-second order routing\n📊 Audit trail: દરેક trade logged, CSV export\n🤝 AlgoMitra: 24/7 chat support 4 languages માં\n\nSubscription tiers finalize થઈ રહી છે — pricing માટે founder ને WhatsApp પર ping કરો.\n\n🔜 Coming: Upstox, AngelOne, tutorial videos.",
    },
    keywords: [
      "features", "feature", "available", "kya hai available", "kya features",
      "क्या features", "क्या है available", "શું features", "શું છે",
    ],
  },
  {
    id: "algomitra-roadmap",
    category: "tradetri",
    question: "What's on the roadmap / future plans?",
    answers: {
      hinglish:
        "Vision hai, time lagega — honest answer:\n\n🔜 1-3 mahine:\n- Upstox integration\n- Tier 1 Free tier (basic webhooks, koi cost nahi)\n- Tutorial video library\n\n🎯 3-6 mahine:\n- AngelOne, Shoonya integrations\n- Strategy marketplace (community shared)\n\n🔮 6-12 mahine:\n- Real AI mentor (Phase 1B)\n- 11 Indian languages full support\n- Photo-based troubleshooting\n- Voice notes\n- Year-end Wrapped report\n\nSpecific dates nahi de sakta — founder se WhatsApp pe pucho. Main commitments nahi karta.",
      en: "Honest answer — vision is big, will take time:\n\n🔜 1-3 months:\n- Upstox integration\n- Tier 1 Free tier (basic webhooks, no cost)\n- Tutorial video library\n\n🎯 3-6 months:\n- AngelOne, Shoonya integrations\n- Strategy marketplace (community-shared)\n\n🔮 6-12 months:\n- Real AI mentor (Phase 1B)\n- All 11 Indian languages\n- Photo-based troubleshooting\n- Voice notes\n- Year-end Wrapped report\n\nNo specific dates — for that, WhatsApp the founder. I don't make commitments.",
      // REVIEW: Hindi rendering — native check before launch announcement
      hi: "Vision है, time लगेगा — honest answer:\n\n🔜 1-3 महीने:\n- Upstox integration\n- Tier 1 Free tier (basic webhooks, कोई cost नहीं)\n- Tutorial video library\n\n🎯 3-6 महीने:\n- AngelOne, Shoonya integrations\n- Strategy marketplace (community shared)\n\n🔮 6-12 महीने:\n- Real AI mentor (Phase 1B)\n- 11 Indian languages full support\n- Photo-based troubleshooting\n- Voice notes\n- Year-end Wrapped report\n\nSpecific dates नहीं दे सकता — founder से WhatsApp पर पूछो। मैं commitments नहीं करता।",
      // REVIEW: Gujarati rendering — native check before launch announcement
      gu: "Vision છે, time લાગશે — honest answer:\n\n🔜 1-3 મહિના:\n- Upstox integration\n- Tier 1 Free tier (basic webhooks, કોઈ cost નહીં)\n- Tutorial video library\n\n🎯 3-6 મહિના:\n- AngelOne, Shoonya integrations\n- Strategy marketplace (community shared)\n\n🔮 6-12 મહિના:\n- Real AI mentor (Phase 1B)\n- 11 Indian languages full support\n- Photo-based troubleshooting\n- Voice notes\n- Year-end Wrapped report\n\nSpecific dates આપી શકું નહીં — founder ને WhatsApp પર પૂછો. હું commitments કરતો નથી.",
    },
    keywords: [
      "roadmap", "future plans", "future", "coming soon", "future plans kya",
      "kab aayega", "जल्द", "भविष्य", "ભવિષ્ય", "આવી રહ્યું", "plans",
    ],
  },
  {
    id: "why-tradetri",
    category: "tradetri",
    question: "Why use TRADETRI?",
    answers: {
      hinglish:
        "Honest reasons:\n\n⚡ Speed: TradingView signal → broker pe order, sub-second\n🛡️ Discipline: kill switch automatic enforce karta hai daily loss limit\n🔀 Multi-broker: ek strategy Fyers pe, ek Dhan pe — flexible\n📝 Paper mode built-in: 2 hafte test karke live jao\n🔒 Audit trail: SEBI compliance ke liye saare trades logged\n🤝 Founder accessible: WhatsApp / Calendly se direct baat\n\n15 saal trading ka pain — yeh platform usse banaya gaya hai. Vision big hai, abhi v1 hai. Honest expectations rakh.",
      en: "Honest reasons:\n\n⚡ Speed: TradingView signal → broker order in sub-second\n🛡️ Discipline: kill switch auto-enforces your daily loss limit\n🔀 Multi-broker: one strategy on Fyers, another on Dhan — flexible\n📝 Paper mode built-in: test 2 weeks before going live\n🔒 Audit trail: every trade logged for SEBI compliance\n🤝 Founder accessible: direct via WhatsApp / Calendly\n\nThis platform was built from 15 years of trading pain. Vision is big, but it's still v1. Keep honest expectations.",
      // REVIEW: Hindi rendering — native check before launch announcement
      hi: "Honest reasons:\n\n⚡ Speed: TradingView signal → broker पर order, sub-second\n🛡️ Discipline: kill switch automatic enforce करता है daily loss limit\n🔀 Multi-broker: एक strategy Fyers पर, एक Dhan पर — flexible\n📝 Paper mode built-in: 2 हफ्ते test करके live जाओ\n🔒 Audit trail: SEBI compliance के लिए सारे trades logged\n🤝 Founder accessible: WhatsApp / Calendly से direct बात\n\n15 साल trading का pain — यह platform उससे बना है। Vision big है, अभी v1 है। Honest expectations रखो।",
      // REVIEW: Gujarati rendering — native check before launch announcement
      gu: "Honest reasons:\n\n⚡ Speed: TradingView signal → broker પર order, sub-second\n🛡️ Discipline: kill switch automatic enforce કરે છે daily loss limit\n🔀 Multi-broker: એક strategy Fyers પર, એક Dhan પર — flexible\n📝 Paper mode built-in: 2 અઠવાડિયા test કરીને live જાવ\n🔒 Audit trail: SEBI compliance માટે બધા trades logged\n🤝 Founder accessible: WhatsApp / Calendly થી direct વાત\n\n15 વર્ષ trading નો pain — આ platform એમાંથી બન્યું છે. Vision big છે, હાલમાં v1 છે. Honest expectations રાખો.",
    },
    keywords: [
      "why tradetri", "why use", "kyu use", "kyu tradetri", "why",
      "क्यों use", "क्यों tradetri", "શા માટે", "કેમ tradetri",
    ],
  },
  {
    id: "tt-support",
    category: "tradetri",
    question: "How do I contact support?",
    answers: {
      hinglish:
        "Teen options:\n1. AlgoMitra (mujhse) — 24/7 yahan available\n2. WhatsApp founder — typical reply <2hrs market hours mein\n3. Calendly call book — 30 min direct slot\n\nUrgent (paisa stuck, order broke) ho toh WhatsApp use kar. Education ya planning ke liye Calendly best hai.",
      en: "Three options:\n1. AlgoMitra (me) — available 24/7 here\n2. WhatsApp the founder — typical reply <2hrs during market hours\n3. Calendly call — 30-min direct slot with the founder\n\nUrgent (money stuck, order broken)? Use WhatsApp. Education or planning conversations? Calendly is best.",
      hi: "तीन options:\n1. AlgoMitra (मुझसे) — 24/7 यहाँ available\n2. WhatsApp founder — typical reply <2hrs market hours में\n3. Calendly call book — 30 min direct slot\n\nUrgent (पैसा stuck, order broke) हो तो WhatsApp use करो। Education या planning के लिए Calendly best है।",
      gu: "ત્રણ options:\n1. AlgoMitra (મારાથી) — 24/7 અહીં available\n2. WhatsApp founder — typical reply <2hrs market hours માં\n3. Calendly call book — 30 min direct slot\n\nUrgent (પૈસા stuck, order broke) હોય તો WhatsApp use કરો. Education કે planning માટે Calendly best છે.",
    },
    keywords: ["support", "contact", "help", "founder", "मदद", "મદદ"],
  },

  // ─── Account ─────────────────────────────────────────────────────────
  {
    id: "acc-password",
    category: "account",
    question: "How do I change my password?",
    answers: {
      hinglish:
        "Settings → Profile → Change Password. Old + new password de. Strong password rakh — broker credentials yahan encrypted hain but TRADETRI password attacker ke haath laga toh wo full access pa sakta hai.",
    },
    keywords: ["password", "change", "update"],
  },
  {
    id: "acc-forgot",
    category: "account",
    question: "I forgot my password",
    answers: {
      hinglish:
        "Login page → 'Forgot Password' link → email enter kar. Reset link 5 min mein aayega. Spam folder bhi check kar. Agar email hi nahi mil raha toh founder ko WhatsApp kar manual reset ke liye.",
    },
    keywords: ["forgot", "password", "reset"],
  },
  {
    id: "acc-2fa",
    category: "account",
    question: "Is 2FA available?",
    answers: {
      hinglish:
        "TOTP-based 2FA roadmap mein hai (Phase 2). Currently strong password + JWT short expiry use karte hain. 2FA chahiye urgent toh founder ko bol — priority bump kar sakte hain.",
    },
    keywords: ["2fa", "two factor", "totp", "auth"],
  },
  {
    id: "acc-delete",
    category: "account",
    question: "How do I delete my account?",
    answers: {
      hinglish:
        "Settings → Account → Delete Account. Confirmation ke baad data 30 din mein purge ho jaata hai (compliance window). Trade history CSV download karle pehle — wo dobara nahi milegi.",
    },
    keywords: ["delete", "remove", "close", "account"],
  },
] as const;

/**
 * Cheap keyword scorer. Phase 1B will replace with embeddings.
 * Returns the best-matching FAQ or null if no question scores above 1.
 *
 * Match is language-agnostic — keywords on each FAQ include both
 * English and (for the top FAQs) native-script tokens, so a Hindi
 * user typing "Fyers कैसे जोड़ें" still hits the fyers-connect entry
 * via the "fyers" + "जोड़" keywords.
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
