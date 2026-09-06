/**
 * ADR 0001 §5 (IA before UI) and §6 (one page template, one header shell).
 *
 * `tests/pro/pro-structure.test.ts` already checks the pages that sit in a nav
 * group. This test walks the WHOLE route map instead, so a page can no longer
 * dodge the template simply by not being in the sidebar — which is how the
 * detail pages, the builders and the admin console quietly diverged.
 *
 * The rule is not "every page must use ProPage". Some pages genuinely should
 * not: a chooser screen whose heading is a question, a long-form legal
 * document, a staff console. The rule is that every exception is DECLARED,
 * with a reason someone wrote down. A new page that is neither templated nor
 * declared fails the build.
 */
import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join } from "node:path";

const APP = join(process.cwd(), "src/app");
const read = (p: string) => readFileSync(p, "utf8");

function pageFiles(dir: string, out: string[] = []): string[] {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) pageFiles(p, out);
    else if (n === "page.tsx") out.push(p);
  }
  return out;
}

/** "src/app/(dashboard)/kill-switch/page.tsx" -> "/kill-switch" */
function routeOf(file: string): string {
  const rel = file.slice(APP.length + 1).replace(/\/page\.tsx$/, "");
  const url = rel
    .split("/")
    .filter((seg) => !/^\(.+\)$/.test(seg))
    .join("/");
  return "/" + url;
}

/**
 * Pages that deliberately do not render ProPage. Each needs a reason, and the
 * reason has to survive being read aloud to the founder.
 */
const TEMPLATE_EXCEPTIONS: Record<string, string> = {
  "/strategies/new":
    "A chooser screen. Its heading is a question — 'How do you want to start?' — and the nav label ('Strategies') would be a worse title, not a better one.",
  "/strategies/new/beginner": "Builder wizard: its own stepper is the page header.",
  "/strategies/new/intermediate": "Builder wizard: its own stepper is the page header.",
  "/strategies/new/expert": "Builder wizard: its own stepper is the page header.",
  "/strategies/[id]": "Detail view of one strategy; the title is the strategy's own name.",
  "/strategies/[id]/backtest": "Detail view; the title is the strategy's own name.",
  "/strategies/templates/[slug]": "Detail view of one template; the title is the template's own name.",
  "/marketplace/[id]": "Detail view; the strategy card IS the header, and a ProPage title above it would state the name twice.",
  "/compliance/legal": "Long-form legal document with its own document structure.",
  // The admin console is a staff tool, not a customer surface. It is excluded
  // from the customer vocabulary and template rules by the same decision that
  // excludes it from tests/pro/vocab.test.ts.
  "/admin": "Staff console, not a customer surface.",
  "/admin/users": "Staff console, not a customer surface.",
  "/admin/audit": "Staff console, not a customer surface.",
  "/admin/compliance": "Staff console, not a customer surface.",
  "/admin/indicators": "Staff console, not a customer surface.",
  "/admin/announcements": "Staff console, not a customer surface.",
  "/admin/kill-switch-events": "Staff console, not a customer surface.",
};

const dashboardPages = pageFiles(join(APP, "(dashboard)"));

