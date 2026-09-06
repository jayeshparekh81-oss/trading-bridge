import { DEFAULT_NEXT, safeNextPath } from "@/lib/safe-next";

/**
 * Where onboarding should send the customer when it finishes, if the visit
 * started with a destination (Start Free on a public strategy card carries
 * `?next=/marketplace/<listing>` through register → onboarding). Same-site
 * paths only; null when there is nothing more specific than the home.
 */
export function onboardingReturnPath(raw: string | null | undefined): string | null {
  const p = safeNextPath(raw);
  return p === DEFAULT_NEXT ? null : p;
}
