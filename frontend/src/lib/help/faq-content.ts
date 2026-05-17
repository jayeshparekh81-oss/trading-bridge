/**
 * /help — static FAQ content, en + hi pairs.
 *
 * Phase 1: in-code content so launch-day support doesn't depend on a
 * CMS deploy. Phase 2 will migrate to backend-served knowledge base
 * editable via the admin console.
 *
 * Voice rules (Hinglish, not formal Devanagari):
 *   ✓ "Aapka data safe hai..."   ← conversational
 *   ✗ "आपका डेटा सुरक्षित है"   ← formal, avoid
 *
 * Adding a new FAQ:
 *   1. Pick a unique `id` (slug-style, never reused)
 *   2. Assign one of the 10 enum categories
 *   3. Write BOTH `question_en` and `question_hi` (no fallbacks)
 *   4. Write BOTH `answer_en` and `answer_hi` (markdown allowed)
 *   5. Tag with 2-5 keywords for the search index
 */

export type FAQCategory =
  | "getting-started"
  | "account"
  | "brokers"
  | "chart"
  | "strategies"
  | "backtest"
  | "live-trading"
  | "pricing"
  | "compliance"
  | "troubleshooting";

export interface FAQ {
  id: string;
  category: FAQCategory;
  question_en: string;
  question_hi: string;
  answer_en: string;
  answer_hi: string;
  tags: string[];
}

export interface CategoryMeta {
  id: FAQCategory;
  label_en: string;
  label_hi: string;
}

/** Display order is the order on the sidebar — keep deliberate. */
export const CATEGORIES: readonly CategoryMeta[] = [
  { id: "getting-started", label_en: "Getting Started", label_hi: "Shuruwat" },
  { id: "account", label_en: "Account & Login", label_hi: "Account aur Login" },
  { id: "brokers", label_en: "Brokers (Dhan / Fyers)", label_hi: "Brokers (Dhan / Fyers)" },
  { id: "chart", label_en: "Chart & Indicators", label_hi: "Chart aur Indicators" },
  { id: "strategies", label_en: "Strategies & Builder", label_hi: "Strategies aur Builder" },
  { id: "backtest", label_en: "Backtest & Paper Trading", label_hi: "Backtest aur Paper Trading" },
  { id: "live-trading", label_en: "Live Trading (Coming July 2026)", label_hi: "Live Trading (July 2026)" },
  { id: "pricing", label_en: "Pricing & Plans", label_hi: "Pricing aur Plans" },
  { id: "compliance", label_en: "Compliance & Safety", label_hi: "Compliance aur Safety" },
  { id: "troubleshooting", label_en: "Troubleshooting", label_hi: "Problem solving" },
] as const;

