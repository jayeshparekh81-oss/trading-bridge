/**
 * The practice-mode banner on every customer-path screen (founder, 1 Oct 2026: "paper demo only
 * with the practice banner on every screen"). TRUE for every visitor: the customer path sends no
 * order to any broker while MARKETPLACE_FANOUT_ENABLED / CUSTOMER_LANE_ORDER_ENABLED are OFF —
 * worded about THIS path, so it never tells the founder his own live BSE strategy is paper (INC #12).
 *
 * Mounted (2 Oct 2026): ONCE by `app/start/layout.tsx` (sticky — one column, no chrome) and ONCE by
 * `app/(dashboard)/layout.tsx` for every CUSTOMER (non-admin) account, `sticky={false}` there so it
 * can never sit under the Simple shell's own sticky header. No page mounts its own copy.
 */

"use client";

import { cn } from "@/shared/lib/utils";
import { siteCopy } from "@/lib/i18n/copy/site";
import { useCopy, type Lang } from "@/lib/i18n/core";

/** The Hinglish line, by name (the 1-2 Oct tests pin it); the component reads the customer's language. */
export const PRACTICE_PATH_LINE = siteCopy.dicts.hinglish.practice_line;
export const practiceLine = (lang: Lang) => siteCopy.pick(lang).practice_line;

export function PracticeBanner({ sticky = true }: { sticky?: boolean }) {
  const { c } = useCopy(siteCopy);
  return (
    <div
      role="status"
      data-testid="practice-banner"
      className={cn(
        "z-20 w-full border-b border-accent-gold/40 bg-accent-gold/10 px-4 py-2 text-center text-sm font-medium text-foreground",
        sticky && "sticky top-0",
      )}
    >
      {c.practice_line}
    </div>
  );
}
