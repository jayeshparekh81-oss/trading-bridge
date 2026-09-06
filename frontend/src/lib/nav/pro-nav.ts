/**
 * THE Pro navigation. One source, consumed by the desktop sidebar, the mobile
 * drawer and every page header.
 *
 * WHY THIS FILE EXISTS. The sidebar and the drawer each carried their own copy of
 * the list, and they had drifted: the drawer was missing Strategy Templates,
 * Indicator Library and Indicator Requests, and the same page was called
 * "Sab band" in one and "Kill Switch" in the other. One list makes "desktop and
 * mobile identical" structural instead of a promise, and makes one-name-per-thing
 * enforceable by a test.
 *
 * The page TITLE is this `label`. The page's one plain line is this `blurb`. The
 * single primary action is this `action`. A page does not get to invent its own
 * header, so the sidebar and the page can never disagree.
 *
 * Groups are the story the founder asked for: six plain words, in this order.
 */

import {
  BarChart3,
  Bot,
  BookOpen,
  CandlestickChart,
  HelpCircle,
  Landmark,
  Layers,
  LineChart,
  ListOrdered,
  RadioTower,
  Settings,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Store,
  TrendingUp,
  Trophy,
  Webhook,
  Crown,
  Bell,
} from "lucide-react";

export type NavIcon = typeof BarChart3;

export interface ProNavItem {
  /** Sidebar label AND page title. They are the same string by construction. */
  label: string;
  href: string;
  icon: NavIcon;
  /** The one plain line under the title: "yeh page kya karta hai". */
  blurb: string;
  /** The single primary action, top-right. Omit where a page has none. */
  action?: { label: string; href: string };
  /** Sub-entries live INSIDE their parent, never as top-level nav. */
  children?: { label: string; href: string }[];
  adminOnly?: boolean;
  creatorOnly?: boolean;
  /**
   * This entry leaves the Pro chrome (it is a PUBLIC page with its own
   * marketing header and no sidebar). It opens in a new tab so the customer
   * never loses their way back — the Pro tab is still sitting there. The
   * page-title rule cannot apply to a page Pro does not own.
   */
  external?: boolean;
}

export interface ProNavGroup {
  /** A plain word, rendered as a plain word — not a caps-tracked label. */
  title: string;
  items: ProNavItem[];
}

