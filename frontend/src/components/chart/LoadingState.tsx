/**
 * LoadingState — chart-shaped skeleton for the initial history fetch.
 *
 * Three-layer composition so the loading placeholder reads as
 * "chart loading" at a glance rather than "something loading":
 *   1. Canvas — large rectangular block taking ~90% of the area.
 *   2. Time axis — thin horizontal block along the bottom edge.
 *   3. Price axis — thin vertical block along the right edge.
 *
 * Layout uses a CSS grid (1fr_auto × 1fr_auto) so the canvas
 * naturally fills remaining space after the axis tracks are
 * reserved — works at any container size without media queries.
 */

"use client";

import { Skeleton } from "@/components/ui/skeleton-loader";

// Each Skeleton is wrapped in a thin div carrying the testid because
// the shared ``Skeleton`` component (src/components/ui/skeleton-loader)
// only accepts ``className``, not arbitrary DOM props. Wrapping is
// cheaper than modifying a shared UI primitive used across the app.
export function LoadingState() {
  return (
    <div
      data-testid="chart-loading"
      className="grid h-full w-full grid-cols-[1fr_auto] grid-rows-[1fr_auto] gap-1 p-3"
    >
      <div
        data-testid="chart-loading-canvas"
        className="h-full w-full"
      >
        <Skeleton className="h-full w-full rounded-lg" />
      </div>
      <div
        data-testid="chart-loading-price-axis"
        className="h-full w-8"
      >
        <Skeleton className="h-full w-full rounded-md" />
      </div>
      <div
        data-testid="chart-loading-time-axis"
        className="h-4 w-full"
      >
        <Skeleton className="h-full w-full rounded-md" />
      </div>
      {/* Bottom-right corner stays blank — matches the empty
          intersection between time and price axes on a real chart. */}
      <div aria-hidden="true" />
    </div>
  );
}
