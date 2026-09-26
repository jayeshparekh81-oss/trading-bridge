/**
 * THE ONE LIST of customer-facing screens and the files that draw them
 * (founder's standing rule, 26 Sep 2026 — RULES #50: "it must be easy for a
 * customer who knows nothing"). The customer-screen rules test walks exactly
 * these files; `kb/customer/LIVE_WALK_PROOF.md` walks exactly these screens.
 * Add a screen here the day a customer can reach it.
 *
 * NOT in this list, on purpose (and why):
 *  - admin/*            — admin only.
 *  - dev-preview/*      — 404 on the live site (measured 26 Sep).
 *  - Pro tools (chart, indicators, strategy builders, backtest, analytics,
 *    alerts, signals, compliance): a Pro-mode customer's workbench, where the
 *    trading words ARE the tool. Walked separately; not linted here.
 *  - Knowledge-base text (help FAQ answers, indicator lessons, tutorials):
 *    that is where a jargon word is TAUGHT. The FAQ/AlgoMitra screens
 *    themselves are in the list; their article bodies are not.
 */

export const CUSTOMER_SCREENS: Record<string, string[]> = {
  "S01 Login": ["src/app/(auth)/login/page.tsx", "src/components/brand/conviction-panel.tsx"],
  "S02 Register": ["src/app/(auth)/register/page.tsx", "src/components/compliance/RiskAcknowledgment.tsx"],
  "S03 Home (public)": ["src/app/(public)/home/page.tsx", "src/components/marketing/HomePricing.tsx", "src/app/(public)/layout.tsx"],
  "S04 Pricing": ["src/app/(public)/pricing/page.tsx", "src/components/billing/plan-checkout-button.tsx"],
  "S05 Proof / Track Record": ["src/app/(public)/showcase/page.tsx", "src/components/strategy/strategy-card.tsx"],
  "S06 About": ["src/app/(public)/about/page.tsx"],
  "S07 Contact": ["src/app/(public)/contact/page.tsx"],
  "S08 Not found (404)": ["src/app/not-found.tsx"],
  "S09 Something broke (global error)": ["src/app/global-error.tsx"],
  "S10 First-run onboarding (Simple)": ["src/components/simple/simple-onboarding.tsx", "src/lib/simple/copy.ts"],
  "S11 Ghar (Simple home)": ["src/components/simple/simple-home.tsx", "src/components/simple/simple-home-view.tsx", "src/components/simple/simple-shell.tsx", "src/components/simple/safety-bar.tsx"],
  "S12 Dashboard (Pro overview)": ["src/app/(dashboard)/page.tsx", "src/components/dashboard/mobile-nav.tsx"],
  "S13 Strategy chuno (marketplace)": ["src/app/(dashboard)/marketplace/page.tsx", "src/components/simple/strategy-pick.tsx"],
  "S14 Strategy detail + subscribe": ["src/app/(dashboard)/marketplace/[id]/page.tsx", "src/components/strategy/strategy-detail.tsx", "src/components/marketplace/subscribe-button.tsx"],
  "S15 Meri strategies + settings + picker": [
    "src/app/(dashboard)/marketplace/me/page.tsx",
    "src/components/marketplace/subscription-settings.tsx",
    "src/components/marketplace/vehicle-picker.tsx",
    "src/components/marketplace/account-truth-card.tsx",
    "src/components/marketplace/execution-log.tsx",
    "src/components/marketplace/position-detail.tsx",
    "src/components/marketplace/close-position-button.tsx",
    "src/components/marketplace/pause-deployment-button.tsx",
    "src/components/marketplace/drift-notice-banner.tsx",
    "src/components/risk/risk-chip.tsx",
    "src/lib/risk-labels.ts",
    "src/lib/customer-vehicles.ts",
    "src/lib/execution-label.ts",
  ],
  "S16 Broker jodo": ["src/app/(dashboard)/brokers/page.tsx", "src/components/brokers/UpdateDhanTokenModal.tsx", "src/components/brokers/ReconnectInfoBanner.tsx"],
  "S17 Positions": ["src/app/(dashboard)/positions/page.tsx", "src/components/dashboard/paper-mode-banner.tsx", "src/components/dashboard/tracking-epoch-note.tsx"],
  "S18 Orders / trades": ["src/app/(dashboard)/trades/page.tsx", "src/components/billing/upgrade-wall.tsx"],
  "S19 Sab band (kill switch)": ["src/app/(dashboard)/kill-switch/page.tsx", "src/lib/kill-switch-label.ts", "src/components/strategies/kill-switch-summary.tsx"],
  "S20 Meri banayi strategies": ["src/app/(dashboard)/strategies/page.tsx"],
  "S21 TradingView doorbell (webhooks)": ["src/app/(dashboard)/webhooks/page.tsx"],
  "S22 Madad (help + tickets)": ["src/app/(dashboard)/help/page.tsx", "src/components/support/ticket-form.tsx", "src/components/support/my-tickets-list.tsx"],
  "S23 Settings": ["src/app/(dashboard)/settings/page.tsx", "src/components/simple/mode-card.tsx"],
  "S24 AlgoMitra chat": ["src/lib/algomitra-flows.ts", "src/lib/algomitra-personality.ts", "src/components/algomitra/QuickActions.tsx", "src/components/algomitra/ChatHeader.tsx", "src/components/algomitra/InputArea.tsx"],
  "S25 /start — first-timer guided path": [
    "src/app/start/page.tsx",
    "src/components/guided/guided-path.tsx",
    "src/components/guided/guided-screens.tsx",
    "src/components/guided/guided-parts.tsx",
    "src/components/guided/guided-running.tsx",
    "src/lib/guided-path.ts",
  ],
  "S26 /journey — kahan tak pahunche": ["src/app/(dashboard)/journey/page.tsx", "src/components/journey/journey-stepper.tsx", "src/lib/customer-journey.ts", "src/lib/account-truth.ts"],
};