export const PRO_NAV: ProNavGroup[] = [
  {
    title: "Ghar",
    items: [
      {
        label: "Overview",
        href: "/",
        icon: BarChart3,
        blurb: "Aaj kya ho raha hai — ek jagah par.",
      },
    ],
  },
  {
    title: "Trade karo",
    items: [
      {
        label: "Marketplace",
        href: "/marketplace",
        icon: Store,
        blurb: "Doosron ki strategies dekho aur subscribe karo.",
      },
      {
        label: "My Strategies",
        href: "/marketplace/me",
        icon: Layers,
        blurb: "Jin strategies ko aapne subscribe kiya hai.",
      },
      {
        label: "Signals",
        href: "/signals",
        icon: RadioTower,
        blurb: "Har signal jo aayi — aur uska kya hua.",
      },
      {
        label: "Positions",
        href: "/positions",
        icon: LineChart,
        blurb: "Abhi jo trades khuli hain, unka live P&L.",
      },
      {
        label: "Trades",
        href: "/trades",
        icon: ListOrdered,
        blurb: "Poori trade history, band ho chuki trades ke saath.",
      },
      {
        label: "Chart",
        href: "/chart",
        icon: CandlestickChart,
        blurb: "Bazaar ka chart, aapke trade markers ke saath.",
      },
    ],
  },
  {
    title: "Banao",
    items: [
      {
        label: "Strategies",
        href: "/strategies",
        icon: Bot,
        blurb: "Apni strategy banao, test karo, chalao.",
        action: { label: "Nayi strategy", href: "/strategies/new" },
        children: [
          { label: "Templates", href: "/strategies/templates" },
          { label: "Pine import", href: "/strategies/import-pine" },
        ],
      },
    ],
  },
  {
    title: "Seekho",
    items: [
      {
        label: "Learn Indicators",
        href: "/indicators",
        icon: BookOpen,
        blurb: "Har indicator: kya karta hai, kab kaam aata hai.",
      },
      {
        label: "Track Record",
        href: "/showcase",
        external: true,
        icon: Trophy,
        blurb: "Humari apni strategies ka public record.",
      },
      {
        label: "Indicator Requests",
        href: "/indicators/requests",
        icon: Sparkles,
        blurb: "Naya indicator maango ya request ka status dekho.",
        creatorOnly: true,
      },
    ],
  },
  {
    title: "Control",
    items: [
      {
        label: "Kill Switch",
        href: "/kill-switch",
        icon: ShieldAlert,
        blurb: "Sab kuch turant band karo.",
      },
      {
        label: "Brokers",
        href: "/brokers",
        icon: Landmark,
        blurb: "Broker account jodo aur session zinda rakho.",
        action: { label: "Broker jodo", href: "/brokers?add=1" },
      },
      {
        label: "Webhooks",
        href: "/webhooks",
        icon: Webhook,
        blurb: "TradingView se signal bhejne ka URL.",
      },
      {
        label: "Analytics",
        href: "/analytics",
        icon: TrendingUp,
        blurb: "Aapki trading ka hisaab — jeet, haar, drawdown.",
      },
      {
        label: "Settings",
        href: "/settings",
        icon: Settings,
        blurb: "Account, notifications, aur mode.",
      },
      {
        label: "Compliance",
        href: "/compliance",
        icon: ShieldCheck,
        blurb: "SEBI disclosures aur legal documents.",
      },
    ],
  },
  {
    title: "Madad",
    items: [
      {
        label: "Help & Support",
        href: "/help",
        icon: HelpCircle,
        blurb: "Jawab dhoondo, ya humein ticket bhejo.",
      },
    ],
  },
];

export const ADMIN_NAV: ProNavItem[] = [
  { label: "System Health", href: "/admin", icon: Crown, blurb: "Platform ki sehat.", adminOnly: true },
  { label: "Users", href: "/admin/users", icon: Crown, blurb: "Sab users.", adminOnly: true },
  { label: "Audit Logs", href: "/admin/audit", icon: Crown, blurb: "Kisne kya kiya.", adminOnly: true },
  { label: "Kill-switch Events", href: "/admin/kill-switch-events", icon: ShieldAlert, blurb: "Kab kab sab band hua.", adminOnly: true },
  { label: "Compliance", href: "/admin/compliance", icon: ShieldCheck, blurb: "Compliance review.", adminOnly: true },
  { label: "Indicators", href: "/admin/indicators", icon: Sparkles, blurb: "Indicator approvals.", adminOnly: true },
  { label: "Announcements", href: "/admin/announcements", icon: Bell, blurb: "Sab ko batao.", adminOnly: true },
];

/** Every non-admin item, flattened. Used by the header lookup and the tests. */
export const ALL_PRO_ITEMS: ProNavItem[] = PRO_NAV.flatMap((g) => g.items);

/** Longest-prefix lookup so a detail route inherits its section's header. */
export function navItemForPath(pathname: string): ProNavItem | undefined {
  const all = [...ALL_PRO_ITEMS, ...ADMIN_NAV];
  const exact = all.find((i) => i.href === pathname);
  if (exact) return exact;
  const child = ALL_PRO_ITEMS.flatMap((i) => (i.children ?? []).map((c) => ({ i, c })))
    .find(({ c }) => c.href === pathname);
  if (child) return child.i;
  return all
    .filter((i) => i.href !== "/" && pathname.startsWith(i.href + "/"))
    .sort((a, b) => b.href.length - a.href.length)[0];
}

/** Old URLs that moved, and where they went. Rendered as redirects in next.config. */
export const MOVED_URLS: Record<string, string> = {
  "/strategies/indicators": "/indicators",
  "/support/faq": "/help",
  "/support": "/help",
  "/alerts": "/settings",
};