describe("ADR 0001 §6 — one page template, across the whole route map", () => {
  it("every dashboard page either uses ProPage, redirects, or has a declared reason", () => {
    const undeclared: string[] = [];
    for (const file of dashboardPages) {
      const src = read(file);
      const route = routeOf(file);
      if (/redirect\(/.test(src)) continue; // moved-route stub
      if (/<ProPage/.test(src)) continue;
      if (TEMPLATE_EXCEPTIONS[route]) continue;
      undeclared.push(route);
    }
    expect(
      undeclared,
      `These pages skip the shared template with no recorded reason.\n` +
        `Either render <ProPage>, or add the route to TEMPLATE_EXCEPTIONS with a reason:\n  ${undeclared.join("\n  ")}`,
    ).toEqual([]);
  });

  it("a page that uses ProPage does not also carry its own <h1>", () => {
    const doubled = dashboardPages
      .filter((f) => /<ProPage/.test(read(f)) && /<h1[\s>]/.test(read(f)))
      .map(routeOf);
    expect(doubled, `Two titles on one page: ${doubled.join(", ")}`).toEqual([]);
  });

  it("every declared exception still points at a real route", () => {
    const routes = new Set(dashboardPages.map(routeOf));
    const stale = Object.keys(TEMPLATE_EXCEPTIONS).filter((r) => !routes.has(r));
    expect(stale, `Exception listed for a route that no longer exists: ${stale.join(", ")}`).toEqual([]);
  });

  it("every declared exception carries a real reason, not a placeholder", () => {
    for (const [route, reason] of Object.entries(TEMPLATE_EXCEPTIONS)) {
      expect(reason.length, `${route}: reason too short to be a reason`).toBeGreaterThan(25);
      expect(reason, `${route}: placeholder reason`).not.toMatch(/^(TODO|FIXME|n\/a|because)/i);
    }
  });
});

describe("ADR 0001 §6 — one header shell", () => {
  it("the public site and the app render the SAME header shell", () => {
    const publicLayout = read(join(APP, "(public)/layout.tsx"));
    const topBar = read(join(process.cwd(), "src/components/dashboard/top-bar.tsx"));
    for (const [name, src] of [
      ["(public)/layout.tsx", publicLayout],
      ["dashboard/top-bar.tsx", topBar],
    ] as const) {
      expect(src, `${name} must render the shared HeaderShell`).toMatch(/components\/site\/header-shell/);
      expect(src, `${name} must not hand-roll its own <header>`).not.toMatch(/<header\b/);
    }
  });

  it("the header shell exists and exports its shared tokens", () => {
    const shell = join(process.cwd(), "src/components/site/header-shell.tsx");
    expect(existsSync(shell)).toBe(true);
    const src = read(shell);
    expect(src).toMatch(/export const HEADER_SHELL_TOKENS/);
    expect(src).toMatch(/export const HEADER_LOGO/);
  });
});

describe("ADR 0001 §5 — no orphan routes", () => {
  // A route nobody can reach is either dead code or a missing nav entry. Both
  // are decisions, so both must be written down.
  const REACHABLE_WITHOUT_NAV: Record<string, string> = {
    "/strategies/new": "Opened by the 'Nayi strategy' action on the Strategies page.",
    "/strategies/new/beginner": "Opened from the /strategies/new chooser.",
    "/strategies/new/intermediate": "Opened from the /strategies/new chooser.",
    "/strategies/new/expert": "Opened from the /strategies/new chooser, and by ?edit= deep links.",
    "/strategies/[id]": "Opened from the strategies list.",
    "/strategies/[id]/backtest": "Opened from the strategy detail page.",
    "/strategies/templates/[slug]": "Opened from the templates list.",
    "/strategies/indicators": "Redirect stub kept so old links keep working.",
    "/marketplace/[id]": "Opened from the marketplace and from the public Track Record.",
    "/compliance": "Reached from the Control group and the site footer.",
    "/compliance/legal": "Reached from the site footer.",
    "/support": "Redirect stub kept so old links keep working.",
    "/support/faq": "Redirect stub kept so old links keep working.",
    "/alerts": "Redirect stub kept so old links keep working.",
    "/admin": "Staff console, shown only to admins.",
    "/admin/users": "Staff console, shown only to admins.",
    "/admin/audit": "Staff console, shown only to admins.",
    "/admin/compliance": "Staff console, shown only to admins.",
    "/admin/indicators": "Staff console, shown only to admins.",
    "/admin/announcements": "Staff console, shown only to admins.",
    "/admin/kill-switch-events": "Staff console, shown only to admins.",
  };

  it("every dashboard route is in the nav or has a recorded way in", async () => {
    const nav = read(join(process.cwd(), "src/lib/nav/pro-nav.ts"));
    const orphans = dashboardPages
      .map(routeOf)
      .filter((r) => !nav.includes(`"${r}"`) && !REACHABLE_WITHOUT_NAV[r]);
    expect(
      orphans,
      `Unreachable route(s) — add a nav entry, or record how a customer gets there:\n  ${orphans.join("\n  ")}`,
    ).toEqual([]);
  });
});
