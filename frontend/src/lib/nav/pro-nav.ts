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
        // NOT "live P&L". This said "unka live P&L" and the page has never
        // shown one: an OPEN row has no P&L at all (final_pnl is written only
        // when the trade closes and is reconciled against the broker's fills),
        // so the promise was contradicted by the first row under it. Live P&L
        // would mean polling an LTP per open position on the same Dhan quota
        // the trading engine uses — a separate founder decision, not something
        // a subtitle gets to imply.
        blurb: "Abhi jo trades khuli hain. P&L trade band hone par aata hai.",
      },
      {
        label: "Orders",
        href: "/trades",
        icon: ListOrdered,
        blurb: "TRADETRI ke orders. Aapke manual trades yahan nahi hain.",
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


/**
 * 2 Oct 2026 (English default): the group titles and the blurbs above are the Hinglish SOURCE; a
 * screen renders them through the app dictionary (lib/i18n/copy/app.ts: nav_g_* / nav_b_* / nav_a_*),
 * so the chrome and the page title line are in the customer's ONE language. The maps below are
 * total over PRO_NAV — tests/i18n/pro-nav-words.test.ts fails if an item has no key.
 */
export const NAV_GROUP_KEY: Record<string, string> = {
  Ghar: "nav_g_ghar", "Trade karo": "nav_g_trade", Banao: "nav_g_banao", Seekho: "nav_g_seekho", Control: "nav_g_control", Madad: "nav_g_madad",
};
export const NAV_BLURB_KEY: Record<string, string> = {
  "/": "nav_b_home", "/marketplace": "nav_b_marketplace", "/marketplace/me": "nav_b_my_strategies", "/signals": "nav_b_signals",
  "/positions": "nav_b_positions", "/trades": "nav_b_orders", "/chart": "nav_b_chart", "/strategies": "nav_b_strategies",
  "/indicators": "nav_b_indicators", "/showcase": "nav_b_showcase", "/indicators/requests": "nav_b_indicator_requests",
  "/kill-switch": "nav_b_kill_switch", "/brokers": "nav_b_brokers", "/webhooks": "nav_b_webhooks", "/analytics": "nav_b_analytics",
  "/settings": "nav_b_settings", "/compliance": "nav_b_compliance", "/help": "nav_b_help",
};
export const NAV_ACTION_KEY: Record<string, string> = { "/strategies/new": "nav_a_new_strategy", "/brokers?add=1": "nav_a_connect_broker" };

type Words = Record<string, string>;
/** The group title in the customer's language (admin groups have no key → their English label). */
export function navGroupTitle(c: Words, title: string): string {
  const k = NAV_GROUP_KEY[title];
  return k ? c[k] : title;
}
/** The one plain line under a page title, in the customer's language. */
export function navBlurb(c: Words, item: ProNavItem | undefined): string {
  if (!item) return "";
  const k = NAV_BLURB_KEY[item.href];
  return k ? c[k] : item.adminOnly ? item.blurb : "";
}
export function navAction(c: Words, item: ProNavItem | undefined): { label: string; href: string } | undefined {
  if (!item?.action) return undefined;
  const k = NAV_ACTION_KEY[item.action.href];
  return { label: k ? c[k] : item.action.label, href: item.action.href };
}
