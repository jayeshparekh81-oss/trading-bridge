/**
 * Pro information architecture, pinned.
 *
 * The founder's complaint was that Pro was 20 features with no story. The story
 * is six groups in a fixed order. These tests pin that story so it cannot drift
 * back — the sidebar and the drawer had ALREADY drifted apart before this work
 * (the drawer was missing three entries and called the kill switch by another
 * name), which is exactly what an untested nav does.
 */
import { describe, it, expect } from "vitest";
import { readFileSync, existsSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { PRO_NAV, ADMIN_NAV, ALL_PRO_ITEMS, MOVED_URLS, navItemForPath } from "@/lib/nav/pro-nav";

const APP = join(process.cwd(), "src/app/(dashboard)");
const SRC = join(process.cwd(), "src");
const KILL_SWITCH_LABEL = join(SRC, "lib/kill-switch-label.ts");
const read = (p: string) => readFileSync(p, "utf8");

describe("sidebar structure is pinned", () => {
  it("has exactly six groups, in this order", () => {
    expect(PRO_NAV.map((g) => g.title)).toEqual([
      "Ghar",
      "Trade karo",
      "Banao",
      "Seekho",
      "Control",
      "Madad",
    ]);
  });

  it("each group has exactly these members, in this order", () => {
    const members = Object.fromEntries(
      PRO_NAV.map((g) => [g.title, g.items.map((i) => i.label)]),
    );
    expect(members["Ghar"]).toEqual(["Overview"]);
    expect(members["Trade karo"]).toEqual([
      "Marketplace",
      "My Strategies",
      "Signals",
      "Positions",
      // Renamed 2026-09-10. This surface is the BOT's order log, not the
      // account's trade book — the founder's four-tab contract. Calling it
      // "Trades" while it deliberately excludes his manual trades was the
      // confusion the rename fixes.
      "Orders",
      "Chart",
    ]);
    expect(members["Banao"]).toEqual(["Strategies"]);
    expect(members["Seekho"]).toEqual(["Learn Indicators", "Track Record", "Indicator Requests"]);

    // The ONE entry that leaves the Pro chrome is declared as such, and both
    // the sidebar and the drawer open it in a new tab — so a customer who
    // taps it still has the Pro tab to come back to. If another entry ever
    // becomes external it must be declared here too, deliberately.
    const external = ALL_PRO_ITEMS.filter((i) => i.external).map((i) => i.href);
    expect(external).toEqual(["/showcase"]);
    for (const f of ["sidebar.tsx", "mobile-drawer.tsx"]) {
      const src = read(join(process.cwd(), "src/components/dashboard", f));
      expect(src).toContain("item.external");
      expect(src).toContain('target: "_blank"');
      expect(src).toContain('rel: "noopener noreferrer"');
    }
    expect(members["Control"]).toEqual([
      "Kill Switch",
      "Brokers",
      "Webhooks",
      "Analytics",
      "Settings",
      "Compliance",
    ]);
    expect(members["Madad"]).toEqual(["Help & Support"]);
  });

  it("Templates and Pine import live INSIDE Strategies, not as top-level entries", () => {
    const strategies = ALL_PRO_ITEMS.find((i) => i.href === "/strategies");
    expect(strategies?.children?.map((c) => c.href)).toEqual([
      "/strategies/templates",
      "/strategies/import-pine",
    ]);
    const topLevel = ALL_PRO_ITEMS.map((i) => i.href);
    expect(topLevel).not.toContain("/strategies/templates");
    expect(topLevel).not.toContain("/strategies/import-pine");
  });

  it("group headers are plain words, not caps-tracked labels", () => {
    for (const g of PRO_NAV) {
      expect(g.title).not.toEqual(g.title.toUpperCase());
    }
    for (const f of ["sidebar.tsx", "mobile-drawer.tsx"]) {
      const src = read(join(process.cwd(), "src/components/dashboard", f));
      const header = src.split("group.title")[0].slice(-400);
      expect(header, `${f} group header must not be uppercase/tracked`).not.toMatch(
        /uppercase|tracking-wider|tracking-widest/,
      );
    }
  });

  it("every sidebar entry points at a page that exists", () => {
    for (const item of [...ALL_PRO_ITEMS, ...ADMIN_NAV]) {
      const children = item.children ?? [];
      for (const href of [item.href, ...children.map((c) => c.href)]) {
        if (href === "/showcase") continue; // public route, outside (dashboard)
        const rel = href === "/" ? "page.tsx" : join(href.replace(/^\//, ""), "page.tsx");
        expect(existsSync(join(APP, rel)), `${href} has no page`).toBe(true);
      }
    }
  });
});

describe("desktop sidebar and mobile drawer are identical", () => {
  it("both render from the SAME module and keep no list of their own", () => {
    for (const f of ["sidebar.tsx", "mobile-drawer.tsx"]) {
      const src = read(join(process.cwd(), "src/components/dashboard", f));
      expect(src, `${f} must import the shared nav`).toMatch(/from "@\/lib\/nav\/pro-nav"/);
      expect(src, `${f} must not declare its own list`).not.toMatch(
        /const (navItems|adminItems)\s*[:=]/,
      );
    }
  });

  it("the bottom shortcut bar uses the same words as the sidebar", () => {
    const src = read(join(process.cwd(), "src/components/dashboard/mobile-nav.tsx"));
    expect(src).toMatch(/ALL_PRO_ITEMS/);
    expect(src, "the bottom bar must not retype a label").not.toMatch(/label: "/);
  });

  it("one name per thing — no retired synonyms survive in any nav surface", () => {
    for (const f of ["sidebar.tsx", "mobile-drawer.tsx", "mobile-nav.tsx"]) {
      const src = read(join(process.cwd(), "src/components/dashboard", f))
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .replace(/^\s*\/\/.*$/gm, "");
      expect(src, `${f} still says "Sab band"`).not.toMatch(/Sab band/);
      expect(src, `${f} still says "Contact Support"`).not.toMatch(/Contact Support/);
      expect(src, `${f} still says "Indicator Library"`).not.toMatch(/Indicator Library/);
    }
  });
});

describe("moved URLs redirect to their new home", () => {
  it("every moved route is a redirect stub pointing at its new home", () => {
    for (const [from, to] of Object.entries(MOVED_URLS)) {
      const file = join(APP, from.replace(/^\//, ""), "page.tsx");
      expect(existsSync(file), `${from} should still resolve`).toBe(true);
      const src = read(file);
      expect(src, `${from} must redirect`).toMatch(/redirect\(/);
      expect(src, `${from} must redirect to ${to}`).toContain(`"${to}"`);
    }
  });

  it("the merged indicators page serves BOTH former routes", () => {
    expect(read(join(APP, "indicators/page.tsx"))).toMatch(/useApi</);
    expect(read(join(APP, "strategies/indicators/page.tsx"))).toMatch(/redirect\("\/indicators"\)/);
  });

  it("the merged indicators page keeps the API catalog as the SOURCE and content as detail", () => {
    const src = read(join(APP, "indicators/page.tsx"));
    expect(src, "catalog is the source").toMatch(/"\/strategies\/indicators"/);
    expect(src, "educational content is the detail").toMatch(/getIndicator|IndicatorDetailModal/);
  });

  it("Help & Support carries FAQ and ticket filing on ONE page", () => {
    const help = read(join(APP, "help/page.tsx"));
    expect(help).toMatch(/TicketForm/);
    expect(help).toMatch(/MyTicketsList/);
    expect(read(join(APP, "support/page.tsx"))).toMatch(/redirect\("\/help"\)/);
  });
});

describe("one page template everywhere", () => {
  const pagesInGroups = ALL_PRO_ITEMS.filter((i) => i.href !== "/showcase").flatMap((i) => [
    i.href,
    ...(i.children ?? []).map((c) => c.href),
  ]);

  it("every page in the six groups uses ProPage and keeps no bespoke title", () => {
    const offenders: string[] = [];
    for (const href of pagesInGroups) {
      const rel = href === "/" ? "page.tsx" : join(href.replace(/^\//, ""), "page.tsx");
      const file = join(APP, rel);
      if (!existsSync(file)) continue;
      const src = read(file);
      if (/redirect\(/.test(src)) continue; // moved routes are stubs
      if (!/ProPage/.test(src)) offenders.push(`${href}: no ProPage`);
      else if (/<h1[\s>]/.test(src)) offenders.push(`${href}: still has its own <h1>`);
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });

  it("the header derives the title from the sidebar label, so they cannot disagree", () => {
    const shell = read(join(process.cwd(), "src/components/dashboard/pro-page.tsx"));
    expect(shell).toMatch(/navItemForPath/);
    expect(shell).toMatch(/item\?\.label/);
    expect(navItemForPath("/positions")?.label).toBe("Positions");
    expect(navItemForPath("/strategies/templates")?.label).toBe("Strategies");
  });

  it("no empty state says only 'No data'", () => {
    const walk = (dir: string, out: string[] = []): string[] => {
      for (const n of readdirSync(dir)) {
        const p = join(dir, n);
        if (statSync(p).isDirectory()) walk(p, out);
        else if (/page\.tsx$/.test(n)) out.push(p);
      }
      return out;
    };
    const bad = walk(APP).filter((f) => /No data(?!\w)|Nothing here|No results found\./i.test(read(f)));
    expect(bad, `bare empty state in:\n${bad.join("\n")}`).toEqual([]);
  });

  // Pro may use trader words (lots, NRML, webhook, round trip). What it may
  // NOT do is switch voice: half the empty states in Hinglish and half in
  // English is exactly the "bikhra hua" feeling. Every headline opens in the
  // one voice the rest of Pro speaks.
  it("every empty-state headline speaks in one voice", () => {
    const walk = (dir: string, out: string[] = []): string[] => {
      for (const n of readdirSync(dir)) {
        const p = join(dir, n);
        if (statSync(p).isDirectory()) walk(p, out);
        else if (/page\.tsx$/.test(n)) out.push(p);
      }
      return out;
    };
    const offenders: string[] = [];
    for (const f of walk(APP)) {
      for (const m of read(f).matchAll(/headline=(?:"([^"]*)"|\{[^}]*?"((?:No|Nothing)[^"]*)")/g)) {
        const text = m[1] ?? m[2] ?? "";
        if (/^(No|Nothing)\b/.test(text)) offenders.push(`${f}: ${text}`);
      }
    }
    expect(offenders, `English-voice headline:\n${offenders.join("\n")}`).toEqual([]);
  });
});

describe("one kill switch, one word", () => {
  // The founder hit this: the same switch read "Active" on /strategies and
  // "NORMAL" on /kill-switch. "NORMAL" was never a backend word — the backend
  // enum has exactly ACTIVE and TRIPPED. Every surface now asks one module,
  // the same way the bottom bar stopped retyping nav labels.
  const owner = readFileSync(KILL_SWITCH_LABEL, "utf8");
  const surfaces = [
    join(APP, "kill-switch/page.tsx"),
    join(APP, "page.tsx"),
    join(SRC, "components/strategies/kill-switch-summary.tsx"),
  ];

  it("every surface that shows the state reads the owner module", () => {
    for (const f of surfaces) {
      expect(readFileSync(f, "utf8"), f).toMatch(/killSwitchLabel/);
    }
  });

  it("no surface retypes a state word of its own", () => {
    for (const f of surfaces) {
      const body = readFileSync(f, "utf8");
      expect(body, `${f} invents "NORMAL"`).not.toMatch(/"NORMAL"/);
      expect(body, `${f} invents its own state word`).not.toMatch(/"(Active|Disabled)\./);
    }
  });

  it("the owner names three states, because an unarmed switch guards nothing", () => {
    expect(owner).toMatch(/Sab band hai/);
    expect(owner).toMatch(/Limit set nahi/);
    expect(owner).toMatch(/Chalu hai/);
  });
});

describe("Overview reads executions, not the dead trades table", () => {
  const src = read(join(APP, "page.tsx"));

  it("last trades come from the SAME endpoint the Trades page uses", () => {
    expect(src).toMatch(/\/strategies\/executions\?limit=/);
    const trades = read(join(APP, "trades/page.tsx"));
    expect(trades).toMatch(/\/strategies\/executions/);
    // The list still shows three; the wider fetch exists so "N trades aaj"
    // can be counted from the SAME rows the list is drawn from.
    expect(src).toMatch(/slice\(0,\s*3\)/);
  });

  it('"trades aaj" is counted from those rows, not the kill-switch counter', () => {
    // The kill switch's trades_today is a Redis cap counter. Reading it here
    // let the number contradict the list right below it.
    expect(src).not.toMatch(/ks\?\.trades_today/);
    expect(src).toMatch(/istDateKey/);
  });

  it('"Signals" names one thing: the Overview card says whose signals it counts', () => {
    // The sidebar's Signals page is the marketplace subscription inbox
    // (/marketplace/subscriptions/signals). Overview's card counts the
    // customer's OWN strategy signals (/strategies/signals). Two populations
    // may not share one unqualified word.
    expect(src).toMatch(/Aaj ke apne signals/);
    expect(src).not.toMatch(/>Aaj ke signals</);
    const signalsPage = read(join(APP, "signals/page.tsx"));
    expect(signalsPage).toMatch(/marketplace\/subscriptions\/signals/);
    expect(src).toMatch(/\/strategies\/signals/);
  });

  it("Overview never claims a live broker session it did not check", () => {
    // activeBrokers comes from the credential rows' is_active flag. Turning
    // that into "session zinda hai" invents a fact, and contradicts the
    // Simple status strip, which reads the broker's real session.
    expect(src).not.toMatch(/Session zinda hai/);
  });

  it("Overview never calls a /me/trades style endpoint", () => {
    expect(src).not.toMatch(/["'`]\/me\/trades/);
    expect(src).not.toMatch(/["'`]\/users\/me\/trades/);
  });

  it("shows the six things an overview must show", () => {
    expect(src, "signals count").toMatch(/Aaj ke signals/);
    expect(src, "open positions").toMatch(/Khuli positions/);
    // The kill-switch word is no longer typed into this page. It is looked up
    // from the ONE owner module, which is why /kill-switch, the /strategies
    // summary and this page could once call a single switch "NORMAL",
    // "Active." and "Chalu hai" — and cannot now.
    expect(src, "kill switch in plain words").toMatch(/killSwitchLabel/);
    expect(readFileSync(KILL_SWITCH_LABEL, "utf8")).toMatch(/Sab band hai/);
    expect(src, "broker status").toMatch(/Koi broker nahi juda|juda hua/);
    expect(src, "last 3 trades").toMatch(/Aakhri 3 trades/);
    expect(src, "aaj ka sabak").toMatch(/Aaj ka sabak/);
  });

  it("the Trading card cannot contradict the Broker card next to it", () => {
    // "Chalu hai" printed directly above "Broker jode bina koi order nahi
    // jayega" was one page making two claims about one fact. The headline is
    // now derived once, from the untripped switch AND the same activeBrokers
    // the Broker card renders AND an actually-active strategy.
    expect(src).toMatch(/const canTrade =/);
    expect(src).toMatch(/activeBrokers\.length > 0 && activeStrategies > 0/);
    expect(src, "reads whether a strategy is actually on").toMatch(/\/strategies\?limit=/);
  });

  it("its empty states say what to do next", () => {
    expect(src).toMatch(/ProEmpty/);
    expect(src).toMatch(/Marketplace kholo|My Strategies dekho/);
  });
});
