/**
 * Customer-journey fixes from the 2026-09-03 walkthrough — pinned so they
 * cannot quietly regress. Each block names the thing a first-time customer
 * actually hit.
 */

import { describe, it, expect } from "vitest";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const read = (p: string) => readFileSync(join(process.cwd(), p), "utf8");
const code = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

// ── Nav: what a customer is shown ─────────────────────────────────────

describe("sidebar + drawer show a customer only what they can use", () => {
  const SIDEBAR = read("src/components/dashboard/sidebar.tsx");
  const DRAWER = read("src/components/dashboard/mobile-drawer.tsx");

  it("🔴 admin items are gated on user.is_admin (they rendered for everyone)", () => {
    for (const src of [SIDEBAR, DRAWER]) {
      expect(src).toMatch(/const isAdmin = !!user\?\.is_admin/);
      expect(src).toMatch(/\{isAdmin && \(/);
    }
  });

  it("🔴 'Indicator Requests' is creator-only (its endpoint answers 403 to a customer)", () => {
    // The gate moved from each nav component into the shared nav module; both
    // the sidebar and the drawer now render from it, so ONE flag gates both.
    const nav = read("src/lib/nav/pro-nav.ts");
    const block = nav.slice(nav.indexOf('"/indicators/requests"'));
    expect(block.slice(0, 300)).toMatch(/creatorOnly: true/);
  });

  it("no 'Soon' pill on a wired page — only /alerts still renders ComingSoon", () => {
    // Stronger than before: there is no "Soon" pill at all now. /alerts was the
    // only one and it rendered a placeholder behind a nav entry, so it was
    // retired to a redirect rather than kept as clutter.
    for (const src of [SIDEBAR, DRAWER]) {
      expect(code(src)).not.toMatch(/comingSoon/);
    }
    expect(read("src/app/(dashboard)/alerts/page.tsx")).toMatch(/redirect\("\/settings"\)/);
  });

  it("admin labels are words, not abbreviations", () => {
    expect(SIDEBAR).not.toMatch(/label: "KS Events"/);
    expect(SIDEBAR).not.toMatch(/label: "Announce"/);
  });
});

// ── Orphans ───────────────────────────────────────────────────────────

describe("orphan builder pages are gone", () => {
  it.each(["entry", "exit", "risk"])("/strategies/builder/%s no longer exists", (p) => {
    expect(existsSync(join(process.cwd(), `src/app/(dashboard)/strategies/builder/${p}/page.tsx`))).toBe(false);
  });
  it("nothing links to them", () => {
    // cheap sweep of the app tree
    const walk = (dir: string, acc: string[] = []): string[] => {
      for (const e of readdirSync(dir, { withFileTypes: true })) {
        const p = join(dir, e.name);
        if (e.isDirectory()) walk(p, acc);
        else if (/\.(tsx?|mdx?)$/.test(e.name)) acc.push(p);
      }
      return acc;
    };
    const hits = walk(join(process.cwd(), "src")).filter((f) => /strategies\/builder\/(entry|exit|risk)/.test(readFileSync(f, "utf8")));
    expect(hits).toEqual([]);
  });
});

// ── Backtest honesty ──────────────────────────────────────────────────

describe("backtest is honest about sample data", () => {
  const BT = read("src/app/(dashboard)/strategies/[id]/backtest/page.tsx");

  it("🔴 never celebrates a synthetic result", () => {
    // the guard must sit inside the celebration effect, before any confetti
    const effect = BT.slice(BT.indexOf("lastCelebrationKey.current = key"), BT.indexOf("isDoubleA) {"));
    expect(effect).toMatch(/candles_source !== "dhan_historical"\) return/);
  });

  it("no longer promises a real run 'after market close' that nothing queues", () => {
    expect(code(BT)).not.toMatch(/runs after market close/i);
    expect(BT).toContain('data-testid="synthetic-notice"');
    expect(BT).toMatch(/SAMPLE data, not the market/);
  });
});

// ── Onboarding tour tells the truth ───────────────────────────────────

describe("onboarding tour", () => {
  const T = read("src/lib/onboarding/tourSteps.ts");
  it("makes no claim the product cannot back", () => {
    const body = code(T);
    for (const bad of [/drag,? drop/i, /70 indicators/, /TradingView-grade/i, /24×7/, /India's first/i]) {
      expect(body).not.toMatch(bad);
    }
  });
  it("step 4 targets an element that renders (the strategies nav), not a banner that never mounts", () => {
    expect(T).not.toContain('paper-mode-banner');
  });
});

// ── Overview: a zero-state customer gets a next step ──────────────────

describe("overview for a brand-new account", () => {
  const OV = read("src/app/(dashboard)/page.tsx");
  it("🔴 shows a Start-here card instead of an ops metric", () => {
    // A brand-new account sees empty states that say what to do next (ProEmpty
    // renders data-testid="start-here"), never an ops metric.
    expect(OV).toMatch(/ProEmpty/);
    expect(read("src/components/dashboard/pro-page.tsx")).toContain('data-testid="start-here"');
    expect(code(OV)).not.toMatch(/Backend health/);
    expect(code(OV)).not.toMatch(/\/health returned ok/);
  });
  it("links each step to the real page", () => {
    // Every next step on the Overview points at a real page.
    for (const href of ['"/brokers"', '"/marketplace"', '"/marketplace/me"', '"/kill-switch"', '"/positions"', '"/trades"'])
      expect(OV).toContain(href);
  });
  it("drops the threshold jargon from the signals card", () => {
    expect(code(read("src/components/dashboard/conviction-signals.tsx"))).not.toMatch(/regime-adjusted\. Verdict/);
  });
});

// ── Stale copy: promises the backend cannot back ──────────────────────

describe("stale promises are gone from shipped pages", () => {
  const files = {
    alerts: "src/app/(dashboard)/alerts/page.tsx",
    settings: "src/app/(dashboard)/settings/page.tsx",
    killswitch: "src/app/(dashboard)/kill-switch/page.tsx",
    webhooks: "src/app/(dashboard)/webhooks/page.tsx",
    analytics: "src/app/(dashboard)/analytics/page.tsx",
    me: "src/app/(dashboard)/marketplace/me/page.tsx",
    listing: "src/app/(dashboard)/marketplace/[id]/page.tsx",
    templates: "src/app/(dashboard)/strategies/templates/page.tsx",
    templateCard: "src/components/strategy-templates/TemplateCard.tsx",
    detail: "src/app/(dashboard)/strategies/[id]/page.tsx",
    intermediate: "src/app/(dashboard)/strategies/new/intermediate/page.tsx",
    expert: "src/app/(dashboard)/strategies/new/expert/page.tsx",
    banner: "src/components/brokers/ReconnectInfoBanner.tsx",
    roadmap: "src/components/marketing/RoadmapSection.tsx",
    indicators: "src/components/chart/IndicatorsDropdown.tsx",
  } as const;
  const bodies = Object.fromEntries(Object.entries(files).map(([k, p]) => [k, code(read(p))]));

  it("Telegram is not sold as a customer channel anywhere it is not one", () => {
    expect(bodies.alerts).not.toMatch(/already firing/i);
    expect(bodies.settings).not.toMatch(/Real-time push to your Telegram/);
    expect(bodies.settings).not.toMatch(/Order fills, kill-switch trips/);
    expect(bodies.killswitch).not.toMatch(/CRITICAL Telegram alert/);
  });
  it("no undated 'future sprint' / 'Phase N' promises on customer pages", () => {
    for (const k of ["webhooks", "analytics", "me", "listing", "templates", "templateCard", "detail", "intermediate", "expert"] as const) {
      expect(bodies[k], k).not.toMatch(/future sprint/i);
      expect(bodies[k], k).not.toMatch(/Phase [3-8]\b/);
    }
  });
  it("the brokers banner and the public roadmap carry no dated targets", () => {
    expect(bodies.banner).not.toMatch(/target: \d/);
    expect(bodies.roadmap).not.toMatch(/2026/);
    expect(bodies.roadmap).not.toMatch(/drag-drop|BLACK BOX|10 regional/);
  });
  it("My Strategies speaks to the subscriber, not to creators", () => {
    expect(bodies.me).not.toMatch(/Creators yahan se/);
  });
  it("indicator count claim matches the dropdown", () => {
    expect(bodies.indicators).not.toMatch(/sirf default 4/);
  });
});


// ── One name per thing: nav label = page title ─────────────────────────

describe("nav label equals page title", () => {
  // The INTENT is unchanged and is still the rule: one name per thing, and the
  // page title is the sidebar label. The MECHANISM changed in the Pro
  // reorganisation — a page no longer carries its own <h1>. The title is derived
  // from @/lib/nav/pro-nav by the shared ProPage header, so the sidebar and the
  // title cannot disagree by construction. These assertions moved from
  // "each page repeats its label" to "no page repeats it, and the shared header
  // derives it". tests/pro/pro-structure.test.ts pins the rest.
  const templated: [string, string][] = [
    ["brokers", "src/app/(dashboard)/brokers/page.tsx"],
    ["positions", "src/app/(dashboard)/positions/page.tsx"],
    ["trades", "src/app/(dashboard)/trades/page.tsx"],
    ["marketplace", "src/app/(dashboard)/marketplace/page.tsx"],
    ["compliance", "src/app/(dashboard)/compliance/page.tsx"],
  ];

  it.each(templated)("%s page takes its title from the shared header", (_n, file) => {
    const src = read(file);
    expect(src, "must use the shared page template").toMatch(/ProPage/);
    expect(src, "must not carry its own page title").not.toMatch(/<h1[\s>]/);
  });

  it("the shared header derives the title from the nav label", () => {
    const shell = read("src/components/dashboard/pro-page.tsx");
    expect(shell).toMatch(/navItemForPath/);
    expect(shell).toMatch(/item\?\.label/);
  });

  it("Contact Support is gone as a separate page — one Help & Support", () => {
    expect(read("src/app/(dashboard)/support/page.tsx")).toMatch(/redirect\("\/help"\)/);
    expect(read("src/app/(dashboard)/help/page.tsx")).toMatch(/TicketForm/);
  });

  it("the two indicator pages became one", () => {
    expect(read("src/app/(dashboard)/strategies/indicators/page.tsx")).toMatch(
      /redirect\("\/indicators"\)/,
    );
    expect(read("src/app/(dashboard)/indicators/page.tsx")).toMatch(/ProPage/);
  });

  it("mobile tabs use the same names as the sidebar", () => {
    const nav = read("src/components/dashboard/mobile-nav.tsx");
    // The bottom bar no longer retypes labels — it looks them up from the same
    // module the sidebar uses, which is why "Sab band" could drift from
    // "Kill Switch" before and cannot now.
    expect(nav).toMatch(/ALL_PRO_ITEMS/);
    expect(nav).toMatch(/"\/marketplace\/me"/);
    expect(nav).not.toMatch(/label: "/);
  });
});

// ── Dead and ambiguous controls ────────────────────────────────────────

describe("dead and ambiguous controls", () => {
  it("brokers: no 'Notify Me' button without a handler", () => {
    expect(code(read("src/app/(dashboard)/brokers/page.tsx"))).not.toMatch(/Notify Me/);
  });
  it("dates spell the month (3/9/2026 was ambiguous)", () => {
    expect(read("src/app/(dashboard)/marketplace/me/page.tsx")).toMatch(/month: "short"/);
    expect(read("src/app/(dashboard)/settings/page.tsx")).toMatch(/month: "short"/);
  });
  it("a never-started subscription offers 'Start auto-execution', not 'Resume'", () => {
    const b = code(read("src/components/marketplace/pause-deployment-button.tsx"));
    expect(b).toMatch(/Start auto-execution/);
    expect(b).not.toMatch(/\? "Resume"/);
  });
  it("settings captions are real <label>s (the input is nested, so it is announced and focusable)", () => {
    const s = read("src/app/(dashboard)/settings/page.tsx");
    const row = s.slice(s.indexOf("function FieldRow"), s.indexOf("function ToggleRow"));
    expect(row).toMatch(/<label className="block[^"]*">\s*<span[^>]*>\{label\}<\/span>\s*\{children\}\s*<\/label>/);
  });
  it("pre-flight 'Fix' links point at routes that exist (paper-sessions and /settings/account never did)", () => {
    for (const f of ["src/components/strategies/order-result-card.tsx", "src/components/strategies/safety-pre-flight-panel.tsx"]) {
      const b = code(read(f));
      expect(b, f).not.toMatch(/paper-sessions/);
      expect(b, f).not.toMatch(/settings\/account/);
      expect(b, f).toMatch(/return "\/settings";/);
    }
    expect(existsSync(join(process.cwd(), "src/app/(dashboard)/strategies/[id]/paper-sessions"))).toBe(false);
    expect(existsSync(join(process.cwd(), "src/app/(dashboard)/settings/account"))).toBe(false);
  });
  it("the avatar menu's Settings opens /settings and the inert Profile item is gone", () => {
    const b = code(read("src/components/dashboard/top-bar.tsx"));
    expect(b).toMatch(/data-testid="user-menu-settings" onClick=\{\(\) => router\.push\("\/settings"\)\}/);
    expect(b).not.toMatch(/<User className[^>]*\/> Profile/);
  });
  it("🔴 picking a builder on /strategies/new is not asked again by a dialog on top of the wizard", () => {
    const door = code(read("src/app/(dashboard)/strategies/new/page.tsx"));
    expect(door).toMatch(/onClick=\{\(\) => rememberMode\(href\)\}/);
    expect(door).toMatch(/localStorage\.setItem\(STRATEGY_MODE_STORAGE_KEY, m\[1\]\)/);
    const modal = code(read("src/components/strategies/builder-onboarding-modal.tsx"));
    expect(modal).toMatch(/const picked = window\.localStorage\.getItem\(STRATEGY_MODE_STORAGE_KEY\);\s*if \(seen !== "1" && !picked\)/);
    expect(modal).not.toMatch(/switch at any time from the strategies page/);
  });
  it("🔴 the AlgoMitra panel no longer covers the builder's Next button — the page reserves its 320px while it is open", () => {
    const lay = code(read("src/app/(dashboard)/layout.tsx"));
    expect(lay).toMatch(/const \{ isOpen: coachOpen \} = useAlgoMitraPanelState\(\)/);
    expect(lay).toMatch(/coachOpen && \/\^\\\/strategies\\\/new\\\/\(beginner\|intermediate\|expert\)/);
    expect(lay).toMatch(/coachReservesSpace && "md:pr-\[320px\]"/);
    // and the panel really is 320px wide, fixed right
    const panel = read("src/components/algomitra/always-on-panel.tsx");
    expect(panel).toMatch(/max-w-\[320px\]/);
    expect(panel).toMatch(/fixed right-0/);
  });
  it("the top bar carries no dead controls (search box with no handler, bell with a hardcoded 0)", () => {
    const b = code(read("src/components/dashboard/top-bar.tsx"));
    expect(b).not.toMatch(/Ctrl\+K/);
    expect(b).not.toMatch(/aria-label="Notifications"/);
    expect(b).not.toMatch(/notificationCount/);
  });
  it("Learn Indicators and Compliance are reachable on a phone (drawer), not only in the desktop sidebar", () => {
    // The drawer renders the shared nav, so "reachable on a phone" is now a
    // property of that list rather than of a second hand-maintained copy.
    const d = read("src/components/dashboard/mobile-drawer.tsx");
    expect(d).toMatch(/PRO_NAV/);
    const nav = read("src/lib/nav/pro-nav.ts");
    expect(nav).toMatch(/href: "\/indicators"/);
    expect(nav).toMatch(/href: "\/compliance"/);
  });
  it("the indicator library does not point at a 'mode at the top of /strategies' that is never rendered", () => {
    // The page is gone: the catalog and the glossary are one page at /indicators
    // now, so the stale pointer cannot exist.
    const b = read("src/app/(dashboard)/strategies/indicators/page.tsx");
    expect(b).toMatch(/redirect\("\/indicators"\)/);
    expect(code(read("src/app/(dashboard)/indicators/page.tsx"))).not.toMatch(
      /Mode at the top of \/strategies/,
    );
  });
  it("residuals from the verifier: no 24x7 in any language, banner disclaimers agree in hi/gu, notice names a real control", () => {
    expect(code(read("src/lib/onboarding/tourSteps.ts"))).not.toMatch(/24 ?[x×\/] ?7/i);
    const banner = code(read("src/components/brokers/ReconnectInfoBanner.tsx"));
    expect(banner).not.toMatch(/Targets (हैं|છે)/);
    const bt = read("src/app/(dashboard)/strategies/[id]/backtest/page.tsx");
    expect(bt).toMatch(/&ldquo;Re-run with different data&rdquo;/);
    expect(bt).not.toMatch(/Re-run on real data/);
  });
  it("realised P&L is labelled 'net of modelled charges' wherever the reconciler's figure appears", () => {
    const pos = read("src/app/(dashboard)/positions/page.tsx");
    expect(pos).toMatch(/Realised P&amp;L <span[^>]*>\(net of modelled charges\)<\/span>/);
    expect(pos).toMatch(/not the broker's contract note/);
    const panel = read("src/components/marketplace/transparency-ledger-panel.tsx");
    expect(panel).toMatch(/isNetOfModelled \? "Cumulative P&L \(net of modelled charges\)"/);
    expect(panel).toMatch(/data-testid="ledger-pnl-basis"/);
    expect(panel).toMatch(/could not be priced from platform data and are excluded, not zeroed/);
    const modal = read("src/components/marketplace/ledger-history-modal.tsx");
    expect(modal).toMatch(/Net of modelled charges — fills real, charges estimated/);
    // live listings publish the drawdown in rupees (the percent is null on the chain)
    expect(panel).toMatch(/max_drawdown_pct === null \? "Max Drawdown \(₹, peak to trough\)"/);
    expect(modal).toMatch(/snapshot\.max_drawdown_pct === null/);
  });
  it("the webhook dialog's action says what the button that opened it said", () => {
    const w = code(read("src/app/(dashboard)/webhooks/page.tsx"));
    expect(w).toMatch(/"Creating…" : "Create webhook"/);
    expect(w).not.toMatch(/: "Generate"/);
  });
});
