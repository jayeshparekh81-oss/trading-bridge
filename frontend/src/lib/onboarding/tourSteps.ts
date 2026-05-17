/**
 * Onboarding tour content — 5 steps, en + hi pairs.
 *
 * Targets are CSS selectors. The owning components add the matching
 * `data-tour-id` attribute. Keep selectors stable; renaming an ID
 * breaks the tour silently.
 */

export type Lang = "en" | "hi";

export interface TourCopy {
  en: string;
  hi: string;
}

export interface TourStepDef {
  id: string;
  target: string;
  title: TourCopy;
  body: TourCopy;
  placement: "right" | "bottom" | "left" | "top" | "auto";
}

export const TOUR_STEPS: readonly TourStepDef[] = [
  {
    id: "brokers",
    target: '[data-tour-id="brokers-nav"]',
    title: {
      en: "Step 1: Connect a broker",
      hi: "Step 1: Broker connect karo",
    },
    body: {
      en: "Connect your Dhan or Fyers account — paste the daily token, the rest is automatic.",
      hi: "Dhan ya Fyers account connect kar — daily token paste karo, baki sab automatic.",
    },
    placement: "right",
  },
  {
    id: "chart",
    target: '[data-tour-id="chart-nav"]',
    title: {
      en: "Step 2: Watch the market",
      hi: "Step 2: Market dekho",
    },
    body: {
      en: "Live NIFTY, BANKNIFTY charts + 230 indicators. TradingView-grade experience.",
      hi: "Live NIFTY, BANKNIFTY charts + 230 indicators. TradingView jaisa experience.",
    },
    placement: "right",
  },
  {
    id: "strategies",
    target: '[data-tour-id="strategies-nav"]',
    title: {
      en: "Step 3: Build a strategy",
      hi: "Step 3: Strategy banao",
    },
    body: {
      en: "Use the no-code builder to create your own strategy — drag, drop, no programming needed.",
      hi: "No-code builder se own strategy create kar — drag drop, no programming needed.",
    },
    placement: "right",
  },
  {
    id: "paper-mode",
    target: '[data-tour-id="paper-mode-banner"]',
    title: {
      en: "Step 4: Paper trading",
      hi: "Step 4: Paper trading",
    },
    body: {
      en: "Practice in paper mode first — virtual money, real market data. Risk-free.",
      hi: "Pehle paper mode mein practice karo — virtual money, real market data. Risk-free.",
    },
    placement: "bottom",
  },
  {
    id: "algomitra",
    // AlgoMitra's ChatWidget lives outside the dashboard/ folder
    // (out of the onboarding sprint's edit scope), so target it via
    // the existing stable aria-label rather than a new data-tour-id.
    target: '[aria-label="Open AlgoMitra chat"]',
    title: {
      en: "Step 5: AI Mentor",
      hi: "Step 5: AI Mentor",
    },
    body: {
      en: "Ask AlgoMitra anything — strategy ideas, indicator help, trading psychology. Available 24×7.",
      hi: "AlgoMitra se kuch bhi pooch — strategy ideas, indicator help, trading psychology. 24x7 available.",
    },
    placement: "left",
  },
] as const;

export const WELCOME_COPY = {
  greeting: {
    en: (name: string) => `Welcome to TRADETRI, ${name}! 🙏`,
    hi: (name: string) => `Namaste ${name}! TRADETRI mein swagat hai 🙏`,
  },
  tagline: {
    en: "India's first AI-powered algo trading platform. Build strategies, backtest, paper trade to practice.",
    hi: "India ka first AI-powered algo trading platform. Strategies banao, backtest karo, paper trade kar ke practice karo.",
  },
  trustBadge: {
    en: "L&T Engineer Built",
    hi: "L&T Engineer Built",
  },
  startCta: {
    en: "Start tour",
    hi: "Tour shuru karo",
  },
  laterCta: {
    en: "Later",
    hi: "Baad mein",
  },
} as const;

export const SUCCESS_COPY = {
  title: {
    en: "Tour complete! 🚀",
    hi: "Tour complete! 🚀",
  },
  body: {
    en: "You're ready to start trading.",
    hi: "Ab tu ready hai trading shuru karne ke liye.",
  },
  buildCta: {
    en: "Build a strategy",
    hi: "Strategy banao",
  },
  chartCta: {
    en: "View chart",
    hi: "Chart dekho",
  },
} as const;

export const STEP_NAV_COPY = {
  next: { en: "Next", hi: "Aage" },
  skip: { en: "Skip", hi: "Skip" },
  finish: { en: "Finish", hi: "Khatam" },
  stepOf: {
    en: (n: number, total: number) => `Step ${n} of ${total}`,
    hi: (n: number, total: number) => `Step ${n}/${total}`,
  },
} as const;