export const FAQS: readonly FAQ[] = [
  // ── Getting Started ──────────────────────────────────────────────
  {
    id: "what-is-tradetri",
    category: "getting-started",
    question_en: "What is TRADETRI?",
    question_hi: "TRADETRI kya hai?",
    answer_en:
      "TRADETRI is India's AI-powered algo trading platform. You can build trading strategies without writing code, backtest them on historical data, and practice in paper-trading mode with virtual money — all while connected to a real Indian broker (Dhan or Fyers). Live trading lands in July 2026.",
    answer_hi:
      "TRADETRI India ka AI-powered algo trading platform hai. Aap bina coding ke trading strategies bana sakte ho, historical data pe backtest kar sakte ho, aur paper-trading mode mein virtual money se practice kar sakte ho — saare Indian brokers (Dhan / Fyers) connect karke. Live trading July 2026 mein launch hogi.",
    tags: ["intro", "overview", "platform"],
  },
  {
    id: "how-to-create-account",
    category: "getting-started",
    question_en: "How do I create an account?",
    question_hi: "Account kaise banaye?",
    answer_en:
      "Go to `/register`, fill in name, email, phone (optional), and a password (min 8 characters). You'll get an OTP on email to verify. Once verified, you land on the dashboard with paper-mode unlocked. The whole flow is < 2 minutes.",
    answer_hi:
      "`/register` page pe jao, naam, email, phone (optional), aur password (min 8 characters) daalo. Email pe OTP aayega — verify karo. Verify hone ke baad dashboard khul jayega, paper-mode unlock ho jayega. Pura flow 2 minute se kam ka hai.",
    tags: ["signup", "register", "onboarding"],
  },
  {
    id: "first-login",
    category: "getting-started",
    question_en: "What should I do on my first login?",
    question_hi: "First login pe kya karu?",
    answer_en:
      "A 5-step welcome tour will guide you: (1) connect a broker, (2) view the live chart, (3) build a strategy, (4) understand the paper-mode banner, (5) chat with AlgoMitra. You can skip the tour anytime and restart it later from the user menu (top-right) → 'Restart tour'.",
    answer_hi:
      "First login pe ek 5-step welcome tour milega: (1) broker connect karo, (2) live chart dekho, (3) strategy banao, (4) paper-mode banner samjho, (5) AlgoMitra se baat karo. Tour kabhi bhi skip kar sakte ho, baad mein user menu (top-right) → 'Restart tour' se firse start kar sakte ho.",
    tags: ["tour", "welcome", "onboarding"],
  },
  {
    id: "virtual-money-10l",
    category: "getting-started",
    question_en: "What is the ₹10L virtual money?",
    question_hi: "₹10L virtual money kya hai?",
    answer_en:
      "Every account starts with ₹10,00,000 of virtual capital for paper trading. Buy / sell against real-time market data — orders simulate, no real broker calls. P&L tracks just like live trading. This is your practice sandbox; nothing affects your real broker account.",
    answer_hi:
      "Har account ₹10,00,000 virtual capital ke saath start hota hai paper trading ke liye. Real-time market data pe buy / sell karo — orders simulate hote hain, real broker pe nahi jaate. P&L bilkul live trading jaisa track hota hai. Yeh aapka practice sandbox hai, real broker account ko kuch nahi hota.",
    tags: ["paper", "virtual", "capital", "10L"],
  },

  // ── Account & Login ──────────────────────────────────────────────
  {
    id: "password-reset",
    category: "account",
    question_en: "How do I reset my password?",
    question_hi: "Password kaise reset karu?",
    answer_en:
      "On the `/login` page, click 'Forgot password?'. Enter your registered email — a reset link arrives within 2 minutes (check spam if not). The link is valid for 60 minutes. After clicking, set a new password (min 8 chars) and you're back in.",
    answer_hi:
      "`/login` page pe 'Forgot password?' click karo. Apna registered email daalo — 2 minute mein reset link aa jayega (spam check karo agar na mile). Link 60 minute tak valid hai. Click karke naya password (min 8 chars) set karo, aur wapas login ho jao.",
    tags: ["password", "reset", "forgot"],
  },
  {
    id: "change-email",
    category: "account",
    question_en: "How do I change my email?",
    question_hi: "Email change kaise karu?",
    answer_en:
      "Settings → Profile → 'Change email'. Enter the new email + your current password. A confirmation link goes to the new address; click it and the swap completes. Your strategies, brokers, and trade history all carry over.",
    answer_hi:
      "Settings → Profile → 'Change email'. Naya email aur current password daalo. Naye email pe confirmation link aayega — click karo, email change ho jayega. Aapki strategies, brokers, aur trade history — sab carry over ho jaate hain.",
    tags: ["email", "change", "profile"],
  },
  {
    id: "delete-account",
    category: "account",
    question_en: "How do I delete my account?",
    question_hi: "Account delete kaise karu?",
    answer_en:
      "Settings → Privacy → 'Delete account'. Confirm with your password. The account disables immediately; all personal data (strategies, trades, audit logs except legally-required) is hard-deleted within 30 days as required by DPDP Act. If you have published marketplace listings, archive them first. The action is irreversible — export anything you want to keep beforehand.",
    answer_hi:
      "Settings → Privacy → 'Delete account'. Password se confirm karo. Account turant disable ho jayega; saara personal data (strategies, trades, audit logs except legally-required) 30 din ke andar hard-delete ho jayega — DPDP Act ka requirement. Marketplace pe listings hain to pehle archive karo. Process irreversible hai — backup chahiye to pehle export karo.",
    tags: ["delete", "privacy", "dpdp"],
  },

  // ── Brokers ──────────────────────────────────────────────────────
  {
    id: "connect-dhan",
    category: "brokers",
    question_en: "How do I connect my Dhan account?",
    question_hi: "Dhan account kaise connect karu?",
    answer_en:
      "Brokers → 'Add Broker' → Dhan. Paste your Dhan client ID, API key, and the daily access token from the Dhan developer portal (web.dhan.co → Profile → API → Generate access token). The token expires every 24 hours; we'll prompt you to refresh it each morning before market open.",
    answer_hi:
      "Brokers → 'Add Broker' → Dhan. Apna Dhan client ID, API key, aur daily access token (Dhan developer portal — web.dhan.co → Profile → API → Generate access token) paste karo. Token har 24 ghante mein expire hota hai; har subah market open se pehle hum aapko refresh karne ka reminder denge.",
    tags: ["dhan", "connect", "token"],
  },
  {
    id: "why-daily-token",
    category: "brokers",
    question_en: "Why do I have to paste a new token every day?",
    question_hi: "Daily token kyu paste karna padta?",
    answer_en:
      "Dhan's API issues access tokens with a 24-hour TTL — this is the broker's security policy, not ours. We can't auto-refresh because Dhan doesn't expose a refresh-token flow for retail accounts. The daily paste is a 30-second ritual; we send a Telegram reminder if you set it up.",
    answer_hi:
      "Dhan ki API access tokens 24 ghante ke liye deti hai — yeh broker ki security policy hai, hamari nahi. Hum auto-refresh nahi kar sakte kyunki Dhan retail accounts ke liye refresh-token flow nahi deta. Roz ke 30 second ka ritual hai; Telegram reminder set kar sakte ho.",
    tags: ["token", "daily", "dhan"],
  },
  {
    id: "fyers-token-refresh",
    category: "brokers",
    question_en: "How do I refresh my Fyers token?",
    question_hi: "Fyers token kaise refresh karu?",
    answer_en:
      "Fyers uses OAuth — Brokers → your Fyers row → 'Reconnect'. The Fyers login page opens in a new tab; sign in, grant access, and you'll be redirected back with a fresh token. Unlike Dhan, Fyers tokens last 1 week, so you'll do this once a week, not daily.",
    answer_hi:
      "Fyers OAuth use karta hai — Brokers → Fyers row → 'Reconnect'. Fyers login page new tab mein khulega; sign in karke access grant karo, fresh token ke saath redirect ho jaoge. Dhan ke unlike, Fyers tokens 1 week tak chalte hain — daily nahi, weekly karna hota hai.",
    tags: ["fyers", "oauth", "refresh"],
  },
  {
    id: "switch-broker",
    category: "brokers",
    question_en: "Can I switch brokers?",
    question_hi: "Broker switch kar sakte?",
    answer_en:
      "Yes. You can have multiple brokers connected at once — each strategy picks one at run time. To replace one: Brokers → remove the old, add the new. Your strategies repoint to the new credential automatically if the broker name matches; otherwise, edit each strategy and choose the new broker in 'Execution settings'.",
    answer_hi:
      "Haan. Ek saath multiple brokers connect kar sakte ho — har strategy run time pe ek choose kar leti hai. Ek ko replace karne ke liye: Brokers → purana remove karo, naya add karo. Strategies automatic naye credential ko point kar dengi agar broker name match karta hai; nahi to har strategy mein 'Execution settings' se naya broker choose karo.",
    tags: ["broker", "switch", "multi"],
  },

  // ── Chart & Indicators ───────────────────────────────────────────
  {
    id: "chart-no-data",
    category: "chart",
    question_en: "Why isn't live chart data showing?",
    question_hi: "Chart pe live data nahi aa raha?",
    answer_en:
      "Three usual causes: (1) market is closed (Mon-Fri 9:15-15:30 IST — weekends and holidays show static history only); (2) your broker session expired — Brokers → check for a red 'Reconnect' badge; (3) you're on the 5-minute timeframe over a weekend, which only fetches the last ~16 hours of data — switch to 15m or 1d to see historical bars going back farther.",
    answer_hi:
      "Teen common reasons: (1) market closed hai (Mon-Fri 9:15-15:30 IST — weekend / holiday pe sirf static history milti hai); (2) broker session expire ho gaya — Brokers → red 'Reconnect' badge check karo; (3) 5-minute timeframe pe weekend hai — sirf last ~16 ghante ka data fetch hota hai — 15m ya 1d pe switch karo to wider history milegi.",
    tags: ["chart", "data", "empty", "weekend"],
  },
  {
    id: "add-indicators",
    category: "chart",
    question_en: "How do I add indicators to the chart?",
    question_hi: "Indicators kaise add karu?",
    answer_en:
      "Chart top bar → 'Indicators' dropdown → toggle on what you want (SMA20, EMA50, RSI, MACD, Volume). RSI and MACD render in their own bottom panes; SMA and EMA overlay on the price chart. The selection persists per-device via localStorage.",
    answer_hi:
      "Chart top bar → 'Indicators' dropdown → jo chahiye toggle karo (SMA20, EMA50, RSI, MACD, Volume). RSI aur MACD apne bottom panes mein render hote hain; SMA aur EMA price chart pe overlay hote hain. Selection localStorage mein save ho jaati hai per-device.",
    tags: ["indicators", "chart", "rsi", "macd"],
  },
  {
    id: "change-timeframe",
    category: "chart",
    question_en: "How do I change the timeframe?",
    question_hi: "Timeframe change kaise kare?",
    answer_en:
      "Chart top bar → click on a timeframe button (1m, 3m, 5m, 15m, 30m, 1h, 1d). The chart reloads with the new aggregation. For intraday strategies, 5m or 15m is the typical default; for positional, 1h or 1d.",
    answer_hi:
      "Chart top bar → koi bhi timeframe button click karo (1m, 3m, 5m, 15m, 30m, 1h, 1d). Chart naya aggregation ke saath reload ho jayega. Intraday strategies ke liye 5m ya 15m typical default hai; positional ke liye 1h ya 1d.",
    tags: ["timeframe", "interval"],
  },
  {
    id: "230-indicators",
    category: "chart",
    question_en: "Where's the full list of 230+ indicators?",
    question_hi: "230+ indicators ka list kahan hai?",
    answer_en:
      "Strategies → Builder → 'Add condition' → 'Indicators' picker shows all 230+. They're grouped: trend (SMA, EMA, MACD, Supertrend, …), momentum (RSI, Stochastic, CCI, …), volatility (ATR, BB, Keltner, …), volume (OBV, VWAP, MFI, …). The chart's Indicators dropdown is the 5-most-common subset for visual reference. Strategy logic can use any of the 230+.",
    answer_hi:
      "Strategies → Builder → 'Add condition' → 'Indicators' picker mein saare 230+ hain. Groups: trend (SMA, EMA, MACD, Supertrend, …), momentum (RSI, Stochastic, CCI, …), volatility (ATR, BB, Keltner, …), volume (OBV, VWAP, MFI, …). Chart ka Indicators dropdown sirf 5 most-common dikhata hai visual reference ke liye. Strategy logic mein saare 230+ use kar sakte ho.",
    tags: ["indicators", "list", "230"],
  },

  // ── Strategies & Builder ─────────────────────────────────────────
  {
    id: "what-is-strategy",
    category: "strategies",
    question_en: "What is a trading strategy?",
    question_hi: "Strategy kya hoti hai?",
    answer_en:
      "A strategy is a set of rules that decide when to buy and sell. Example: 'Buy NIFTY when 9-period RSI crosses above 30, sell when it crosses 70'. TRADETRI lets you express these rules visually — entry, exit, risk-management — and runs them automatically (paper-mode now, live-mode from July 2026).",
    answer_hi:
      "Strategy matlab rules ka set jo decide karte hain kab kharidna aur kab bechna. Example: 'NIFTY kharido jab 9-period RSI 30 ke upar cross kare, becho jab 70 cross kare'. TRADETRI aapko in rules ko visually likhne deta hai — entry, exit, risk-management — aur automatically run karta hai (abhi paper-mode, July 2026 se live-mode).",
    tags: ["strategy", "rules", "definition"],
  },
  {
    id: "first-strategy",
    category: "strategies",
    question_en: "How do I build my first strategy?",
    question_hi: "Pehli strategy kaise banaye?",
    answer_en:
      "Strategies → 'New strategy' → choose Beginner mode (guided wizard). Pick a symbol (NIFTY recommended for first try), a timeframe (15m), an entry condition (e.g. RSI < 30), and an exit condition (e.g. RSI > 70). Save → click 'Backtest' → see how it would have performed on the last 60 days. AlgoMitra panel on the right gives tips at each step.",
    answer_hi:
      "Strategies → 'New strategy' → Beginner mode choose karo (guided wizard). Symbol pick karo (NIFTY recommended pehli baar), timeframe (15m), entry condition (e.g. RSI < 30), aur exit condition (e.g. RSI > 70). Save → 'Backtest' click karo → last 60 din pe performance dekho. AlgoMitra panel right side pe har step pe tips deta hai.",
    tags: ["strategy", "build", "wizard", "beginner"],
  },
  {
    id: "edit-delete-strategy",
    category: "strategies",
    question_en: "How do I edit or delete a strategy?",
    question_hi: "Strategy edit/delete kaise kare?",
    answer_en:
      "Strategies list → click the strategy → 'Edit' button. Make changes, click 'Save' — a new version is created (v1, v2, v3 …). You can rollback to any past version from the 'Version History' panel. To delete: same detail page → '⋯' menu → 'Delete'. Confirmation required. Deleted strategies are soft-deleted for 30 days, then permanently removed.",
    answer_hi:
      "Strategies list → strategy click karo → 'Edit' button. Changes karke 'Save' click karo — naya version create ho jayega (v1, v2, v3 …). 'Version History' panel se kisi bhi version pe rollback kar sakte ho. Delete karne ke liye: same detail page → '⋯' menu → 'Delete'. Confirmation maangega. Deleted strategies 30 din tak soft-deleted rehti hain, phir permanently remove ho jaati hain.",
    tags: ["strategy", "edit", "delete", "version"],
  },
  {
    id: "run-strategy",
    category: "strategies",
    question_en: "How do I run a strategy?",
    question_hi: "Strategy run kaise karu?",
    answer_en:
      "Strategy detail → 'Run' button. Choose Paper or Live (Live becomes available after 7 paper-mode sessions + Trust Score pass + broker connected). The engine evaluates your conditions on every candle close; matching signals fire orders. Paper trades show up in Trades tab marked 'PAPER'. Stop anytime from the same Run panel.",
    answer_hi:
      "Strategy detail → 'Run' button. Paper ya Live choose karo (Live available hoti hai 7 paper sessions + Trust Score pass + broker connected hone ke baad). Engine har candle close pe conditions evaluate karta hai; matching signals pe orders fire hote hain. Paper trades 'PAPER' tag ke saath Trades tab mein dikhte hain. Kabhi bhi Run panel se stop kar sakte ho.",
    tags: ["strategy", "run", "execute"],
  },

  // ── Backtest & Paper Trading ─────────────────────────────────────
  {
    id: "what-is-backtest",
    category: "backtest",
    question_en: "What is backtesting?",
    question_hi: "Backtest kya hai?",
    answer_en:
      "Backtesting runs your strategy against historical data to see how it would have performed. Pick a date range, hit 'Backtest', and TRADETRI replays the market candle-by-candle, firing your rules and tracking simulated P&L, drawdown, win rate, Sharpe ratio. Useful for sanity-checking — but past performance doesn't guarantee future results.",
    answer_hi:
      "Backtest matlab strategy ko historical data pe run karna — past data pe kaisi perform karti? Date range pick karo, 'Backtest' click karo — TRADETRI market candle-by-candle replay karta hai, aapke rules fire karta hai, aur simulated P&L, drawdown, win rate, Sharpe ratio track karta hai. Sanity check ke liye useful — but past performance future results guarantee nahi karti.",
    tags: ["backtest", "history", "simulation"],
  },
  {
    id: "paper-vs-live",
    category: "backtest",
    question_en: "Paper trading vs live trading — what's the difference?",
    question_hi: "Paper trade aur live trade ka antar?",
    answer_en:
      "Paper trading uses real-time market data but virtual money; no real broker orders fire. Live trading places actual orders with your broker using real money. Both run the same strategy engine — the only difference is the order-router target. Paper is for practice; live is for production. We require 7 paper-mode sessions before unlocking live.",
    answer_hi:
      "Paper trading mein real-time market data use hota hai par virtual money se; real broker orders fire nahi hote. Live trading mein actual orders aapke broker pe real money se jaate hain. Dono same strategy engine run karte hain — sirf order-router target alag hota hai. Paper practice ke liye, live production ke liye. Live unlock hone ke liye 7 paper sessions required hain.",
    tags: ["paper", "live", "difference"],
  },
  {
    id: "backtest-report",
    category: "backtest",
    question_en: "How do I read a backtest report?",
    question_hi: "Backtest report kaise samjhe?",
    answer_en:
      "Key numbers: **Net P&L** (total profit/loss), **Win rate** (% of profitable trades — aim 50%+), **Max drawdown** (worst peak-to-trough drop — keep < 20% of capital), **Sharpe ratio** (risk-adjusted return — > 1 is decent, > 2 is great), **Trade count** (sample size — < 30 trades is suspect). Trust Score and Truth Score panels translate these into a single verdict.",
    answer_hi:
      "Important numbers: **Net P&L** (total profit/loss), **Win rate** (profitable trades ka percentage — 50%+ target karo), **Max drawdown** (worst peak-to-trough drop — capital ka 20% se kam rakho), **Sharpe ratio** (risk-adjusted return — 1 se upar decent, 2 se upar great), **Trade count** (sample size — 30 se kam trades suspect hai). Trust Score aur Truth Score panels yeh sab ek single verdict mein translate kar dete hain.",
    tags: ["backtest", "report", "metrics"],
  },

  // ── Live Trading (Coming July 2026) ──────────────────────────────
  {
    id: "live-trading-when",
    category: "live-trading",
    question_en: "When does live trading launch?",
    question_hi: "Real money se trading kab aayegi?",
    answer_en:
      "Live trading launches **July 2026**. Until then the platform is paper-only — you can practice, backtest, build, refine. The July launch unlocks the live order router for users who clear: 7+ paper sessions per strategy, Trust Score pass, Truth Score pass, and an active broker connection.",
    answer_hi:
      "Live trading **July 2026** mein launch hogi. Tab tak platform paper-only hai — practice, backtest, build, refine sab kar sakte ho. July launch ke baad live order router unlock hoga un users ke liye jinka: 7+ paper sessions per strategy, Trust Score pass, Truth Score pass, aur active broker connection ho.",
    tags: ["live", "launch", "july"],
  },
  {
    id: "live-trading-prereqs",
    category: "live-trading",
    question_en: "What do I need for live trading?",
    question_hi: "Live trade ke liye kya chahiye?",
    answer_en:
      "Four gates: (1) **Broker connected** — Dhan or Fyers with a valid token; (2) **7+ paper sessions** completed for the strategy you want to go live with; (3) **Trust Score** pass (consistent behavior, manageable drawdown); (4) **Truth Score** pass (no overfitting, no lookahead, walk-forward validated). The SafetyChain runs these checks on every live order — failures get blocked with a clear reason.",
    answer_hi:
      "Char gates: (1) **Broker connected** — Dhan ya Fyers valid token ke saath; (2) **7+ paper sessions** complete strategy ke saath jo live karni hai; (3) **Trust Score** pass (consistent behavior, manageable drawdown); (4) **Truth Score** pass (no overfitting, no lookahead, walk-forward validated). SafetyChain har live order pe yeh checks run karta hai — fail hone pe order block ho jaata hai clear reason ke saath.",
    tags: ["live", "prerequisites", "gates"],
  },
  {
    id: "sebi-compliance",
    category: "live-trading",
    question_en: "What's the SEBI compliance status?",
    question_hi: "SEBI compliance ka status?",
    answer_en:
      "TRADETRI is a self-trade execution platform — you connect your own broker account and trade your own funds. We don't act as a broker, investment advisor, or portfolio manager, so SEBI registration in those categories isn't required. We follow the Algorithmic Trading Framework guidance for retail (broker-side approval is handled by Dhan/Fyers). For the latest on SEBI's evolving algo-retail rules, see our Compliance page.",
    answer_hi:
      "TRADETRI ek self-trade execution platform hai — aap apna khud ka broker account connect karte ho aur apne funds se trade karte ho. Hum broker, investment advisor, ya portfolio manager nahi hain, isliye SEBI registration in categories mein required nahi hai. Algorithmic Trading Framework guidance for retail follow karte hain (broker-side approval Dhan/Fyers handle karte hain). SEBI ke evolving algo-retail rules ke latest update Compliance page pe milenge.",
    tags: ["sebi", "compliance", "regulation"],
  },

  // ── Pricing & Plans ──────────────────────────────────────────────
  {
    id: "current-cost",
    category: "pricing",
    question_en: "What does TRADETRI cost right now?",
    question_hi: "Abhi kya cost hai?",
    answer_en:
      "**Free** during the paper-trading phase (now through July 2026 launch). All features — chart, indicators, builder, backtest, paper mode, AlgoMitra, marketplace — are open. No credit card needed.",
    answer_hi:
      "Paper-trading phase ke dauran **free** hai (abhi se July 2026 launch tak). Saare features — chart, indicators, builder, backtest, paper mode, AlgoMitra, marketplace — open hain. Credit card ki zaroorat nahi.",
    tags: ["pricing", "free", "cost"],
  },
  {
    id: "live-pricing",
    category: "pricing",
    question_en: "What will live trading cost?",
    question_hi: "Live trading mein kya pricing hogi?",
    answer_en:
      "Final pricing publishes 2 weeks before the July launch. Direction: subscription tiers (free baseline with caps, paid tiers for higher strategy counts and marketplace creator perks). Indian market pricing — significantly less than US-platform equivalents. Existing paper-mode users get a 3-month free trial of paid tiers on switch-over.",
    answer_hi:
      "Final pricing July launch se 2 hafte pehle publish hogi. Direction: subscription tiers (free baseline with caps, paid tiers higher strategy counts aur marketplace creator perks ke liye). Indian market pricing — US-platform equivalents se kaafi kam. Existing paper-mode users ko switch-over pe paid tiers ka 3-month free trial milega.",
    tags: ["pricing", "live", "subscription"],
  },
  {
    id: "subscription-start",
    category: "pricing",
    question_en: "When does subscription billing start?",
    question_hi: "Subscription kab start hogi?",
    answer_en:
      "Not before July 2026. We won't charge anyone during the paper phase. When billing turns on, you'll get a 30-day advance email and an in-app banner — no silent charges. You can cancel anytime from Settings → Billing.",
    answer_hi:
      "July 2026 se pehle nahi. Paper phase mein kisi ko bhi charge nahi karenge. Billing on hone pe 30 din pehle email aur in-app banner milega — koi silent charge nahi. Cancel kabhi bhi Settings → Billing se kar sakte ho.",
    tags: ["pricing", "billing", "subscription"],
  },

  // ── Compliance & Safety ──────────────────────────────────────────
  {
    id: "data-safety",
    category: "compliance",
    question_en: "Is my data safe?",
    question_hi: "Mera data safe hai?",
    answer_en:
      "Yes. Broker credentials are stored encrypted (Fernet, key rotated quarterly). Passwords are hashed with bcrypt (cost factor 12). All traffic is HTTPS / WSS only. Database backups are encrypted at rest. We don't sell data to third parties — full privacy policy at `/privacy`. DPDP Act compliant for Indian users.",
    answer_hi:
      "Haan. Broker credentials encrypted (Fernet, key rotated quarterly) store hote hain. Passwords bcrypt (cost factor 12) se hash hote hain. Saara traffic HTTPS / WSS only hai. Database backups at rest encrypted hain. Hum data third parties ko bechte nahi — full privacy policy `/privacy` pe. Indian users ke liye DPDP Act compliant.",
    tags: ["security", "privacy", "data"],
  },
  {
    id: "glass-box-ai",
    category: "compliance",
    question_en: "What is Glass Box AI?",
    question_hi: "Glass Box AI kya hai?",
    answer_en:
      "Every AI decision (signal validation, strategy advice, doctor recommendations) returns a structured 'reasoning' field that explains *why* the AI chose the verdict. Stored in the audit log; viewable per-decision in the UI. No opaque black-box calls — if the AI says 'reject', you can see exactly which indicator / threshold / context drove that.",
    answer_hi:
      "Har AI decision (signal validation, strategy advice, doctor recommendations) ek structured 'reasoning' field return karta hai jo explain karta hai *kyun* AI ne yeh verdict diya. Audit log mein store hota hai; UI mein per-decision viewable. Koi opaque black-box call nahi — agar AI 'reject' bole, aap exactly dekh sakte ho kaunsa indicator / threshold / context behind that.",
    tags: ["ai", "transparency", "glass-box"],
  },
  {
    id: "kill-switch-purpose",
    category: "compliance",
    question_en: "What does the kill switch do?",
    question_hi: "Kill switch kya karta?",
    answer_en:
      "The kill switch is a safety circuit-breaker. When tripped (by you manually OR automatically when daily loss cap is breached) it: (a) cancels all pending orders across every connected broker; (b) squares off all open positions; (c) blocks new orders until reset. Reset is manual — Kill Switch page → 'Acknowledge & Resume' with confirmation. Trip events are audit-logged.",
    answer_hi:
      "Kill switch ek safety circuit-breaker hai. Trip hone pe (aapne manually ya daily loss cap breach hone pe automatic): (a) saare connected brokers pe pending orders cancel; (b) saari open positions square off; (c) reset hone tak naye orders block. Reset manual hai — Kill Switch page → 'Acknowledge & Resume' confirmation ke saath. Trip events audit-log mein record ho jaate hain.",
    tags: ["kill", "switch", "safety"],
  },

  // ── Troubleshooting ──────────────────────────────────────────────
  {
    id: "login-failing",
    category: "troubleshooting",
    question_en: "Why can't I log in?",
    question_hi: "Login nahi ho raha?",
    answer_en:
      "Three usual causes: (1) wrong email/password — use 'Forgot password' to reset; (2) email not verified yet — check inbox for the OTP email; (3) account temporarily locked after 5 failed attempts — wait 15 minutes or use password reset. If none apply, file a support ticket with your email — we'll resolve within 24h.",
    answer_hi:
      "Teen common reasons: (1) galat email/password — 'Forgot password' se reset karo; (2) email verify nahi hua — inbox mein OTP email check karo; (3) account temporarily locked 5 failed attempts ke baad — 15 minute wait karo ya password reset use karo. Inme se kuch nahi to support ticket file karo apne email ke saath — 24 ghante mein resolve karenge.",
    tags: ["login", "troubleshoot", "locked"],
  },
  {
    id: "chart-blank",
    category: "troubleshooting",
    question_en: "Why is the chart blank?",
    question_hi: "Chart blank dikh raha hai?",
    answer_en:
      "Most common cause on weekends/holidays: the 5m timeframe's 200-bar window doesn't reach back to the last trading session. Switch to 15m or 1d. If still blank on a weekday during market hours: hard-refresh (Cmd/Ctrl+Shift+R), check the Brokers page for a red 'Reconnect' badge, and verify your token isn't expired. Persistent blank → support ticket with a screenshot.",
    answer_hi:
      "Weekends / holidays pe sabse common cause: 5m timeframe ka 200-bar window last trading session tak nahi pahunchta. 15m ya 1d pe switch karo. Weekday mein market hours mein bhi blank ho to: hard-refresh (Cmd/Ctrl+Shift+R), Brokers page pe red 'Reconnect' badge check karo, aur token expire to nahi check karo. Persistent blank ho to support ticket screenshot ke saath.",
    tags: ["chart", "blank", "troubleshoot"],
  },
  {
    id: "strategy-not-running",
    category: "troubleshooting",
    question_en: "My strategy isn't running. Why?",
    question_hi: "Strategy run nahi ho rahi?",
    answer_en:
      "Check: (1) is the market open? (Mon-Fri 9:15-15:30 IST only); (2) is the strategy actually started? Strategy detail → 'Run' panel should show 'Running' green dot; (3) is your broker connected? Brokers page → green status; (4) check the Trades tab — even if no entry has fired, the engine might be evaluating but no signal matched yet. If all four are green and nothing fires after a session, the rules may simply be too tight — review entry conditions.",
    answer_hi:
      "Check karo: (1) market open hai? (Mon-Fri 9:15-15:30 IST only); (2) strategy actually start hui hai? Strategy detail → 'Run' panel pe 'Running' green dot dikhna chahiye; (3) broker connected hai? Brokers page → green status; (4) Trades tab check karo — entry fire nahi bhi hua to engine evaluating ho rahi hogi but signal match nahi hua. Chaaron green hain aur ek session mein kuch fire nahi hua to rules zyada tight hain shayad — entry conditions review karo.",
    tags: ["strategy", "run", "troubleshoot"],
  },
  {
    id: "contact-support",
    category: "troubleshooting",
    question_en: "How do I contact support?",
    question_hi: "Support contact kaise kare?",
    answer_en:
      "Three ways, in order of speed: (1) **AlgoMitra chat** (bottom-right floating button) — instant answers to common questions, no waiting; (2) **Support ticket** (`/support` → 'Naya Ticket') — human reply in 24-48 hours, with priority routing for billing / broker connection / critical bugs; (3) **Email** support@tradetri.com — same backlog as tickets, slightly slower because manual triage. For urgent kill-switch resets, the ticket form is fastest.",
    answer_hi:
      "Teen tarike, speed ke order mein: (1) **AlgoMitra chat** (bottom-right floating button) — common questions ke instant answer, no waiting; (2) **Support ticket** (`/support` → 'Naya Ticket') — 24-48 ghante mein human reply, billing / broker connection / critical bugs ke liye priority routing; (3) **Email** support@tradetri.com — tickets jaisa hi backlog, slightly slower manual triage ki wajah se. Urgent kill-switch reset ke liye ticket form fastest hai.",
    tags: ["support", "contact", "ticket"],
  },

  // ── Wave 2 — Advanced Strategy (in 'strategies' category) ─────────
  {
    id: "interpret-backtest-results",
    category: "strategies",
    question_en: "How do I interpret backtest results properly?",
    question_hi: "Backtest results sahi se kaise interpret karu?",
    answer_en:
      "Look at five numbers in order: **Total trades** (< 30 is statistically suspect — small-sample noise dominates), **Win rate** (50-60% is healthy for most setups; >70% is suspiciously curve-fit), **Max drawdown** (keep < 20% of capital — anything worse means the strategy will be psychologically untradeable in live), **Profit factor** (gross-profit / gross-loss — > 1.5 is good, > 2.0 is exceptional), and **Sharpe ratio** (risk-adjusted return — > 1.0 acceptable, > 2.0 strong). A strategy that's strong on all five is rare; most have trade-offs. Use Trust Score + Truth Score panels — they distil these five into a single verdict.",
    answer_hi:
      "Paanch numbers order mein dekho: **Total trades** (< 30 statistically suspect — small-sample noise dominate karta), **Win rate** (50-60% most setups ke liye healthy; >70% suspiciously curve-fit), **Max drawdown** (capital ka 20% se kam rakho — usse worse hua to live mein strategy psychologically untradeable ho jayegi), **Profit factor** (gross-profit / gross-loss — > 1.5 good, > 2.0 exceptional), aur **Sharpe ratio** (risk-adjusted return — > 1.0 acceptable, > 2.0 strong). Strategy jo paanchon pe strong ho woh rare hai; most mein trade-offs hote. Trust Score + Truth Score panels use karo — yeh paanchon ko ek verdict mein distil karte.",
    tags: ["backtest", "interpretation", "metrics", "advanced"],
  },
  {
    id: "strategy-lifecycle",
    category: "strategies",
    question_en: "What's the typical lifecycle of a trading strategy?",
    question_hi: "Trading strategy ka typical lifecycle kya hota hai?",
    answer_en:
      "Four phases: (1) **Discovery** — backtest looks great, you're excited. Don't go live yet. (2) **Paper validation** — 7+ paper sessions on TRADETRI. Strategy survives real-time tape with slippage / partial fills modelled. Most 'great backtests' die here. (3) **Small-money live** — once Live Trading launches (July 2026), start with 25-50% of intended size. Watch for slippage / fills divergence from paper. (4) **Decay** — every strategy decays as the market changes. Track rolling 30-day Sharpe and exit when it drops below 0.5 sustained. Average alpha-strategy half-life in Indian retail is 6-18 months. Plan for retirement from day 1.",
    answer_hi:
      "Char phases: (1) **Discovery** — backtest great lagta, aap excited. Live mat jao abhi. (2) **Paper validation** — 7+ paper sessions TRADETRI pe. Strategy real-time tape pe slippage / partial fills ke saath survive kare. Most 'great backtests' yahin die karte. (3) **Small-money live** — Live Trading launch hone ke baad (July 2026), intended size ka 25-50% se start. Slippage / fills divergence paper se watch karo. (4) **Decay** — har strategy market change hone ke saath decay hoti. Rolling 30-day Sharpe track karo, sustained 0.5 ke neeche aaye to exit karo. Indian retail mein average alpha-strategy half-life 6-18 months hoti. Day 1 se retirement plan karo.",
    tags: ["strategy", "lifecycle", "decay", "advanced"],
  },
  {
    id: "when-to-retire-strategy",
    category: "strategies",
    question_en: "When should I retire a strategy?",
    question_hi: "Strategy kab retire karu?",
    answer_en:
      "Five signals (any TWO trigger retirement consideration): (1) Rolling 30-day Sharpe drops below 0.5 and stays there for 2+ weeks. (2) Max drawdown breaches 1.5× the backtest's worst drawdown — the strategy is operating outside its tested envelope. (3) The market regime has visibly changed (e.g. a trend-following strategy on NIFTY when NIFTY enters multi-month chop). (4) Three consecutive losing weeks with positions sized normally. (5) Trust Score panel flags 'decay'. Don't retire on a single bad week — random variance is real. Don't HOLD ON forever — strategies decay structurally, not just stochastically.",
    answer_hi:
      "Paanch signals (koi do = retirement consideration): (1) Rolling 30-day Sharpe 0.5 ke neeche aaye aur 2+ weeks tak rahe. (2) Max drawdown backtest ke worst drawdown ka 1.5× breach kare — strategy tested envelope ke bahar operate kar rahi. (3) Market regime visibly change ho gaya (e.g. NIFTY pe trend-following strategy jab NIFTY multi-month chop mein chala jaye). (4) Teen consecutive losing weeks positions normally sized. (5) Trust Score panel 'decay' flag kare. Single bad week pe retire mat karo — random variance real hai. Forever HOLD mat karo — strategies structurally decay hoti, sirf stochastically nahi.",
    tags: ["strategy", "retirement", "decay", "advanced"],
  },
  {
    id: "walk-forward-vs-backtest",
    category: "strategies",
    question_en: "What's the difference between backtest and walk-forward?",
    question_hi: "Backtest aur walk-forward mein kya antar hai?",
    answer_en:
      "**Backtest** runs the strategy on a single historical period — you see how it would have performed. The big risk is **curve-fitting**: tuning parameters until they perfectly fit that past period. The strategy 'works' on the tested data and fails on new data.\n\n**Walk-forward** addresses this. Split the history into N segments; on each segment, tune parameters using ONLY data before that segment, then evaluate on the segment. If performance holds across segments, the strategy is robust; if it crashes on some segments, it was curve-fit.\n\nTRADETRI's Truth Score uses walk-forward implicitly — it checks that backtest performance doesn't decay catastrophically when you slice the history forward. A backtest with Sharpe 2.5 but walk-forward Sharpe 0.3 is a curve-fit warning.",
    answer_hi:
      "**Backtest** strategy ko single historical period pe run karta — past performance dikhata. Bada risk **curve-fitting**: parameters ko tune karte raho jab tak woh past period pe perfectly fit ho jayein. Tested data pe strategy 'kaam karti hai' aur new data pe fail ho jaati.\n\n**Walk-forward** isko address karta. History ko N segments mein split karo; har segment pe, parameters tune karo USING ONLY segment se pehle ka data, phir segment pe evaluate. Performance segments ke across hold ho to strategy robust; kuch segments pe crash kare to curve-fit thi.\n\nTRADETRI ka Truth Score walk-forward implicitly use karta — check karta ki backtest performance history forward slice karne pe catastrophically decay nahi karti. Backtest Sharpe 2.5 but walk-forward Sharpe 0.3 = curve-fit warning.",
    tags: ["backtest", "walk-forward", "validation", "advanced"],
  },
  {
    id: "single-vs-portfolio-strategies",
    category: "strategies",
    question_en: "Should I run one strategy or many?",
    question_hi: "Ek strategy run karu ya many?",
    answer_en:
      "Portfolio of 3-5 uncorrelated strategies beats any single strategy on risk-adjusted return — by a wide margin if their correlations are genuinely low (Sharpe stacks; drawdowns smooth out). The hard part is finding 3-5 strategies that AREN'T highly correlated. EMA crossover + Supertrend + RSI mean-reversion all sound different but tend to fire similar trades during big trends. Better diversifiers: one momentum + one mean-reversion + one volatility-breakout + one volume-based. Use TRADETRI's correlation panel (Phase 4 feature) to verify low correlation between candidates.",
    answer_hi:
      "3-5 uncorrelated strategies ka portfolio risk-adjusted return pe single strategy se beat karta — wide margin se agar correlations genuinely low ho (Sharpe stack hote, drawdowns smooth out hote). Mushkil part 3-5 strategies dhoondna jo HIGHLY correlated NA hon. EMA crossover + Supertrend + RSI mean-reversion sab different sound karte but big trends mein similar trades fire karte. Better diversifiers: ek momentum + ek mean-reversion + ek volatility-breakout + ek volume-based. TRADETRI ka correlation panel (Phase 4 feature) use karo verify karne ke liye candidates ke beech low correlation hai.",
    tags: ["portfolio", "diversification", "correlation", "advanced"],
  },

  // ── Wave 2 — Indicator Combinations (in 'strategies' category) ────
  {
    id: "complementary-indicators",
    category: "strategies",
    question_en: "Which indicators work well together?",
    question_hi: "Konse indicators saath mein accha kaam karte?",
    answer_en:
      "Pair across categories, not within. **Good pairs**: trend (EMA, Supertrend) + momentum (RSI, MACD) + volume (VWAP, OBV). The three legs answer different questions — direction, strength, participation — and three independent confirmations beat any single high-quality signal.\n\n**Bad pairs**: RSI + Stochastic + Williams %R together — all three measure roughly the same thing (overbought/oversold via close position in range). Three correlated reads aren't three independent confirmations; they're one read counted three times.\n\nRule of thumb: when picking a second indicator for an existing strategy, ask 'does this measure something my first indicator can't?'. If no, drop it.",
    answer_hi:
      "Categories ke across pair karo, within nahi. **Good pairs**: trend (EMA, Supertrend) + momentum (RSI, MACD) + volume (VWAP, OBV). Teen legs different sawal answer karte — direction, strength, participation — aur teen independent confirmations single high-quality signal se beat karte.\n\n**Bad pairs**: RSI + Stochastic + Williams %R ek saath — teenon roughly same cheez measure karte (close position in range ke through overbought/oversold). Teen correlated reads teen independent confirmations nahi hote; ek read teen baar count ho raha.\n\nRule of thumb: existing strategy ke liye second indicator pick karte time poocho 'kya yeh mere first indicator se different cheez measure karta?'. No to drop karo.",
    tags: ["indicators", "combinations", "diversification", "advanced"],
  },
  {
    id: "conflicting-signals",
    category: "strategies",
    question_en: "What if my indicators give conflicting signals?",
    question_hi: "Indicators conflicting signals dein to kya karu?",
    answer_en:
      "Most of the time, **stand aside**. Conflicting indicators usually mean the market is in transition between regimes — entering then is low-edge. If you must trade: rank your indicators by hierarchy. Trend (e.g. 200-EMA) is usually the most reliable; respect it first. Momentum is second-tier. Oscillators are last because they signal in both trends and chop.\n\nIf trend says 'up' and oscillator says 'overbought', the trend wins — overbought during uptrends is normal. If trend says 'flat' and oscillator says 'reversing', stand aside — no trend means no edge for trend-following or counter-trend.",
    answer_hi:
      "Most of the time, **stand aside**. Conflicting indicators usually matlab market regimes ke beech transition mein hai — tab enter karna low-edge hai. Trade karna hi hai to: indicators ko hierarchy se rank karo. Trend (e.g. 200-EMA) usually most reliable; pehle uska respect karo. Momentum second-tier. Oscillators last kyunki trends aur chop dono mein signal karte.\n\nTrend 'up' kahe aur oscillator 'overbought' kahe to trend wins — uptrends mein overbought normal hai. Trend 'flat' kahe aur oscillator 'reversing' kahe to stand aside — trend nahi matlab trend-following ya counter-trend dono ke liye edge nahi.",
    tags: ["indicators", "conflict", "decision", "advanced"],
  },
  {
    id: "how-many-indicators",
    category: "strategies",
    question_en: "How many indicators should a strategy use?",
    question_hi: "Strategy mein kitne indicators use karu?",
    answer_en:
      "**Two to four**. Below 2: signal is one-dimensional and noisy. Above 4: the indicators start contradicting each other so often that the strategy never fires (or worse, you start curve-fitting to make them agree). The sweet spot for most Indian retail strategies is **3**: one trend filter, one entry trigger, one exit signal. The 'trade only when all 3 agree' rule is restrictive enough to keep quality high and permissive enough to fire several times a week on a typical F&O stock.",
    answer_hi:
      "**Do se char**. 2 ke neeche: signal one-dimensional aur noisy. 4 ke upar: indicators itne baar contradict karte ki strategy fire hi nahi karti (ya worse, agree karwane ke liye curve-fit karne lagte ho). Most Indian retail strategies ka sweet spot **3** hai: ek trend filter, ek entry trigger, ek exit signal. 'Trade only when all 3 agree' rule itna restrictive ki quality high rehti aur itna permissive ki typical F&O stock pe weekly several baar fire ho.",
    tags: ["indicators", "count", "design", "advanced"],
  },
  {
    id: "trend-vs-momentum-vs-volume",
    category: "strategies",
    question_en: "What's the difference between trend, momentum, and volume indicators?",
    question_hi: "Trend, momentum, aur volume indicators mein kya antar hai?",
    answer_en:
      "**Trend** = direction over time. EMA, SMA, Supertrend, ADX. Answers 'are we going up, down, or sideways?'. **Momentum** = rate of change. RSI, MACD, Stochastic. Answers 'how fast is the move happening?'. **Volume** = participation. OBV, VWAP, MFI, CMF. Answers 'who's driving this move and how much money is involved?'.\n\nA complete strategy benefits from one of each. Trend tells you the regime; momentum confirms the regime is alive (not stale); volume confirms it's institutionally backed (not retail noise).",
    answer_hi:
      "**Trend** = time over direction. EMA, SMA, Supertrend, ADX. Answer karta 'up, down, ya sideways jaa rahe?'. **Momentum** = rate of change. RSI, MACD, Stochastic. Answer karta 'move kitna fast ho raha?'. **Volume** = participation. OBV, VWAP, MFI, CMF. Answer karta 'kaun drive kar raha aur kitna paisa involved hai?'.\n\nComplete strategy mein har ek se ek benefit karta. Trend regime batata; momentum confirm karta regime alive hai (stale nahi); volume confirm karta institutionally backed hai (retail noise nahi).",
    tags: ["indicators", "categories", "fundamentals", "advanced"],
  },
  {
    id: "indicator-period-tuning",
    category: "strategies",
    question_en: "How do I choose indicator periods?",
    question_hi: "Indicator periods kaise choose karu?",
    answer_en:
      "Start with platform defaults — they're defaults because they work across most setups. Don't 'optimise' periods aggressively unless you have a specific reason. RSI(14), EMA(20/50/200), MACD(12, 26, 9), Bollinger(20, 2), ATR(14) are the standards for a reason.\n\nIf your strategy needs faster signals (intraday F&O), halve the periods. Slower (weekly positional), double them. **Avoid odd specific tunings** like RSI(17) — they're a red flag for curve-fitting. The strategy should work on RSI(14) AND RSI(13) AND RSI(15) with similar results; if it only works on RSI(17), you've overfit.",
    answer_hi:
      "Platform defaults se start karo — defaults hain kyunki most setups pe kaam karte. Periods aggressively 'optimise' mat karo unless specific reason ho. RSI(14), EMA(20/50/200), MACD(12, 26, 9), Bollinger(20, 2), ATR(14) standards hain reason ke saath.\n\nStrategy ko faster signals chahiye (intraday F&O) to periods halve karo. Slower (weekly positional) to double. **Odd specific tunings** jaise RSI(17) **avoid karo** — curve-fitting ka red flag. Strategy RSI(14) AND RSI(13) AND RSI(15) pe similar results dena chahiye; sirf RSI(17) pe kaam kare to overfit kar liya.",
    tags: ["indicators", "tuning", "periods", "advanced"],
  },

  // ── Wave 2 — Risk Management (in 'compliance' category) ───────────
  {
    id: "position-sizing-basics",
    category: "compliance",
    question_en: "How do I size positions correctly?",
    question_hi: "Positions ki size sahi se kaise rakhu?",
    answer_en:
      "Two-step recipe: (1) Decide **risk per trade** as a fraction of total capital — 1-2% is the textbook range. For ₹2L capital, that's ₹2,000-₹4,000 risk per trade. (2) Compute position size such that 'stop-loss hit' loses exactly that ₹ amount. Position size (shares/lots) = (risk_₹) / (stop_distance_₹_per_share).\n\nNEVER risk more than 2% per trade. Risk of ruin compounds — five consecutive 5% losses leaves you with 77% of capital and an uphill mathematical climb to recover. Five consecutive 1% losses leaves 95%, easily recoverable. Indian retail's #1 cause of blow-ups is oversizing.",
    answer_hi:
      "Do-step recipe: (1) **Risk per trade** decide karo total capital ka fraction — 1-2% textbook range. ₹2L capital ke liye, ₹2,000-₹4,000 risk per trade. (2) Position size compute karo aise ki 'stop-loss hit' exactly woh ₹ amount lose kare. Position size (shares/lots) = (risk_₹) / (stop_distance_₹_per_share).\n\n2% se zyada per trade KABHI risk mat karo. Risk of ruin compound karta — five consecutive 5% losses 77% capital chhodte aur uphill mathematical climb recover karne ke liye. Five consecutive 1% losses 95% chhodte, easily recoverable. Indian retail ke blow-ups ka #1 cause oversizing hai.",
    tags: ["risk", "sizing", "capital", "drawdown"],
  },
  {
    id: "kill-switch-when-to-use",
    category: "compliance",
    question_en: "When should I manually trip the kill switch?",
    question_hi: "Kill switch manually kab trip karna chahiye?",
    answer_en:
      "Four scenarios: (1) You're in a tilt — frustration / FOMO / revenge-trading. Stop everything and walk away. (2) Daily loss is approaching your max threshold (typically 4% of capital). Manual trip locks the threshold before automation does. (3) You see something wrong with broker fills (orders rejected, double-filled, weird slippage) — kill first, investigate after. (4) Major surprise event — RBI announcement, geopolitical shock, exchange outage. Kill while you assess.\n\nResetting after a trip is intentionally a manual two-step process (request token, then confirm) so you can't kill-and-reset reflexively. Cool-off is the feature, not the bug.",
    answer_hi:
      "Char scenarios: (1) Tilt mein ho — frustration / FOMO / revenge-trading. Sab band karo aur walk away. (2) Daily loss max threshold approach kar raha (typically 4% capital). Manual trip threshold ko automation se pehle lock karta. (3) Broker fills mein kuch galat dikhe (orders rejected, double-filled, weird slippage) — kill pehle, investigate baad mein. (4) Major surprise event — RBI announcement, geopolitical shock, exchange outage. Assess karte time kill.\n\nTrip ke baad reset intentionally manual two-step process hai (request token, phir confirm) taaki reflexively kill-and-reset na ho. Cool-off feature hai, bug nahi.",
    tags: ["kill-switch", "risk", "psychology", "discipline"],
  },
  {
    id: "drawdown-handling",
    category: "compliance",
    question_en: "What do I do during a drawdown?",
    question_hi: "Drawdown ke time kya karu?",
    answer_en:
      "**Do not increase position size to 'recover faster'.** That's the textbook way to turn a 10% drawdown into a 50% drawdown. Three rules: (1) **Cut size** — if you're in a 10%+ drawdown, halve your position sizes until you recover to within 5% of peak. (2) **Don't change the strategy** mid-drawdown — random tinkering during emotional pain destroys long-term edge. Either the strategy is still valid (sit through it) or it's broken (retire it and start fresh — but make that call cold, not during pain). (3) **Take a break** if the drawdown is causing visible behavioural changes (sleep loss, mood). The market will still be there.",
    answer_hi:
      "**Position size INCREASE mat karo 'faster recover' karne ke liye.** Yeh textbook tarika hai 10% drawdown ko 50% banane ka. Teen rules: (1) **Size cut karo** — 10%+ drawdown mein ho to position sizes halve karo jab tak peak ke 5% ke andar recover na ho jao. (2) **Strategy MID-DRAWDOWN change mat karo** — emotional pain ke time random tinkering long-term edge destroy karta. Ya strategy valid hai (sit through) ya broken hai (retire karke fresh start — but yeh decision cold lo, pain mein nahi). (3) **Break lo** agar drawdown visible behavioural changes (sleep loss, mood) cause kar raha. Market wahin hai.",
    tags: ["drawdown", "risk", "psychology", "discipline"],
  },
  {
    id: "leverage-warning",
    category: "compliance",
    question_en: "Is leverage in F&O dangerous?",
    question_hi: "F&O ka leverage dangerous hai?",
    answer_en:
      "Yes — F&O notional exposure is 5-10× the margin you put up. A 2% move in NIFTY = ~20% move in your margin. **Most Indian retail F&O accounts lose money** (SEBI's own study put the number at ~89%); leverage is the biggest contributor. Two rules: (1) Compute your stop-loss in MARGIN terms, not just price terms — 'stop at ₹X price' might be 30% of your margin even if it's only 1% of price. (2) Trade smaller than you think you should. The right F&O position size on ₹2L is usually 1-2 lots of NIFTY, not 5-10 — the math of catastrophic loss is unforgiving.",
    answer_hi:
      "Haan — F&O notional exposure aapke put-up margin ka 5-10× hota. NIFTY mein 2% move = aapke margin pe ~20% move. **Most Indian retail F&O accounts paise lose karte hain** (SEBI ki khud ki study ne ~89% number diya); leverage biggest contributor hai. Do rules: (1) Stop-loss MARGIN terms mein compute karo, sirf price terms mein nahi — 'stop at ₹X price' aapke margin ka 30% ho sakta even if price ka sirf 1% hai. (2) Aap jitna sochte ho usse chhota trade karo. ₹2L pe right F&O position size usually 1-2 lots NIFTY, 5-10 nahi — catastrophic loss ka math unforgiving hai.",
    tags: ["leverage", "f&o", "risk", "sizing"],
  },
  {
    id: "stop-loss-discipline",
    category: "compliance",
    question_en: "How strict should I be with stop-losses?",
    question_hi: "Stop-loss ke saath kitna strict hona chahiye?",
    answer_en:
      "**Absolute, no exceptions.** Moving a stop-loss further away to 'give the trade more room' is the single most damaging habit in retail trading. The moment you do it, you've stopped having a strategy and started managing emotions. Three rules: (1) Set the stop BEFORE you enter — not after. (2) Use TRADETRI's automated stop-loss (order placed at broker level) rather than mental stops. The order can be cancelled by you intentionally but won't accidentally drift. (3) When a stop hits, do NOT re-enter the same direction immediately. Wait at least 30 minutes; better yet, the next session. The setup that failed is unlikely to suddenly work 5 minutes later.",
    answer_hi:
      "**Absolute, no exceptions.** Trade ko 'aur room' dene ke liye stop-loss further move karna retail trading ka sabse damaging habit hai. Jis moment yeh karte ho, strategy band aur emotions manage shuru ho jaate. Teen rules: (1) Stop ENTRY se pehle set karo — baad mein nahi. (2) Mental stops ke bajaye TRADETRI ka automated stop-loss use karo (broker level pe order placed). Order intentionally aap cancel kar sakte but accidentally drift nahi karega. (3) Stop hit ho to same direction mein IMMEDIATELY re-enter mat karo. At least 30 min wait karo; better next session. Failed setup 5 minutes later suddenly kaam karne ki sambhavna kam hai.",
    tags: ["stop-loss", "discipline", "risk"],
  },

  // ── Wave 2 — Indian Market Specifics (in 'live-trading' category) ─
  {
    id: "expiry-day-quirks",
    category: "live-trading",
    question_en: "What's special about NSE expiry days?",
    question_hi: "NSE expiry days mein kya special hota hai?",
    answer_en:
      "NIFTY weekly options expire Thursday. BANKNIFTY Wednesday (recent change — verify current schedule). FINNIFTY Tuesday. On the expiry day itself, three things happen: (1) **OI unwinding** drives unusual intraday volatility, especially in the last 90 minutes (~2:00-3:30 PM IST). Strategies that work on normal days often fail here. (2) **Gamma squeezes** — option Greeks compress; small index moves can cause large option-price moves. (3) **Settlement levels matter** — many strategies depend on the closing settlement price, not intraday lows/highs.\n\nGeneral advice: take fewer intraday positions on expiry days; tighten stops; don't enter new positions in the last 90 minutes unless that's specifically your edge.",
    answer_hi:
      "NIFTY weekly options Thursday expire hote. BANKNIFTY Wednesday (recent change — current schedule verify karo). FINNIFTY Tuesday. Expiry day pe khud teen cheezein hoti: (1) **OI unwinding** unusual intraday volatility drive karta, especially last 90 minutes mein (~2:00-3:30 PM IST). Normal days pe kaam karne wali strategies yahan often fail. (2) **Gamma squeezes** — option Greeks compress hote; small index moves bade option-price moves cause karte. (3) **Settlement levels matter** — many strategies closing settlement price pe depend karti, intraday lows/highs pe nahi.\n\nGeneral advice: expiry days pe fewer intraday positions lo; stops tighten karo; last 90 minutes mein new positions tabhi enter karo jab specifically wahi aapka edge ho.",
    tags: ["expiry", "f&o", "nifty", "indian-market"],
  },
  {
    id: "circuit-breakers",
    category: "live-trading",
    question_en: "How do NSE/BSE circuit breakers work?",
    question_hi: "NSE/BSE circuit breakers kaise kaam karte?",
    answer_en:
      "Two layers: (1) **Stock-level circuits** — every stock has a daily price band (2/5/10/20% depending on liquidity/F&O status). If the stock hits the band, trading pauses for that stock until the next session's adjusted band. F&O stocks usually have wider bands or no individual band. (2) **Index-level circuits** — if NIFTY moves 10/15/20% in a single session, the whole market halts (15-minute / 45-minute / rest-of-day pauses respectively). Trading-bridge strategies cannot execute during a circuit; pending orders queue or get rejected depending on broker.\n\nFor practical purposes: circuit breakers fire rarely (a few times per year on individual stocks; index circuits are once-in-multi-year events). But when they do, paper-trade backtests miss them and live trades can fail in unexpected ways.",
    answer_hi:
      "Do layers: (1) **Stock-level circuits** — har stock ki daily price band hoti (2/5/10/20% liquidity/F&O status pe depend). Stock band hit kare to woh stock pause ho jaata next session ki adjusted band tak. F&O stocks ki usually wider bands ya individual band nahi. (2) **Index-level circuits** — NIFTY ek session mein 10/15/20% move kare to pura market halt hota (respectively 15-minute / 45-minute / rest-of-day pauses). Circuit ke dauran trading-bridge strategies execute nahi kar sakti; pending orders broker pe depend karke queue ya reject hote.\n\nPractical purposes: circuit breakers rare fire karte (individual stocks pe per year kuch baar; index circuits once-in-multi-year events). But jab hote hain, paper-trade backtests inhe miss karte aur live trades unexpected tarike se fail kar sakte.",
    tags: ["circuits", "halt", "nse", "bse", "indian-market"],
  },
  {
    id: "bse-vs-nse",
    category: "live-trading",
    question_en: "BSE aur NSE mein kya antar hai?",
    question_hi: "BSE aur NSE mein kya antar hai?",
    answer_en:
      "Both are stock exchanges in India, but their dominance differs by segment. **Equity**: NSE handles ~93% of total Indian equity volume; BSE ~7%. For liquid trades, NSE is the default. **F&O**: NSE dominates with NIFTY / BANKNIFTY / FINNIFTY indices and most stock futures. BSE has SENSEX futures + a handful of stock derivatives — much lower volume. **Commodities**: MCX is the main commodities exchange; NSE and BSE have limited offerings.\n\nFor TRADETRI users: most strategies run on NSE because that's where the liquidity is. BSE-only stocks exist but are rare in retail F&O. The Dhan / Fyers APIs handle both exchanges seamlessly — you specify the exchange when picking a symbol.",
    answer_hi:
      "Dono India ke stock exchanges hain, but segment ke saath dominance alag. **Equity**: NSE total Indian equity volume ka ~93% handle karta; BSE ~7%. Liquid trades ke liye NSE default. **F&O**: NSE NIFTY / BANKNIFTY / FINNIFTY indices aur most stock futures ke saath dominate karta. BSE ke paas SENSEX futures + kuch stock derivatives hain — much lower volume. **Commodities**: MCX main commodities exchange; NSE aur BSE ki limited offerings.\n\nTRADETRI users ke liye: most strategies NSE pe run karti hain kyunki liquidity wahin hai. BSE-only stocks exist karte hain but retail F&O mein rare. Dhan / Fyers APIs dono exchanges ko seamlessly handle karti — aap symbol pick karte time exchange specify karte ho.",
    tags: ["nse", "bse", "exchange", "liquidity", "indian-market"],
  },
  {
    id: "muhurat-trading",
    category: "live-trading",
    question_en: "What is Muhurat trading?",
    question_hi: "Muhurat trading kya hota hai?",
    answer_en:
      "Muhurat trading is a one-hour-ish ceremonial trading session held on Diwali (typically evening, ~6:15-7:15 PM IST). It marks the start of the new Samvat year in Indian trading tradition. Token transactions and a token volume are recorded — the prices are real but the session is symbolic, not a normal market day.\n\nFor algo / strategy traders: most platforms (Dhan, Fyers) do NOT support automated order placement during Muhurat — it's a manual session. Don't expect your strategies to fire. If you participate, it's typically a one-off ceremonial trade (buy a few shares of a favourite stock for sentiment). Skip the day from systematic backtests; it's not statistically representative of a normal session.",
    answer_hi:
      "Muhurat trading ek one-hour-ish ceremonial trading session hai jo Diwali pe hota (typically evening, ~6:15-7:15 PM IST). Indian trading tradition mein new Samvat year ka start mark karta. Token transactions aur token volume record hote — prices real but session symbolic hai, normal market day nahi.\n\nAlgo / strategy traders ke liye: most platforms (Dhan, Fyers) Muhurat ke dauran automated order placement support NAHI karte — manual session hai. Strategies fire honge mat expect karo. Participate karte ho to typically one-off ceremonial trade hota (favourite stock ke kuch shares sentiment ke liye buy). Systematic backtests se yeh day skip karo; statistically normal session ka representative nahi.",
    tags: ["muhurat", "diwali", "ceremonial", "indian-market"],
  },
  {
    id: "rbi-policy-impact",
    category: "live-trading",
    question_en: "How do RBI policy announcements affect trading?",
    question_hi: "RBI policy announcements trading ko kaise affect karte?",
    answer_en:
      "RBI Monetary Policy Committee (MPC) meets roughly every 2 months. Announcements (usually 10:00-11:00 AM IST on day 3 of the meeting) can cause: (1) **Volatility spike** in the 30 minutes around announcement — sharp moves in NIFTY, BANKNIFTY, INR, and rate-sensitive sectors (banks, NBFCs, real estate). (2) **Direction depends on surprise** — if RBI matches consensus, muted reaction; if it dovish-surprises (rate cut, accommodative tone), banks rally + INR weakens; if hawkish-surprises, reverse.\n\nStrategy advice: avoid new entries 30 minutes before / 30 minutes after the announcement window. Tighten stops on existing positions. Backtests rarely capture event-day microstructure accurately, so live behaviour can diverge.",
    answer_hi:
      "RBI Monetary Policy Committee (MPC) roughly har 2 months mein meet karta. Announcements (usually meeting ke day 3 pe 10:00-11:00 AM IST) cause kar sakte: (1) **Volatility spike** announcement ke around 30 minutes mein — NIFTY, BANKNIFTY, INR, aur rate-sensitive sectors (banks, NBFCs, real estate) mein sharp moves. (2) **Direction surprise pe depend karta** — RBI consensus match kare to muted reaction; dovish-surprise (rate cut, accommodative tone) kare to banks rally + INR weakens; hawkish-surprise to reverse.\n\nStrategy advice: announcement window se 30 minutes pehle / 30 minutes baad new entries avoid karo. Existing positions ke stops tighten karo. Backtests rarely event-day microstructure accurately capture karte, so live behaviour diverge ho sakti.",
    tags: ["rbi", "policy", "macro", "event", "indian-market"],
  },

  // ── Wave 2 — Tax & Compliance (in 'compliance' category) ──────────
  {
    id: "stcg-ltcg-basics",
    category: "compliance",
    question_en: "What are STCG and LTCG?",
    question_hi: "STCG aur LTCG kya hote?",
    answer_en:
      "**STCG (Short-Term Capital Gains)**: profits from equity held < 12 months. Taxed at 15% (FY 2025-26; verify current rate at the time you're reading). **LTCG (Long-Term Capital Gains)**: profits from equity held ≥ 12 months. Taxed at 10% on gains above ₹1L per financial year (FY 2025-26 thresholds).\n\nFor active traders, almost all profits are STCG — the 12-month hold rule rarely applies to short-term strategies. F&O profits are NOT capital gains at all — they're treated as **business income** (see the F&O tax FAQ). Always consult a CA for your specific situation; tax law in India changes frequently in budget updates.",
    answer_hi:
      "**STCG (Short-Term Capital Gains)**: equity 12 months se kam hold ki gain. 15% taxed (FY 2025-26; current rate verify karo jab padh rahe ho). **LTCG (Long-Term Capital Gains)**: equity 12 months ya zyada hold ki gain. ₹1L per financial year se upar ki gains pe 10% taxed (FY 2025-26 thresholds).\n\nActive traders ke liye, almost saari profits STCG — 12-month hold rule short-term strategies pe rarely apply hota. F&O profits capital gains NAHI hain — **business income** treat hoti hain (F&O tax FAQ dekho). Apne specific situation ke liye CA se consult karo; tax law India mein budget updates mein frequently change hota.",
    tags: ["tax", "stcg", "ltcg", "equity", "compliance"],
  },
  {
    id: "fno-tax-treatment",
    category: "compliance",
    question_en: "How is F&O income taxed in India?",
    question_hi: "F&O income India mein kaise tax hoti?",
    answer_en:
      "F&O profits are treated as **non-speculative business income** under Indian tax law, taxed at your applicable slab rate (NOT at flat capital-gains rates). Three implications: (1) **Slab rates apply** — high earners pay up to 30% plus surcharge plus cess. (2) **Tax-loss set-off** — F&O losses can be set off against other business income (a benefit equity STCG/LTCG losses don't get). (3) **Tax audit threshold** — if your F&O turnover exceeds ₹10 crore in a financial year, a tax audit is mandatory. Turnover for F&O is computed specially (absolute profits + absolute losses + premium received on shorts) — easily inflated to millions even on modest position sizes. Always consult a CA familiar with derivatives.",
    answer_hi:
      "F&O profits Indian tax law mein **non-speculative business income** treat hoti, applicable slab rate pe taxed (flat capital-gains rates pe NAHI). Teen implications: (1) **Slab rates apply** — high earners 30% tak plus surcharge plus cess pay karte. (2) **Tax-loss set-off** — F&O losses other business income ke against set off ho sakti (benefit jo equity STCG/LTCG losses ko nahi milti). (3) **Tax audit threshold** — financial year mein F&O turnover ₹10 crore exceed kare to tax audit mandatory. F&O ka turnover specially compute hota (absolute profits + absolute losses + shorts pe premium received) — modest position sizes pe bhi easily millions tak inflated. Derivatives-familiar CA se hamesha consult karo.",
    tags: ["tax", "f&o", "business-income", "audit", "compliance"],
  },
  {
    id: "advance-tax-for-traders",
    category: "compliance",
    question_en: "Do I need to pay advance tax as a trader?",
    question_hi: "Trader ke roop mein advance tax pay karna padta?",
    answer_en:
      "Yes — if your estimated total tax liability for the year exceeds ₹10,000, you're required to pay advance tax in four instalments: 15% by Jun 15, 45% by Sep 15, 75% by Dec 15, 100% by Mar 15. Missing these instalments triggers interest under Sections 234B + 234C.\n\nFor active traders, P&L can swing significantly between instalment due dates — projecting accurate tax 9 months out is hard. Two approaches: (1) Pay conservatively higher amounts early (over-paid amounts get refunded). (2) Re-estimate before each due date and pay the gap. Most active retail traders use a CA who builds projections; trying to navigate this alone usually results in penalty interest.",
    answer_hi:
      "Haan — saal ke liye estimated total tax liability ₹10,000 exceed kare to advance tax char instalments mein required: 15% by Jun 15, 45% by Sep 15, 75% by Dec 15, 100% by Mar 15. Yeh instalments miss karne pe Sections 234B + 234C ke under interest trigger hota.\n\nActive traders ke liye P&L instalment due dates ke beech significantly swing kar sakti — 9 months out accurate tax project karna mushkil. Do approaches: (1) Conservatively higher amounts early pay karo (over-paid amounts refund ho jaate). (2) Har due date se pehle re-estimate karke gap pay karo. Most active retail traders CA use karte projections banane ke liye; akele navigate karne se usually penalty interest hota.",
    tags: ["tax", "advance-tax", "compliance", "deadlines"],
  },
  {
    id: "fno-turnover-calculation",
    category: "compliance",
    question_en: "How is F&O turnover calculated for tax?",
    question_hi: "F&O turnover tax ke liye kaise calculate hota?",
    answer_en:
      "F&O turnover calculation differs from equity. Three components summed: (1) **Absolute profit** on each profitable trade. (2) **Absolute loss** on each losing trade (counted as positive). (3) **Premium received** on options shorted (for options sellers; not buyers).\n\nExample: trader makes 20 F&O trades — 12 profitable (total ₹50k profit), 8 losing (total ₹30k loss), sold options collected ₹40k premium. Turnover = 50k + 30k + 40k = ₹1.2L. Note that turnover is much LARGER than net P&L (which is just 50k - 30k = 20k).\n\nThe ₹10cr tax-audit threshold is on turnover, not P&L. Active F&O traders can easily breach turnover thresholds even with modest net profits. Tax auditing adds significant CA fees + ongoing record-keeping requirements.",
    answer_hi:
      "F&O turnover calculation equity se different. Teen components sum: (1) **Absolute profit** har profitable trade pe. (2) **Absolute loss** har losing trade pe (positive count). (3) **Premium received** options shorted pe (options sellers ke liye; buyers ke nahi).\n\nExample: trader 20 F&O trades karta — 12 profitable (total ₹50k profit), 8 losing (total ₹30k loss), sold options ₹40k premium collected. Turnover = 50k + 30k + 40k = ₹1.2L. Note karo turnover net P&L (jo sirf 50k - 30k = 20k) se much LARGER hai.\n\n₹10cr tax-audit threshold turnover pe hai, P&L pe nahi. Active F&O traders modest net profits ke saath bhi turnover thresholds easily breach kar sakte. Tax auditing significant CA fees + ongoing record-keeping requirements add karta.",
    tags: ["tax", "f&o", "turnover", "audit", "compliance"],
  },
  {
    id: "tax-loss-harvesting",
    category: "compliance",
    question_en: "What is tax-loss harvesting in trading?",
    question_hi: "Trading mein tax-loss harvesting kya hai?",
    answer_en:
      "Tax-loss harvesting = deliberately realising losing positions before March 31 (end of Indian financial year) to offset against gains, reducing tax payable. Two flavours: (1) **F&O losses** can offset against ALL business income (other F&O profits, salary, freelance income) — flexible. (2) **STCG / LTCG losses** can only offset capital gains of the same/longer holding period — STCG can offset both, LTCG only offsets LTCG.\n\nUnused losses can be **carried forward for 8 years** (must file ITR before due date to preserve). Don't sell purely for tax purposes without re-evaluating the position — many retail traders sell a 'loser' for tax, then watch it recover the next quarter. The tax benefit only makes sense if you'd sell the position regardless.",
    answer_hi:
      "Tax-loss harvesting = March 31 se pehle (Indian financial year end) deliberately losing positions realise karna gains ke against offset karke tax payable kam karna. Do flavours: (1) **F&O losses** ALL business income ke against offset ho sakti (other F&O profits, salary, freelance income) — flexible. (2) **STCG / LTCG losses** sirf same/longer holding period ki capital gains offset kar sakti — STCG dono offset karti, LTCG sirf LTCG.\n\nUnused losses **8 years tak carry forward** ho sakti (preserve karne ke liye ITR due date se pehle file karna padta). Position re-evaluate kiye bina purely tax purposes ke liye sell mat karo — many retail traders 'loser' tax ke liye sell karte, phir next quarter recover hota dekhte. Tax benefit tabhi sense karta jab position regardless sell karoge.",
    tags: ["tax", "loss-harvesting", "compliance", "fiscal-year"],
  },
] as const;

/** Sanity export — keeps the test file from re-deriving these counts. */
export const FAQ_COUNT = FAQS.length;
export const CATEGORY_COUNT = CATEGORIES.length;
