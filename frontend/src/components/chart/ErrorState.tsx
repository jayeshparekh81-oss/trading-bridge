/**
 * ErrorState — full-area error banner with retry CTA.
 *
 * Three distinct shapes:
 *   - ``fetch`` — initial REST history failed (no candles to render).
 *     Shown full-area with a retry button.
 *   - ``broker_disconnected`` — backend's 5-minute reconnect
 *     threshold breached; live feed is dark. (As of Day-4 / A4 this
 *     variant is no longer used in production — ChartContainer now
 *     surfaces broker disconnects via sonner toast — but the kind
 *     is retained for components.test.tsx coverage and possible
 *     re-use in non-toast contexts.)
 *   - ``page-crash`` — Next.js error.tsx boundary fallback. Used
 *     when an uncaught render error bubbles up to the chart route
 *     segment. Renders full-area with a retry button wired to
 *     ``unstable_retry`` (the v16.2.0 successor to ``reset``).
 */

"use client";

import { AlertTriangle, RotateCw } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export interface ErrorStateProps {
  kind: "fetch" | "broker_disconnected" | "page-crash";
  message: string;
  /** Optional retry handler. When supplied, renders a retry button. */
  onRetry?: () => void;
}

const TITLES: Record<ErrorStateProps["kind"], string> = {
  fetch: "Chart data load nahi ho sake",
  broker_disconnected: "Broker connection toot gaya",
  "page-crash": "Chart crash ho gaya",
};

export function ErrorState({ kind, message, onRetry }: ErrorStateProps) {
  const title = TITLES[kind];
  return (
    <div
      className="flex h-full w-full items-center justify-center p-6"
      data-testid={`chart-error-${kind}`}
    >
      <Alert variant="destructive" className="max-w-xl">
        <AlertTriangle aria-hidden="true" />
        <AlertTitle>{title}</AlertTitle>
        <AlertDescription>{message}</AlertDescription>
        {onRetry && (
          <div className="mt-3">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onRetry}
              data-testid="chart-error-retry"
            >
              <RotateCw className="mr-1.5 h-3 w-3" />
              Retry
            </Button>
          </div>
        )}
      </Alert>
    </div>
  );
}
