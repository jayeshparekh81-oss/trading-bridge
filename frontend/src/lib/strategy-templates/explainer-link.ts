/**
 * Catalog template -> explainer page.
 *
 * Both sides key off the same seed slug: `TemplateSummary.slug` comes from
 * GET /templates and `StrategyExplainer.slug` matches the same seed row. So
 * the mapping is identity plus a membership check — never a name guess.
 * Returns null when no explainer has been authored, so a card renders no
 * link rather than a link into the "not written yet" fallback.
 */

import { getExplainer } from "@/lib/strategies/explainers";
import type { TemplateSummary } from "./types";

export function explainerSlugFor(template: Pick<TemplateSummary, "slug">): string | null {
  return getExplainer(template.slug) ? template.slug : null;
}

export function explainerHrefFor(template: Pick<TemplateSummary, "slug">): string | null {
  const slug = explainerSlugFor(template);
  return slug ? `/strategies/templates/${slug}` : null;
}
