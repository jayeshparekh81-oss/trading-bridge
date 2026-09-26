/**
 * Every in-app link must land on a page that exists (2026-09-26).
 *
 * Found while chasing a live-site 404 report after the 26 Sep publish: the
 * AlgoMitra chat's "funds" flow sent customers to "/dashboard", which has
 * never been a page on this site — `(dashboard)` is a route GROUP, so its
 * home page is served at "/". The button was dead from the day it was
 * written (643a8f52, 25 Apr 2026).
 *
 * This test builds the list of real URLs from the `src/app` folder (the same
 * rule Next.js uses: `(group)` folders add nothing to the URL, `[param]`
 * matches one segment) and checks:
 *   1. the two pages the 26 Sep publish added (/start, /journey) are routes;
 *   2. every chat-widget "open_url" button points at a real route;
 *   3. every literal in-app link in `src` (href / url / push / replace /
 *      redirect with a quoted "/path") points at a real route.
 */

import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join, relative, sep } from "node:path";

import { FLOWS } from "@/lib/algomitra-flows";

const SRC = join(process.cwd(), "src");
const APP = join(SRC, "app");

function walk(dir: string, acc: string[] = []): string[] {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) walk(p, acc);
    else acc.push(p);
  }
  return acc;
}

function appRoutes(): string[] {
  return walk(APP)
    .filter((f) => /[\\/]page\.(tsx|ts|jsx|js|mdx)$/.test(f))
    .map((f) => {
      const segs = relative(APP, f).split(sep).slice(0, -1);
      const kept = segs.filter((s) => !(s.startsWith("(") && s.endsWith(")")));
      return "/" + kept.join("/");
    });
}

const ROUTES = appRoutes();
const MATCHERS = ROUTES.map(
  (r) => new RegExp("^" + r.replace(/\[\[?\.{0,3}[^\]]+\]\]?/g, "[^/]+") + "$"),
);

function resolves(url: string): boolean {
  const path = url.split(/[?#]/)[0].replace(/\/$/, "") || "/";
  return MATCHERS.some((m) => m.test(path));
}

describe("in-app links land on real pages", () => {
  it("the route list is built from src/app (sanity)", () => {
    expect(ROUTES).toContain("/");
    expect(ROUTES).toContain("/marketplace/me");
    expect(ROUTES.length).toBeGreaterThan(20);
  });

  it("/start and /journey exist as pages (26 Sep publish)", () => {
    expect(resolves("/start")).toBe(true);
    expect(resolves("/journey")).toBe(true);
  });

  it("'/dashboard' is NOT a page — (dashboard) is a route group served at '/'", () => {
    expect(resolves("/dashboard")).toBe(false);
  });

  it("every AlgoMitra open_url button points at a real page", () => {
    const dead: string[] = [];
    type Opt = { label: string; action?: { kind: string; url?: string } };
    for (const [flowId, flow] of Object.entries(
      FLOWS as Record<string, { steps: Record<string, { options?: readonly Opt[] }> }>,
    )) {
      for (const [stepId, step] of Object.entries(flow.steps)) {
        for (const opt of step.options ?? []) {
          const url = opt.action?.kind === "open_url" ? opt.action.url : undefined;
          if (url && url.startsWith("/") && !resolves(url)) {
            dead.push(`${flowId}.${stepId} "${opt.label}" -> ${url}`);
          }
        }
      }
    }
    expect(dead).toEqual([]);
  });

  it("every literal in-app link in src points at a real page", () => {
    const re = /(?:href|url|push|replace|redirect)\(?\s*[=:]?\s*\{?\s*["'`](\/[A-Za-z0-9/_-]*)["'`]/g;
    const dead: string[] = [];
    for (const f of walk(SRC).filter((x) => /\.(tsx?|jsx?)$/.test(x))) {
      const text = readFileSync(f, "utf8");
      for (const m of text.matchAll(re)) {
        const url = m[1];
        if (url.startsWith("/api") || url.startsWith("/_next")) continue;
        if (!resolves(url)) dead.push(`${relative(SRC, f)}: ${url}`);
      }
    }
    expect(dead).toEqual([]);
  });
});
