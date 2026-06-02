/**
 * Verification-badge lookup for the Indicator Library.
 *
 * Reads the build-time-static JSON artifact shipped by Queue WW Sprint 8c
 * (``docs/indicator_library_badges.json`` → mirrored to
 * ``frontend/src/data/indicator_library_badges.json``). 96 entries, one
 * per indicator slug, classifying each into one of 5 customer-facing
 * badges (Verified, Verified*, Best-effort, Convention varies,
 * Under review).
 *
 * See: ``docs/INDICATOR_LIBRARY_VERIFICATION_SPEC.md``.
 */

import data from "@/data/indicator_library_badges.json";

export type VerificationBadgeKind =
  | "Verified"
  | "Verified*"
  | "Best-effort"
  | "Convention varies"
  | "Under review";

export interface VerificationBadgeEntry {
  indicator: string;
  tier_pine: string;
  tier_talib: string;
  divergence_note: string;
  badge: VerificationBadgeKind;
  badge_help: string;
}

interface BadgeFile {
  generated_from: string;
  row_count: number;
  entries: VerificationBadgeEntry[];
}

const FILE = data as BadgeFile;

const BY_SLUG: ReadonlyMap<string, VerificationBadgeEntry> = (() => {
  const map = new Map<string, VerificationBadgeEntry>();
  for (const e of FILE.entries) map.set(e.indicator, e);
  return map;
})();

/**
 * Look up the verification badge for a given indicator slug. Returns
 * ``undefined`` when the indicator isn't in the badge artifact — caller
 * should treat that as "no badge to render" rather than an error.
 */
export function getVerificationBadge(
  slug: string,
): VerificationBadgeEntry | undefined {
  return BY_SLUG.get(slug);
}

/**
 * All entries (mostly useful for tests and the eventual marketing-page
 * aggregate-count widget).
 */
export function allVerificationEntries(): readonly VerificationBadgeEntry[] {
  return FILE.entries;
}
