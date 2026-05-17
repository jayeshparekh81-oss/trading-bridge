/**
 * /compliance — site-wide disclaimer copy in en + hi.
 *
 * Voice rules: Hinglish (conversational), not formal Devanagari —
 * matches the /help FAQ corpus and the onboarding tour. Test enforces
 * the rule mechanically.
 *
 * Adding a new section:
 *   1. Pick a stable `id` (slug-style, never reused — appears as a
 *      DOM anchor for footer / signup deep-links)
 *   2. Write BOTH `title_en` and `title_hi`
 *   3. Write BOTH `body_en` and `body_hi` (markdown allowed via the
 *      same minimal tokeniser as the /help FAQ items)
 */

export type Lang = "en" | "hi";

export interface DisclaimerSection {
  id: string;
  title_en: string;
  title_hi: string;
  body_en: string;
  body_hi: string;
}

// ─── Footer (compact, every page) ───────────────────────────────────

export const FOOTER_COPY = {
  en: "TRADETRI is an algorithmic trading platform. Trading involves substantial risk of capital loss. Past performance does not guarantee future results. Not investment advice. SEBI Algo Trading Framework compliance pending.",
  hi: "TRADETRI ek algorithmic trading platform hai. Trading mein capital loss ka substantial risk hai. Past performance future results ki guarantee nahi deta. Yeh investment advice nahi hai. SEBI Algo Trading Framework compliance pending hai.",
  cta_en: "Read full disclaimer",
  cta_hi: "Pura disclaimer padho",
} as const;

// ─── Signup checkbox ────────────────────────────────────────────────

export const RISK_ACK_COPY = {
  en: "I understand that algorithmic trading involves substantial risk of capital loss and I agree to TRADETRI's Terms of Service and Risk Disclosure.",
  hi: "Maine samjha hai ki algorithmic trading mein capital loss ka substantial risk hai aur main TRADETRI ki Terms of Service aur Risk Disclosure se sehmat hu.",
  error_en: "You must acknowledge the risk disclosure to create an account.",
  error_hi: "Account banane ke liye risk disclosure acknowledge karna zaroori hai.",
} as const;

// ─── Pre-trade risk modal ───────────────────────────────────────────

export const PRE_TRADE_COPY = {
  title_en: "Important Risk Acknowledgment",
  title_hi: "Important Risk Acknowledgment",
  intro_en:
    "You are about to place a live order with real money. This is irreversible. By proceeding you confirm:",
  intro_hi:
    "Aap real money se live order place karne wale ho. Yeh irreversible hai. Aage badhne se aap confirm karte ho:",
  bullets_en: [
    "You understand trading involves risk of complete capital loss",
    "You have read TRADETRI's risk disclosure",
    "You take full responsibility for trading decisions",
    "You are not relying on TRADETRI for investment advice",
    "You have sufficient capital you can afford to lose",
  ],
  bullets_hi: [
    "Aap samjhte ho ki trading mein complete capital loss ka risk hai",
    "Aapne TRADETRI ka risk disclosure padh liya hai",
    "Trading decisions ki poori responsibility aapki hai",
    "Aap investment advice ke liye TRADETRI pe rely nahi karte",
    "Aapke paas itna capital hai jo aap afford to lose kar sakte ho",
  ],
  cta_en: "I Understand and Proceed",
  cta_hi: "Main samjhta hu aur aage badhta hu",
  cancel_en: "Cancel",
  cancel_hi: "Cancel",
} as const;

// ─── /compliance/legal — long-form page sections ────────────────────

