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
      en: "Connect your Dhan account by pasting its daily access token. Without it, charts and paper trading stay empty.",
      hi: "Dhan account connect karo — daily access token paste karo. Bina iske chart aur paper trading khaali rahenge.",
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
      en: "Live NIFTY and BANKNIFTY charts with the built-in indicators, once your broker is connected.",
      hi: "Broker connect hone ke baad live NIFTY aur BANKNIFTY charts, built-in indicators ke saath.",
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
      en: "Pick a proven strategy from the Marketplace, or build your own with the 5-step Beginner Builder. No code needed.",
      hi: "Marketplace se proven strategy lo, ya 5-step Beginner Builder se apni banao. Code ki zaroorat nahi.",
    },
    placement: "right",
  },
  {
    id: "paper-mode",
    target: '[data-tour-id="strategies-nav"]',
    title: {
      en: "Step 4: Paper trading",
      hi: "Step 4: Paper trading",
    },
    body: {
      en: "Everything runs in paper mode first — simulated orders, no real money. Live orders are not enabled for subscribers yet.",
      hi: "Sab kuch pehle paper mode mein chalta hai — simulated orders, real paisa nahi. Subscribers ke liye live orders abhi enable nahi hain.",
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
      en: "AlgoMitra answers common questions about strategies, indicators and the platform — instantly, from a built-in FAQ.",
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
    en: "Build a strategy, backtest it, and practice in paper mode — then decide. Nothing here is investment advice.",
    hi: "Strategies banao, backtest karo, paper trade kar ke practice karo.",
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
