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

import { cn } from "@/shared/lib/utils";

export const PRACTICE_PATH_LINE =
  "Practice mode: is raaste par nakli order hote hain, asli paisa nahi lagta — koi order broker tak nahi jaata.";

export function PracticeBanner({ sticky = true }: { sticky?: boolean }) {
  return (
    <div
      role="status"
      data-testid="practice-banner"
      className={cn(
        "z-20 w-full border-b border-accent-gold/40 bg-accent-gold/10 px-4 py-2 text-center text-sm font-medium text-foreground",
        sticky && "sticky top-0",
      )}
    >
      {PRACTICE_PATH_LINE}
    </div>
  );
}
