/**
 * Founder decision (2026-09-04): every template card links to its explainer
 * (/strategies/templates/[slug]) — 44 authored pages had zero inbound links.
 * The link renders if and only if the slug resolves in the explainer
 * registry, so the catalog can never link into the "not written yet" page.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) =>
    React.createElement("a", { href, ...rest }, children),
}));

import { TemplateCard } from "@/components/strategy-templates/TemplateCard";
import { explainerHrefFor, explainerSlugFor } from "@/lib/strategy-templates/explainer-link";
import { EXPLAINERS, EXPLAINER_COUNT, getExplainer } from "@/lib/strategies/explainers";
import { EXPLAINER_SLUGS, hasExplainer } from "@/lib/strategies/explainers/slugs";
import catalog from "../fixtures/template-catalog-slugs.json";
import type { TemplateSummary } from "@/lib/strategy-templates/types";

function tpl(over: Partial<TemplateSummary>): TemplateSummary {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    slug: "ema-crossover-9-21",
    name: "EMA Crossover 9/21",
    segment: "equity",
    instrument_type: "cash",
    category: "trend",
    complexity: "beginner",
    description_en: "d",
    description_hi: "d",
    risk_level: "medium",
    recommended_capital_inr: 50000,
    timeframe: "15m",
    indicators_used: ["ema"],
    index_filter: null,
    tags: [],
    is_active: true,
    requires_options_builder: false,
    legs_count: 1,
    display_order: 1,
    ...over,
  } as TemplateSummary;
}

describe("explainer link helper", () => {
  it("resolves a known slug to its page and an unknown slug to null", () => {
    expect(explainerSlugFor({ slug: "ema-crossover-9-21" })).toBe("ema-crossover-9-21");
    expect(explainerHrefFor({ slug: "ema-crossover-9-21" })).toBe("/strategies/templates/ema-crossover-9-21");
    expect(explainerHrefFor({ slug: "iron-condor-nifty-weekly" })).toBeNull();
  });
  it("the content-free slug list matches the content registry exactly (the card bundle relies on it)", () => {
    expect([...EXPLAINER_SLUGS].sort()).toEqual(Object.keys(EXPLAINERS).sort());
    for (const slug of Object.keys(EXPLAINERS)) expect(hasExplainer(slug), slug).toBe(true);
    expect(hasExplainer("iron-condor-nifty-weekly")).toBe(false);
  });
  it("every authored explainer resolves to itself (no slug drift in the registry)", () => {
    expect(EXPLAINER_COUNT).toBe(44);
    for (const slug of Object.keys(EXPLAINERS)) {
      expect(getExplainer(slug)?.slug, slug).toBe(slug);
      expect(explainerHrefFor({ slug })).toBe(`/strategies/templates/${slug}`);
    }
  });
});

describe("catalog coverage (prod strategy_templates, read-only capture 2026-09-04)", () => {
  const active = catalog.templates.filter((t) => t.is_active);
  it("🔴 every ACTIVE catalog template has an explainer — a customer never sees a card without 'Learn more' on an active strategy", () => {
    const missing = active.filter((t) => !getExplainer(t.slug)).map((t) => t.slug);
    expect(missing).toEqual([]);
    expect(active.length).toBe(27);
  });
  it("every explainer slug exists in the catalog (no orphan pages)", () => {
    const slugs = new Set(catalog.templates.map((t) => t.slug));
    for (const slug of Object.keys(EXPLAINERS)) expect(slugs.has(slug), slug).toBe(true);
  });
  it("inactive templates without an explainer are the options/advanced set (reported, not linked)", () => {
    const missing = catalog.templates.filter((t) => !t.is_active && !getExplainer(t.slug));
    expect(missing.length).toBe(69);
  });
});

describe("TemplateCard", () => {
  it("renders 'Learn more' → /strategies/templates/[slug] when an explainer exists", () => {
    render(<TemplateCard template={tpl({})} onView={() => {}} onClone={() => {}} />);
    const link = screen.getByTestId("template-card-explainer-link");
    expect(link).toHaveAttribute("href", "/strategies/templates/ema-crossover-9-21");
    expect(link).toHaveTextContent("Learn more");
    expect(link).toHaveAttribute("aria-label", "Learn more about EMA Crossover 9/21");
  });
  it("renders NO explainer link when the slug has no authored page (never a dead link)", () => {
    render(<TemplateCard template={tpl({ slug: "iron-condor-nifty-weekly", name: "Iron Condor", is_active: false })} onView={() => {}} onClone={() => {}} />);
    expect(screen.queryByTestId("template-card-explainer-link")).toBeNull();
  });
  it("the link is not gated on card state — a Coming Soon card with an explainer still links", () => {
    render(<TemplateCard template={tpl({ slug: "vwap-bounce", name: "VWAP Bounce", is_active: false })} onView={() => {}} onClone={() => {}} />);
    expect(screen.getByTestId("template-card-explainer-link")).toHaveAttribute("href", "/strategies/templates/vwap-bounce");
  });
});
