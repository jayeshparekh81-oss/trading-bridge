/**
 * /chart route segment error boundary.
 *
 * Next.js App Router convention (``error.tsx``): automatically
 * wraps the chart route segment + its nested children in a React
 * Error Boundary. When a render error bubbles up here, this
 * component renders as the fallback UI.
 *
 * v16.2.0 changed the recommended retry prop from ``reset`` to
 * ``unstable_retry``. The latter re-fetches AND re-renders the
 * segment (closer to a full re-mount), whereas ``reset`` only
 * re-renders without re-fetching. For a chart whose render
 * depended on hook state (history/WS/token), re-fetching is the
 * right behaviour — a transient API blip is the most likely
 * trigger.
 *
 * NOT a server component. Error boundaries must be client
 * components per Next.js docs ("Error boundaries must be Client
 * Components").
 */

"use client";

import { useEffect } from "react";

import { ErrorState } from "@/components/chart/ErrorState";

interface ChartErrorProps {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}

export default function ChartError({
  error,
  unstable_retry,
}: ChartErrorProps) {
  useEffect(() => {
    // Best-effort client-side error log. Sentry's client config
    // (sentry.client.config.ts) auto-captures console.error in
    // production, so this also flows into the dashboards.
    console.error("[chart] error boundary caught:", error);
  }, [error]);

  const message = error.digest
    ? `${error.message || "Unexpected render error"} (ID: ${error.digest})`
    : error.message || "Unexpected render error";

  return (
    <div
      className="flex h-[calc(100vh-4rem)] flex-col"
      data-testid="chart-error-boundary"
    >
      <ErrorState
        kind="page-crash"
        message={message}
        onRetry={unstable_retry}
      />
    </div>
  );
}