export const DISCLAIMER_SECTIONS: readonly DisclaimerSection[] = [
  {
    id: "risk-disclosure",
    title_en: "Risk Disclosure",
    title_hi: "Risk Disclosure",
    body_en:
      "Algorithmic trading involves substantial financial risk. You may lose some or all of the capital you commit to trading. Market volatility, broker connectivity issues, software bugs, or operational errors can amplify losses beyond what historical backtesting suggested. TRADETRI does not guarantee profitability, accuracy of signals, or uninterrupted service.\n\nPaper trading uses real-time market data with virtual money — useful for practice but **not predictive** of live results. A strategy that performs well in paper mode can still lose money in live trading because real orders incur slippage, partial fills, and broker-side rejections that the simulator does not model perfectly. Treat backtest and paper-mode numbers as one input among many — not as forecasts.\n\nYou are solely responsible for understanding the risks before placing any order. If you do not understand what an indicator does, why a strategy fires, or how a stop-loss interacts with a kill-switch, **do not enable live trading**. Use AlgoMitra chat, the FAQ at `/help`, or open a support ticket first.",
    body_hi:
      "Algorithmic trading mein substantial financial risk hai. Aap apna trading capital partially ya completely lose kar sakte ho. Market volatility, broker connectivity issues, software bugs, ya operational errors losses ko backtesting se zyada amplify kar sakte hain. TRADETRI profitability, signals ki accuracy, ya uninterrupted service ki guarantee nahi deta.\n\nPaper trading real-time market data + virtual money use karta hai — practice ke liye useful but live results ka **predictor nahi hai**. Paper mode mein achhi-perform karne wali strategy live trading mein bhi loss kar sakti hai kyunki real orders mein slippage, partial fills, aur broker-side rejections aate hain — yeh sab simulator perfectly model nahi karta. Backtest aur paper-mode numbers ko ek input maano, forecast nahi.\n\nKisi bhi order place karne se pehle risks samajhna aapki zimmedari hai. Agar aapko indicator ka kaam, strategy kyu fire hoti hai, ya stop-loss kill-switch ke saath kaise interact karta hai samajh nahi aata — **live trading enable mat karo**. Pehle AlgoMitra chat, `/help` ki FAQ, ya support ticket use karo.",
  },
  {
    id: "terms",
    title_en: "Terms of Service Summary",
    title_hi: "Terms of Service Summary",
    body_en:
      "By using TRADETRI you agree that: (1) you are at least 18 years of age and legally permitted to trade securities in India; (2) the broker credentials you connect are your own and you are authorized to use them; (3) you will not attempt to reverse-engineer, exploit, or abuse the platform; (4) TRADETRI is not a registered broker, investment advisor, or portfolio manager — we are an execution platform connecting your strategies to your broker.\n\nWe reserve the right to suspend or terminate accounts that violate these terms, attempt unauthorized access, or expose other users to harm. Account suspension is rare and we will always email you first unless the violation is active (e.g., credential stuffing, API abuse).\n\nThe full Terms of Service text will publish 30 days before live trading launches in July 2026. Until then this summary plus the FAQ at `/help` is the binding statement.",
    body_hi:
      "TRADETRI use karke aap maante ho ki: (1) aapki age 18+ hai aur India mein securities trade karne ki legal permission hai; (2) connected broker credentials aapke khud ke hain aur unhe use karne ka authorization hai; (3) aap platform ko reverse-engineer, exploit, ya abuse nahi karoge; (4) TRADETRI registered broker, investment advisor, ya portfolio manager nahi hai — hum ek execution platform hain jo aapki strategies ko aapke broker se connect karta hai.\n\nHum un accounts ko suspend / terminate kar sakte hain jo terms violate karte hain, unauthorized access try karte hain, ya doosre users ko harm karte hain. Suspension rare hai aur hum hamesha pehle email karenge unless violation active hai (jaise credential stuffing, API abuse).\n\nPuri Terms of Service July 2026 live trading launch se 30 din pehle publish hogi. Tab tak yeh summary aur `/help` ki FAQ hi binding statement hai.",
  },
  {
    id: "sebi-framework",
    title_en: "SEBI Algo Trading Framework",
    title_hi: "SEBI Algo Trading Framework",
    body_en:
      "TRADETRI is a self-trade execution platform — you connect your own broker account and trade with your own funds. We do not act as a broker, investment advisor, research analyst, or portfolio manager, so SEBI registration in those categories does not apply.\n\nIndia's algorithmic-trading-for-retail framework is evolving. SEBI's December 2024 circular on retail algo trading places the burden of vetting + approval primarily on the broker (Dhan, Fyers), who must register your algos with the exchange. TRADETRI cooperates with that process: every strategy you connect to a broker has a stable `broker_algo_id` for exchange registration, and we expose an audit log of every order placed.\n\nCompliance with future SEBI requirements (additional disclosures, kill-switch standards, risk caps) is **pending**. We track the regulator's guidance closely and will update this page whenever the framework expands. If you are uncertain whether your strategy meets your broker's algo-approval requirements, contact your broker before going live.",
    body_hi:
      "TRADETRI ek self-trade execution platform hai — aap apna khud ka broker account connect karke apne funds se trade karte ho. Hum broker, investment advisor, research analyst, ya portfolio manager nahi hain, isliye in categories mein SEBI registration apply nahi hota.\n\nIndia ka retail algo-trading framework evolving hai. SEBI ke December 2024 circular ne retail algo trading ka vetting + approval burden mainly broker (Dhan, Fyers) pe daala hai — broker aapke algos ko exchange se register karta hai. TRADETRI is process mein cooperate karta hai: har broker-connected strategy ka ek stable `broker_algo_id` hota hai exchange registration ke liye, aur har placed order ka audit log expose hota hai.\n\nFuture SEBI requirements (additional disclosures, kill-switch standards, risk caps) ke saath compliance abhi **pending** hai. Regulator ki guidance closely track karte hain aur framework expand hone pe page update hoga. Agar aap unsure ho ki aapki strategy broker ke algo-approval requirements meet karti hai ya nahi, live jaane se pehle broker se contact karo.",
  },
  {
    id: "data-privacy",
    title_en: "Data Privacy",
    title_hi: "Data Privacy",
    body_en:
      "Broker credentials are encrypted at rest using Fernet (symmetric key rotated quarterly). Passwords are hashed with bcrypt (cost factor 12, salted per-user). All network traffic is HTTPS / WSS only. Database backups are encrypted at rest. We do not sell, rent, or share personal data with third parties for marketing.\n\nWe collect what we need to operate the service — email, broker credentials, your strategies, your trades, audit logs of API access. We do not collect biometric data, social-graph data, or trading positions from accounts you have not connected. Telemetry (page loads, error reports) is anonymised and aggregated.\n\nIndia's Digital Personal Data Protection Act (DPDP) 2023 governs how we handle Indian users' data. You have the right to access, correct, and delete your data — Settings → Privacy → 'Export data' / 'Delete account'. Deletion is hard within 30 days of request except for legally-required audit trails. Cross-border data transfer is currently disabled; everything stays in AWS Mumbai (`ap-south-1`).",
    body_hi:
      "Broker credentials Fernet (symmetric key, quarterly rotated) se encrypted at rest store hote hain. Passwords bcrypt (cost factor 12, per-user salted) se hash hote hain. Saara network traffic HTTPS / WSS only hai. Database backups at rest encrypted hain. Hum personal data third parties ko marketing ke liye sell, rent, ya share nahi karte.\n\nHum sirf wahi data collect karte hain jo service operate karne ke liye chahiye — email, broker credentials, aapki strategies, trades, API access ke audit logs. Hum biometric data, social-graph data, ya unconnected accounts ke trading positions collect nahi karte. Telemetry (page loads, error reports) anonymised + aggregated hota hai.\n\nIndia ka Digital Personal Data Protection Act (DPDP) 2023 Indian users ka data handling govern karta hai. Aapko access, correct, aur delete ka right hai — Settings → Privacy → 'Export data' / 'Delete account'. Deletion request ke 30 din ke andar hard ho jaati hai except legally-required audit trails. Cross-border data transfer abhi disabled hai; sab AWS Mumbai (`ap-south-1`) mein hi rehta hai.",
  },
  {
    id: "glass-box-ai",
    title_en: "Glass Box AI Commitment",
    title_hi: "Glass Box AI Commitment",
    body_en:
      "Every AI decision on TRADETRI is **explainable**. When the AI validates a signal, recommends a strategy fix, or rejects an order, it returns a structured `reasoning` field stored in the audit log and surfaced in the UI alongside the verdict. You can always trace *why* the AI chose what it chose — which indicator, which threshold, which historical pattern, which risk-policy clause.\n\nWe deliberately do not use black-box deep-learning models for any safety-critical decision. Strategy validation runs through deterministic rules first; the LLM layer only adds nuance to the explanation, never overrides a deterministic verdict. The kill-switch, broker-execution-guard, and SafetyChain are pure deterministic Python — no AI in the hot path.\n\nIf you ever see an AI decision without a `reasoning` field, that's a bug — please file a support ticket with the signal ID. We treat opaque AI verdicts as P0 incidents.",
    body_hi:
      "TRADETRI pe har AI decision **explainable** hai. Jab AI signal validate kare, strategy fix recommend kare, ya order reject kare — wo ek structured `reasoning` field return karta hai jo audit log mein store hota hai aur UI mein verdict ke saath dikhta hai. Aap hamesha trace kar sakte ho *kyun* AI ne yeh choose kiya — kaunsa indicator, kaunsa threshold, kaunsa historical pattern, kaunsa risk-policy clause.\n\nHum deliberately black-box deep-learning models kisi bhi safety-critical decision ke liye use nahi karte. Strategy validation pehle deterministic rules se chalti hai; LLM layer sirf explanation mein nuance add karta hai, deterministic verdict ko override kabhi nahi karta. Kill-switch, broker-execution-guard, aur SafetyChain pure deterministic Python hain — hot path mein koi AI nahi.\n\nAgar kabhi AI decision `reasoning` field ke bina dikhe, woh bug hai — signal ID ke saath support ticket file karo. Opaque AI verdicts hamare liye P0 incidents hain.",
  },
  {
    id: "transparency-ledger",
    title_en: "Strategy Transparency Ledger",
    title_hi: "Strategy Transparency Ledger",
    body_en:
      "Published marketplace strategies carry a cryptographic audit chain of daily performance snapshots. Each snapshot's hash links to the previous one (SHA-256), forming an append-only ledger of returns + drawdown + trade-count. A `verify` endpoint walks the chain; tampering with any field breaks the chain and `verify` fails.\n\nThis is our concrete answer to 'how do I trust a marketplace strategy?' — instead of taking the creator's word, you can independently confirm that the published track record hasn't been retroactively edited to look better than it was.\n\nPhase 1 keeps the ledger off-chain (Postgres). Phase 4 commits the daily hash to a public blockchain (Polygon) for third-party verifiability. The frontend ledger UI is already shipping; the on-chain anchor is on the live-trading roadmap.",
    body_hi:
      "Published marketplace strategies ke saath ek cryptographic audit chain hota hai jo daily performance snapshots ka link banata hai. Har snapshot ka hash previous wale se link hota hai (SHA-256), aur ek append-only ledger banta hai — returns + drawdown + trade-count ka. Ek `verify` endpoint puri chain walk karta hai; koi bhi field tamper karne pe chain break ho jaati hai aur `verify` fail hota hai.\n\nYeh hamara concrete answer hai 'marketplace strategy pe trust kaise karu?' wale sawal ka — creator ki baat maanne ke bajaye, aap independently confirm kar sakte ho ki published track record retroactively better dikhne ke liye edit nahi hua.\n\nPhase 1 mein ledger off-chain hai (Postgres). Phase 4 mein daily hash public blockchain (Polygon) pe commit hoga third-party verifiability ke liye. Frontend ledger UI already ship ho chuki hai; on-chain anchor live-trading roadmap pe hai.",
  },
] as const;

/** Sanity exports — tests assert against these counts directly. */
export const SECTION_COUNT = DISCLAIMER_SECTIONS.length;

// ─── localStorage keys ──────────────────────────────────────────────

/** Timestamp (ISO) at which the user clicked the signup risk-ack
 *  checkbox. `v1` so future schema changes can ship without colliding. */
export const LS_KEY_RISK_ACK = "tradetri_risk_ack_v1";

/** Timestamp (ISO) at which the user confirmed the pre-trade modal.
 *  Once set, the modal does not re-appear on subsequent live orders. */
export const LS_KEY_PRE_TRADE_ACK = "tradetri_pre_trade_ack_v1";
