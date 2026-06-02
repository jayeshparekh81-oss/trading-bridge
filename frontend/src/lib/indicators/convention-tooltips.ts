/**
 * Convention-tooltip lookup for the 6 ⚠ Convention varies indicators.
 *
 * Source: ``docs/CONVENTION_TOOLTIP_FINAL.md`` (Queue WW Sprint 8d),
 * mirrored to ``frontend/src/data/convention_tooltips.json`` for
 * build-time import. Each row provides a short variant (first
 * sentence, ~15-25 words) for chart-hover / dropdown contexts and a
 * full variant (50-80 words) for the detail-modal context.
 */

import data from "@/data/convention_tooltips.json";

export interface ConventionTooltipEntry {
  indicator: string;
  tooltip_short: string;
  tooltip_full: string;
}

interface TooltipFile {
  source: string;
  entries: ConventionTooltipEntry[];
}

const FILE = data as TooltipFile;

const BY_SLUG: ReadonlyMap<string, ConventionTooltipEntry> = (() => {
  const map = new Map<string, ConventionTooltipEntry>();
  for (const e of FILE.entries) map.set(e.indicator, e);
  return map;
})();

/**
 * Returns the convention tooltip for the given slug, or ``undefined``
 * when the slug isn't one of the 6 Convention-varies indicators.
 */
export function getConventionTooltip(
  slug: string,
): ConventionTooltipEntry | undefined {
  return BY_SLUG.get(slug);
}

/** True iff the slug is one of the 6 Convention-varies indicators. */
export function isConventionVaries(slug: string): boolean {
  return BY_SLUG.has(slug);
}
