/**
 * Catalog template -> explainer page.
 *
 * Both sides key off the same seed slug: `TemplateSummary.slug` comes from
 * GET /templates and `StrategyExplainer.slug` matches the same seed row. So
 * the mapping is identity plus a membership check — never a name guess.
 * Returns null when no explainer has been authored, so a card renders no
 * link rather than a link into the "not written yet" fallback. Uses the
 * content-free slug list so the catalog bundle stays light.
 */

import { hasExplainer } from "@/lib/strategies/explainers/slugs";
import type { TemplateSummary } from "./types";

export function explainerSlugFor(template: Pick<TemplateSummary, "slug">): string | null {
  return hasExplainer(template.slug) ? template.slug : null;
}

export function explainerHrefFor(template: Pick<TemplateSummary, "slug">): string | null {
  const slug = explainerSlugFor(template);
  return slug ? `/strategies/templates/${slug}` : null;
}
