import type { ReactNode } from "react";

import { PracticeBanner } from "@/components/site/practice-banner";

/**
 * /start — the first-timer guided path. Deliberately OUTSIDE the (dashboard) group: a
 * first-timer has no dashboard yet, so no sidebar, no nav, one column, phone-first.
 * No auth redirect here — the path's first screen IS signup; the page decides.
 */
export default function StartLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* 2 Oct 2026 (founder, item 4): NOT sticky here — a sticky banner slid over "Kadam 2/5" and
          "3 kadam baaki" as soon as the customer scrolled, at 375 and at 1440. It stays the first
          thing on the screen; it never covers anything. */}
      <PracticeBanner sticky={false} />
      <main className="mx-auto flex w-full max-w-md flex-col gap-4 px-4 py-6">{children}</main>
    </div>
  );
}
