/**
 * ErrorState — full-area error banner with retry CTA.
 *
 * Two distinct shapes:
 *   - ``fetch`` — initial REST history failed (no candles to render).
 *     Shown full-area with a retry button.
 *   - ``page-crash`` — Next.js error.tsx boundary fallback. Used
 *     when an uncaught render error bubbles up to the chart route
 *     segment. Renders full-area with a retry button wired to
 *     ``unstable_retry`` (the v16.2.0 successor to ``reset``).
 *
 * Phase-8 hygiene removed the previously-defined ``broker_disconnected``
 * kind. ChartContainer surfaces broker disconnects via sonner toast
 * (since Day-4 / A4) — the dead variant only added a switch arm
 * nothing routed to.
 */

"use client";

import { AlertTriangle, RotateCw } from "lucide-react";
import Link from "next/link";

import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";

export interface ErrorStateProps {
  kind: "fetch" | "page-crash";
  message: string;
  /** Optional retry handler. When supplied, renders a retry button. */
  onRetry?: () => void;
  /**
   * Optional escape-hatch link rendered alongside Retry. Supply it only
   * for errors Retry can never clear (B7) — a transient blip must not
   * push the customer somewhere else.
   */
  action?: { label: string; href: string };
}

const TITLES: Record<ErrorStateProps["kind"], string> = {
  fetch: "Chart data load nahi ho sake",
  "page-crash": "Chart crash ho gaya",
};

export function ErrorState({
  kind,
  message,
  onRetry,
  action,
}: ErrorStateProps) {
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
        {(action || onRetry) && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {action && (
              <Button
                nativeButton={false}
                render={<Link href={action.href} />}
                size="sm"
                data-testid="chart-error-action"
              >
                {action.label}
              </Button>
            )}
            {onRetry && (
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
            )}
          </div>
        )}
      </Alert>
    </div>
  );
}
