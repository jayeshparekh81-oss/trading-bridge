import type { ReactNode } from "react";

/**
 * /start — the first-timer guided path. Deliberately OUTSIDE the (dashboard) group: a
 * first-timer has no dashboard yet, so no sidebar, no nav, one column, phone-first.
 * No auth redirect here — the path's first screen IS signup; the page decides.
 */
export default function StartLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <main className="mx-auto flex w-full max-w-md flex-col gap-4 px-4 py-6">{children}</main>
    </div>
  );
}