/** Screens that are the NEW first-timer path: held to the stricter 14px text floor. */
export const FIRST_TIMER_SCREENS = [
  "S10 First-run onboarding (Simple)",
  "S25 /start — first-timer guided path",
  "S26 /journey — kahan tak pahunche",
];

/**
 * Words a customer who knows nothing does not understand (his list, 26 Sep, plus
 * the engineer words found on the walk). A word is allowed ONLY when it is
 * explained right beside it: "Dhan ki chabi (access token)" or
 * "token (Dhan ki chabi)" — the TALKING_TO_FOUNDER bracket rule — or when it is
 * quoted as the literal label of a button on ANOTHER site ('Access DhanHQ Trading APIs').
 */
export const JARGON: { word: string; re: RegExp }[] = [
  { word: "NRML", re: /\bNRML\b/ },
  { word: "MIS", re: /\bMIS\b/ },
  { word: "lot / lots", re: /\blots?\b/i },
  { word: "webhook", re: /\bweb-?hooks?\b/i },
  { word: "API", re: /\bAPIs?\b/ },
  { word: "margin", re: /\bmargin\b/i },
  { word: "security id", re: /\bsecurity[ _-]?ids?\b/i },
  { word: "slippage", re: /\bslippage\b/i },
  { word: "drawdown", re: /\bdraw-?downs?\b/i },
  { word: "execution mode", re: /\bexecution mode\b/i },
  { word: "HMAC", re: /\bHMAC\b/ },
  { word: "OAuth", re: /\bOAuth\b/i },
  { word: "endpoint", re: /\bend-?points?\b/i },
  { word: "backend", re: /\bback-?end\b/i },
  { word: "payload", re: /\bpayloads?\b/i },
  { word: "JSON", re: /\bJSON\b/ },
  { word: "LTP", re: /\bLTP\b/ },
  { word: "ATM/OTM/ITM", re: /\b(ATM|OTM|ITM)\b/ },
  { word: "CE/PE", re: /\b(CE|PE)\b/ },
  { word: "F&O", re: /\bF&O\b/ },
  { word: "forever order", re: /\bforever orders?\b/i },
  { word: "GTT", re: /\bGTT\b/ },
  { word: "square-off", re: /\bsquare[- ]?(?:off|ed off)\b/i },
  { word: "internal error", re: /\binternal error\b/i },
  { word: "status code", re: /\bstatus code\b|\bHTTP \d{3}\b/i },
  { word: "token", re: /\btokens?\b/i },
  { word: "backtest", re: /\bback-?test(?:s|ed|ing)?\b/i },
  { word: "in-sample", re: /\bin-sample\b/i },
  { word: "walk-forward", re: /\bwalk-forward\b/i },
  { word: "non-compounded", re: /\bnon-compounded\b/i },
  { word: "leg", re: /\blegs?\b/i },
  { word: "conviction score", re: /\bconviction\b/i },
];

/**
 * A few screens are ABOUT one of these words — the word is the name of the thing
 * the customer came for. Each allowance names its reason. Everything else on those
 * screens is still checked.
 */
export const ALLOW: { file: string; word: string; why: string }[] = [
  { file: "src/app/(dashboard)/webhooks/page.tsx", word: "webhook", why: "the page IS the TradingView doorbell (webhook) — its title explains the word once" },
  { file: "src/lib/algomitra-flows.ts", word: "webhook", why: "the algo-trader branch of the chat answers questions ABOUT webhooks the customer typed" },
];
