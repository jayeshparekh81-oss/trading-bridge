/**
 * LoadingState — skeleton placeholder for the initial history fetch.
 *
 * Day-5 scope: a single Skeleton block sized to fit the chart canvas
 * area. Day-4 polish may add OHLC-axis-shaped skeletons.
 */

"use client";

import { Skeleton } from "@/components/ui/skeleton-loader";

export function LoadingState() {
  return (
    <div
      className="flex h-full w-full items-center justify-center p-4"
      data-testid="chart-loading"
    >
      <Skeleton className="h-full w-full rounded-lg" />
    </div>
  );
}
