/**
 * /chart — Day-5 chart page.
 *
 * Route placement: under ``(dashboard)/`` route group, so the
 * inherited ``(dashboard)/layout.tsx`` provides auth gating
 * (``useAuth`` redirect to ``/login``), Sidebar + TopBar +
 * MobileNav chrome, and onboarding step enforcement. The chart
 * canvas fills the remaining viewport.
 *
 * Client component (``use client``) because the chart relies on
 * canvas rendering + WebSocket — neither survives SSR.
 *
 * Day-5 scope contains NO route params; ``params``/``searchParams``
 * Next.js 16 Promise-shape doesn't apply here. Future filters
 * (?symbol=X&tf=5m for deep links) would need the v16 async
 * pattern.
 */

"use client";

import { ChartContainer } from "@/components/chart/ChartContainer";

export default function ChartPage() {
  return <ChartContainer />;
}
