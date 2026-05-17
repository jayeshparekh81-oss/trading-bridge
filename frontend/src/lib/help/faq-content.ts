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
] as const;

/** Sanity export — keeps the test file from re-deriving these counts. */
export const FAQ_COUNT = FAQS.length;
export const CATEGORY_COUNT = CATEGORIES.length;
